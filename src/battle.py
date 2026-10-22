"""Exact, offline type rules and cached learnsets. Never asks a model to calculate/filter."""
import json,re
from functools import cached_property
from math import prod
from .catalog import TYPE_KO
from .llm import ServiceError

METHODS={'level-up':'레벨업','machine':'기술머신','egg':'교배','tutor':'기술 가르침','form-change':'폼 체인지','evolution':'진화','light-ball-egg':'전기구슬 교배','stadium-surfing-pikachu':'스타디움 이벤트'}
NOTE='특성·아이템·날씨·기술 고유 효과를 제외한 일반 타입 상성이네.'

def intent(question):
    if re.search('배우|배워|습득|레벨에|레벨업|기술머신|교배',question):return 'moves'
    if re.search('약점|상성|효과적|몇\s*배|반감|저항|무효|통하지|강한\s*타입|강해|강하|효과\s*없',question):return 'types'
    return None

class BattleData:
    def __init__(self,catalog):self.catalog=catalog
    @cached_property
    def charts(self):return json.loads((self.catalog.data_dir/'type_chart.json').read_text(encoding='utf-8'))['charts']
    @cached_property
    def moves(self):return json.loads((self.catalog.data_dir/'move_catalog.json').read_text(encoding='utf-8'))
    @cached_property
    def learnsets(self):
        return {r['pokemon_id']:r['learnsets'] for r in (json.loads(l) for l in (self.catalog.data_dir/'pokemon_learnsets.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}
    def chart(self,generation):
        if generation not in range(1,10):raise ServiceError('1~9세대 중 하나를 지정해 주게.')
        return self.charts[str(generation)]
    def multiplier(self,attack,defenders,generation=9):
        chart=self.chart(generation)
        if not defenders or len(defenders)>2 or attack not in chart or any(t not in chart for t in defenders):raise ServiceError('해당 세대에 존재하지 않거나 확인되지 않은 타입이네.')
        return prod(chart[attack][t] for t in dict.fromkeys(defenders))
    def defense(self,types,generation=9):return {a:self.multiplier(a,types,generation) for a in self.chart(generation)}
    def move_mentions(self,question):
        hits=[]
        for mid,move in self.moves['moves'].items():
            for alias in {move['name'],move['ko']}:
                pattern=re.escape(alias)
                if alias.isascii():pattern=r'(?<![A-Za-z-])'+pattern+r'(?![A-Za-z-])'
                m=re.search(pattern,question,re.I)
                if m:hits.append((m.start(),m.end(),int(mid)))
        selected=[]
        for hit in sorted(hits,key=lambda h:-(h[1]-h[0])):
            if not any(hit[0]<o[1] and o[0]<hit[1] for o in selected):selected.append(hit)
        return sorted(selected)
    def move_at(self,mid,group):
        move=dict(self.moves['moves'][str(mid)])
        order=self.moves['groups'][str(group)]['order']
        for change in sorted(self.moves['changes'].get(str(mid),[]),key=lambda x:-x['order']):
            if order<change['order']:
                for key in ('power','accuracy','type_id'):
                    if key in change:move['type' if key=='type_id' else key]=change[key]
        return move
    def identify(self,question):
        from .natural_search import global_conditions
        clean=re.sub(r'(?:'+ '|'.join(map(re.escape,list(TYPE_KO)+list(TYPE_KO.values())))+r')\s*(?:타입|type)',' ',question,flags=re.I)
        # Keep the existing form/name resolver; query constraints are handled separately here.
        return global_conditions(self.catalog,clean)[0]
    def source(self,text,title,generation,pid=None,url='https://pokeapi.co/docs/v2/#types'):
        from .storage import digest
        return {'id':'structured:'+digest(text),'title':title,'text':text,'source_type':'pokemon_metadata','source_url':url,'generation':generation,**({'pokemon_id':pid,'species_id':self.catalog.varieties[pid]['species_id']} if pid else {})}
    def query(self,question,generation=9,pokemon_id=None,history=None,limit=10):
        kind=intent(question)
        if not kind:return None
        generations={int(x) for x in re.findall(r'(\d+)\s*세대',question)}
        if len(generations)>1:raise ServiceError('상성·기술 검색은 한 번에 한 세대를 지정해 주게.')
        generation=next(iter(generations),generation);self.chart(generation)
        hits=self.move_mentions(question) if kind=='moves' else []
        clean=question
        for start,end,_ in reversed(hits):clean=clean[:start]+' '+clean[end:]
        pids=self.identify(clean)
        if pokemon_id is not None and pokemon_id not in self.catalog.varieties:raise ServiceError('선택한 포켓몬 ID를 확인할 수 없네.')
        if not pids and pokemon_id:pids=[pokemon_id]
        if not pids and re.match(r'\s*(그럼|그 포켓몬|이 포켓몬)',question):
            for message in reversed(history or []):
                if message['role']=='user':
                    found=self.identify(message['content'])
                    if found:pids=found;break
        if len(pids)>6:raise ServiceError('한 번에 포켓몬은 6마리까지 살펴볼 수 있네.')
        return self.type_query(question,pids,generation) if kind=='types' else self.move_query(question,pids,generation,hits,limit,not generations and pokemon_id is None)
    def type_query(self,q,pids,gen):
        types=[t for t,ko in TYPE_KO.items() if re.search(re.escape(ko)+r'\s*타입|(?<![A-Za-z])'+t+r'\s*type',q,re.I)]
        if any(t not in self.chart(gen) for t in types):raise ServiceError('해당 세대에는 이 타입이 존재하지 않네.')
        sources=[];lines=[]
        def add(text,pid=None):
            sources.append(self.source(text,'타입 상성 계산 · '+(self.catalog.species[self.catalog.varieties[pid]['species_id']]['name_ko'] if pid else '공격·방어 규칙'),gen,pid));lines.append(text+f' [근거 {len(sources)}]')
        if pids:
            for pid in pids:
                row=self.catalog.index.get((pid,gen));name=self.catalog.species[self.catalog.varieties[pid]['species_id']]['name_ko']
                if not row or not row.get('types'):add(f'{name}: {gen}세대 타입 데이터가 없어 계산할 수 없네.',pid);continue
                if types and re.search('공격|몇\s*배',q):
                    attack=types[0];factor=self.multiplier(attack,row['types'],gen)
                    add(f"{name}({ ' / '.join(TYPE_KO[t] for t in row['types'])})에게 {TYPE_KO[attack]} 타입 공격은 {factor:g}배라네.",pid)
                elif re.search('공격\s*상성',q):
                    for attack in row['types']:
                        chart=self.chart(gen)[attack];add(f"{name}의 {TYPE_KO[attack]} 공격 상성: "+self.grouped(chart),pid)
                else:add(f"{name}({ ' / '.join(TYPE_KO[t] for t in row['types'])})의 방어 상성: "+self.grouped(self.defense(row['types'],gen)),pid)
        elif types:
            if re.search('공격|통하지|효과\s*없|무효',q):
                for attack in types:add(f'{TYPE_KO[attack]} 타입 공격 상성: '+self.grouped(self.chart(gen)[attack]))
            else:add(f"{' / '.join(TYPE_KO[t] for t in types)} 타입의 방어 상성: "+self.grouped(self.defense(types,gen)))
        else:add('포켓몬 이름이나 공격·방어 타입을 정확히 알려 주게.')
        return {'sources':sources,'verified_lines':lines+[f'{gen}세대 기준. '+NOTE],'generation':gen,'warnings':[]}
    @staticmethod
    def grouped(factors):
        parts=[]
        for label,predicate in [('약점 / 효과 굉장함',lambda v:v>1),('저항 / 효과 별로',lambda v:0<v<1),('무효 / 효과 없음',lambda v:v==0)]:
            items=[f'{TYPE_KO[t]} {v:g}배' for t,v in factors.items() if predicate(v)]
            parts.append(label+': '+(', '.join(items) or '없음'))
        return '; '.join(parts)+'. 나머지는 1배라네.'
    def move_query(self,q,pids,gen,hits,limit,default_gen):
        if re.search('이하|이상|제외|아닌|또는|교배.*레벨업|레벨업.*교배',q):raise ServiceError('현재 기술 검색은 한 가지 습득 방법과 정확한 레벨을 지원하네. 조건을 나눠 주게.')
        mids={h[2] for h in hits}
        if len(mids)>1:raise ServiceError('기술은 한 번에 하나씩 검색해 주게.')
        groups=self.moves['groups'];versions=self.moves['versions'];group_ids=set();found_version=False
        for name,info in versions.items():
            for alias in {name,info['ko']}:
                pattern=(r'(?<![A-Za-z-])'+re.escape(alias)+r'(?![A-Za-z-])') if alias.isascii() else re.escape(alias)
                ambiguous=any(alias in (s.get('name_ko'),s.get('name_en')) for s in self.catalog.species.values())
                if re.search(pattern,q,re.I) and (not ambiguous or re.search('버전|게임',q)):group_ids.add(info['group']);found_version=True
        for gid,info in groups.items():
            if re.search(r'(?<![A-Za-z-])'+re.escape(info['name'])+r'(?![A-Za-z-])',q,re.I):group_ids.add(int(gid));found_version=True
        if group_ids:
            gens={groups[str(g)]['generation'] for g in group_ids}
            explicit=bool(re.search(r'\d+\s*세대',q))
            if len(gens)!=1 or (explicit and gen not in gens):raise ServiceError('지정한 세대와 게임 버전이 일치하지 않네.')
            if not explicit:gen=next(iter(gens))
            if any(groups[str(g)]['generation']!=gen for g in group_ids):raise ServiceError('선택한 세대와 버전이 다르네.')
        else:group_ids={int(g) for g,v in groups.items() if v['generation']==gen}
        available={gid for rows in self.learnsets.values() for _,gid,_,_ in rows}
        if found_version and not group_ids.issubset(available):raise ServiceError('이 게임 버전의 기술 습득 캐시가 없어 확인할 수 없네.')
        group_ids&=available
        if re.search('특성|종족값|공격력|방어력|위력|명중률',q):raise ServiceError('기술 검색에서는 기술명·타입·버전·습득 방법·정확한 레벨을 지원하네. 다른 조건은 나눠 질문해 주게.')
        if re.search('버전|버젼',q) and not found_version:raise ServiceError('게임 버전을 확인하지 못했네. scarlet-violet처럼 정확한 버전명을 알려 주게.')
        method='level-up' if re.search('레벨업|레벨에|\d+\s*레벨',q) else 'machine' if re.search('기술머신|TM\b',q,re.I) else 'egg' if '교배' in q else 'tutor' if re.search('가르침|가르치',q) else None
        level_match=re.search(r'(\d+)\s*레벨',q);level=int(level_match[1]) if level_match else None
        page_match=re.search(r'(\d+)\s*페이지',q);page=int(page_match[1]) if page_match else 1
        if page<1 or page>10000:raise ServiceError('페이지는 1부터 지정해 주게.')
        type_hits=[(m.start(),t,m.end()) for t,ko in TYPE_KO.items() for m in re.finditer(re.escape(ko)+r'\s*타입',q)]
        move_types={t for start,t,end in type_hits if re.match(r'\s*기술',q[end:])}
        pokemon_types={t for start,t,end in type_hits if not re.match(r'\s*기술',q[end:])}
        if not mids and pids and not move_types and level is None and not re.search('어떤\s*기술|무슨\s*기술|배우는\s*기술|기술[은을이]?\s*배워|버전|게임|version|yellow|scarlet|violet',q,re.I):raise ServiceError('찾는 기술명을 확인하지 못했네. 어떤 기술인지 정확히 알려 주게.')
        if not mids and not pids and not move_types:raise ServiceError('검색할 기술명이나 포켓몬 이름을 확인하지 못했네.')
        matches=[]
        for pid in pids or sorted(self.learnsets):
            row=self.catalog.index.get((pid,gen))
            if not row or not pokemon_types.issubset(set(row.get('types') or [])):continue
            if not pids and not self.catalog.varieties[pid]['is_default']:continue
            for mid,gid,how,learn_level in self.learnsets.get(pid,[]):
                if gid not in group_ids or mids and mid not in mids or method and how!=method or level is not None and learn_level!=level:continue
                move=self.move_at(mid,gid)
                if move_types and move['type'] not in move_types:continue
                matches.append({'pokemon_id':pid,'move':move,'version_group':groups[str(gid)]['name'],'method':how,'level':learn_level})
        # One Pokémon per search result, but a selected Pokémon query lists individual learnsets.
        by_pokemon=not pids
        if by_pokemon:
            buckets={}
            for match in matches:buckets.setdefault(match['pokemon_id'],[]).append(match)
            units=list(buckets.values())
        else:units=[[m] for m in matches]
        total=len(units);page=min(page,max(1,(total+limit-1)//limit));shown=units[(page-1)*limit:page*limit];sources=[];lines=[]
        for unit in shown:
            pid=unit[0]['pokemon_id'];name=self.catalog.species[self.catalog.varieties[pid]['species_id']]['name_ko']
            details=[]
            for match in unit[:8]:
                m=match['move'];info=f"{m['ko']}({TYPE_KO.get(m['type'],'타입 미확인')} / 위력 {m['power'] if m['power'] is not None else '미정의'} / 명중 {m['accuracy'] if m['accuracy'] is not None else '미정의'})"
                details.append(f"{info}: {match['version_group']} · {METHODS.get(match['method'],match['method'])} · 레벨 {match['level']}")
            text=f'{name}: '+ '; '.join(details)+(f"; 이 포켓몬의 습득 기록 {len(unit)}건 중 {len(details)}건 표시" if len(unit)>8 else '')
            sources.append(self.source(text,'기술 습득 기록 · '+name,gen,pid,f'https://pokeapi.co/api/v2/pokemon/{pid}/'));lines.append(text+f' [근거 {len(sources)}]')
        basis=f"{gen}세대 · "+(' / '.join(groups[str(g)]['name'] for g in sorted(group_ids)))+f" · {METHODS.get(method,'모든 습득 방법')} 기준이라네. "+f"총 {total}{'마리' if by_pokemon else '건'}, {page}페이지를 보여 주겠네."
        if not matches:basis+=' 이 범위의 캐시에서 조건에 맞는 습득 기록을 확인하지 못했네. 배울 수 없다는 단정은 하지 않겠네.'
        lines.insert(0,basis)
        lines.append('현재 캐시에 있는 버전별 기록의 합집합이네. 레벨 0은 일반적인 0레벨 습득을 뜻하지 않으며, 전송·이벤트와 기술 사용 가능 여부는 별도 확인이 필요하네.')
        if not sources:
            sources=[self.source(basis,'기술 검색 범위 및 결과',gen,url='https://pokeapi.co/docs/v2/#pokemon')];lines[0]+=' [근거 1]'
        base=re.sub(r'\s*\d+\s*페이지','',q).strip()
        return {'sources':sources,'verified_lines':lines,'generation':gen,'warnings':[],'search_context':{'candidate_count':total,'page':page},'more_question':base+f' {page+1}페이지' if page*limit<total else '', 'move_matches':shown}
