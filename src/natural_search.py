import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from .catalog import TYPE_KO, stat_total, STAT_KO
from .llm import ServiceError
from .document_service import prompt

def structured_intent(question):
    from .battle import intent
    return intent(question)

class Filters(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    generation:int|None=None
    types:list[str]=Field(default_factory=list,max_length=2)
    abilities:list[str]=Field(default_factory=list,max_length=5)
    ability_scope:Literal['any','normal','hidden']='any'
    species_ids:list[StrictInt]=Field(default_factory=list,max_length=10)
    unsupported_conditions:list[str]=Field(default_factory=list,max_length=5)
    min_hp:int|None=None
    min_attack:int|None=None
    min_defense:int|None=None
    min_special_attack:int|None=None
    min_special_defense:int|None=None
    min_speed:int|None=None
    min_total:int|None=None
    high_attack:bool=False
    high_defense:bool=False
    high_special_attack:bool=False
    high_special_defense:bool=False
    high_speed:bool=False
    @field_validator('types')
    @classmethod
    def types_valid(cls,value):
        if any(t not in TYPE_KO for t in value): raise ValueError('Unknown type')
        return list(dict.fromkeys(value))
    @field_validator('generation','min_hp','min_attack','min_defense','min_special_attack','min_special_defense','min_speed','min_total')
    @classmethod
    def nonnegative(cls,value):
        if value is not None and value<0: raise ValueError('Negative filter')
        return value

class Pick(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    pokemon_id:StrictInt
    reason:str=Field(min_length=1,max_length=500)
class Picks(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    candidates:list[Pick]=Field(max_length=10)

def filter_rows(catalog,filters,ui_generation,settings):
    gen=filters.generation if filters.generation is not None else ui_generation
    if gen not in catalog.generations: raise ServiceError('데이터에서 확인할 수 없는 세대입니다.')
    limits={}
    for stat in ('hp','attack','defense','special_attack','special_defense','speed','total'):
        minimum=getattr(filters,'min_'+stat)
        if getattr(filters,'high_'+stat,False): minimum=max(minimum or 0,getattr(settings,'high_'+stat))
        if minimum is not None: limits[stat]=minimum
    matches=[]
    for row in catalog.records:
        if row['generation']!=gen or not set(filters.types).issubset(set(row['types'] or [])): continue
        if filters.species_ids and row['species_id'] not in filters.species_ids: continue
        if filters.abilities:
            if gen<3 or row.get('abilities') is None or (filters.ability_scope=='hidden' and gen<5): continue
            available={a['name'] for a in row['abilities'] if filters.ability_scope=='any' or a['is_hidden']==(filters.ability_scope=='hidden')}
            if not set(filters.abilities).issubset(available): continue
        ok=True
        for stat,minimum in limits.items():
            value=stat_total(row) if stat=='total' else row['stats'].get(stat)
            if value is None or value<minimum: ok=False; break
        if ok: matches.append(row)
    ranked_stats=[s for s in limits if s!='total']
    def rank(r): return sum(r['stats'].get(s) or 0 for s in ranked_stats) if ranked_stats else stat_total(r) or 0
    matches.sort(key=lambda r:(-rank(r),r['pokemon_id']))
    return matches,gen,limits

def local_ability_filters(catalog,question):
    """Recognize dictionary-backed ability/type/species terms; leave other intent to the existing LLM."""
    mentions=catalog.ability_mentions(question)
    if not mentions: return None,False
    remaining=question
    abilities=list(dict.fromkeys(hit[2] for hit in mentions))
    for start,end,_ in reversed(mentions): remaining=remaining[:start]+' '+remaining[end:]
    generations={int(n) for n in re.findall(r'(\d+)\s*세대',remaining)}
    if len(generations)>1: raise ServiceError('검색 세대는 하나만 지정해 주세요.')
    remaining=re.sub(r'\d+\s*세대',' ',remaining)
    types=[]
    for identifier,ko in TYPE_KO.items():
        pattern=r'(?<![A-Za-z])(?:'+re.escape(ko)+'|'+identifier+r')\s*(?:타입|type)(?![A-Za-z])'
        if re.search(pattern,remaining,re.I): types.append(identifier); remaining=re.sub(pattern,' ',remaining,flags=re.I)
    if len(types)>2 or len(abilities)>5: raise ServiceError('한 번에 타입은 2개, 특성은 5개까지 지정해 주세요.')
    # Remove type phrases first: 고스트 can mean a type or the species Haunter.
    names={alias:sid for sid,s in catalog.species.items() for alias in (s.get('name_ko'),s.get('name_en')) if alias}
    species=[]
    for alias in sorted(names,key=len,reverse=True):
        pattern=re.escape(alias)
        if alias.isascii(): pattern=r'(?<![A-Za-z])'+pattern+r'(?![A-Za-z])'
        if re.search(pattern,remaining,re.I): species.append(names[alias]); remaining=re.sub(pattern,' ',remaining,flags=re.I)
    scope='hidden' if re.search('숨겨진|숨은|숨특|hidden',remaining,re.I) else 'normal' if re.search('일반\s*특성|일반|normal',remaining,re.I) else 'any'
    filler={'을','를','이','은','가','는','와','과','의','인','으로','로','에','에서','에서는','기준','기준으로','기준에서','특성','특성을','특성으로','특성이','특성인','특성은','특성의','숨겨진','숨은','숨특','일반','hidden','normal','포켓몬','포켓몬을','포켓몬이','가진','가지는','가지고','있는','가지고있는','찾아줘','찾아','줘','주세요','찾아주세요','알려줘','알려','알려주세요','보여줘','보여주세요','검색','검색해줘','추천해줘','추천','해주세요'}
    tokens=re.sub(r'[^가-힣A-Za-z0-9_-]+',' ',remaining).casefold().split()
    simple=all(token in filler for token in tokens)
    return Filters(generation=next(iter(generations)) if generations else None,types=types,abilities=abilities,ability_scope=scope,species_ids=list(dict.fromkeys(species))),simple

def global_conditions(catalog,question):
    """Dictionary-backed identification and exact filters shared with catalog search."""
    clean=question
    types=[]
    for identifier,ko in TYPE_KO.items():
        pattern=r'(?<![A-Za-z])(?:'+re.escape(ko)+'|'+identifier+r')\s*(?:타입|type)'
        if re.search(pattern,clean,re.I):
            types.append(identifier); clean=re.sub(pattern,' ',clean,flags=re.I)
    mentions=catalog.ability_mentions(clean) if '특성' in clean else []
    for start,end,_ in reversed(mentions): clean=clean[:start]+' '+clean[end:]
    found=[]
    aliases={alias:sid for sid,s in catalog.species.items() for alias in (s.get('name_ko'),s.get('name_en')) if alias}
    for alias in sorted(aliases,key=len,reverse=True):
        pattern=re.escape(alias)
        if alias.isascii(): pattern=r'(?<![A-Za-z])'+pattern+r'(?![A-Za-z])'
        if re.search(pattern,clean,re.I):
            found.append(aliases[alias]); clean=re.sub(pattern,' ',clean,flags=re.I)
    pids=[]
    for sid in dict.fromkeys(found):
        candidates=[pid for pid,v in catalog.varieties.items() if v['species_id']==sid]
        explicit=[pid for pid in candidates if re.search(r'(?<![A-Za-z-])'+re.escape(catalog.varieties[pid]['api_name'])+r'(?![A-Za-z-])',question,re.I)]
        if '메가' in question:
            candidates=[pid for pid in candidates if '-mega' in catalog.varieties[pid]['api_name']]
            suffix=re.search(r'메가[^XYxy]*([XYxy])',question)
            if suffix: candidates=[pid for pid in candidates if catalog.varieties[pid]['api_name'].endswith('-'+suffix[1].lower())]
            if len(candidates)!=1: raise ServiceError('메가진화 형태를 정확하게 지정해 주세요. X형 또는 Y형을 확인해 주세요.')
            pids.extend(candidates)
        elif explicit: pids.extend(explicit)
        else: pids.extend(pid for pid in candidates if catalog.varieties[pid]['is_default'])
    generations=sorted({int(n) for n in re.findall(r'(\d+)\s*세대',question)})
    if any(g not in catalog.generations for g in generations): raise ServiceError('데이터에서 확인할 수 없는 세대입니다.')
    filters=Filters(types=types,abilities=list(dict.fromkeys(m[2] for m in mentions)),ability_scope='hidden' if re.search('숨겨진|숨은|숨특',question) else 'normal' if '일반 특성' in question else 'any')
    stat_aliases={'hp':'HP|체력','attack':'공격력|공격','defense':'방어력|방어','special_attack':'특수공격력|특수공격','special_defense':'특수방어력|특수방어','speed':'스피드|속도','total':'종족값 합계|총합'}
    numeric=question
    for stat,aliases_ in sorted(stat_aliases.items(),key=lambda x:-len(x[0])):
        pattern=r'(?:'+aliases_+r')(?:이|가|은|는)?\s*(\d+)\s*이상'
        hit=re.search(pattern,numeric,re.I)
        if hit: setattr(filters,'min_'+stat,int(hit[1])); numeric=re.sub(pattern,' ',numeric,flags=re.I)
        if stat!='total' and stat!='hp' and (re.search(r'(?:'+aliases_+r')(?:이|가|력)?\s*(?:높|빠)',numeric) or re.search(r'(?:높은|빠른)\s*(?:'+aliases_+r')',numeric)): setattr(filters,'high_'+stat,True)
    if '빠르' in question or '빠른' in question or '빠르고' in question: filters.high_speed=True
    constrained=bool(types or mentions or any(getattr(filters,k) for k in Filters.model_fields if k.startswith(('min_','high_'))))
    if re.search(r'\d+\s*(?:이하|미만|초과)|최저|가장|최고|상위|하위',question): raise ServiceError('최소값(이상) 또는 높은/빠른 조건으로 질문해 주세요. 순위 조건은 아직 지원하지 않아요.')
    if re.search(r'\d+\s*이상',numeric): raise ServiceError('최소값이 적용될 능력치를 확인하지 못했어요. 공격력 120 이상처럼 입력해 주세요.')
    if constrained and re.search('이하|미만|제외|아닌|또는|이거나',question): raise ServiceError('현재 조건 검색은 최소값(이상)과 AND 조건을 지원해요. 조건을 바꿔 주세요.')
    if constrained and re.search('전설|환상|몸무게|키가|색상|배우는 기술|기술을|서식|등장하는',question): raise ServiceError('해당 추가 조건은 현재 정확한 필터링을 지원하지 않아요. 타입·특성·세대·능력치 조건으로 질문해 주세요.')
    if constrained and len(generations)>1: raise ServiceError('조건 검색 세대는 하나만 지정해 주세요.')
    if constrained and found: filters.species_ids=list(dict.fromkeys(found))
    if generations: filters.generation=generations[-1]
    if '특성' in question and not found and not mentions: raise ServiceError('특성 이름을 확인하지 못했어요. 등록된 한국어 또는 영문 특성명을 입력해 주세요.')
    return pids,generations,filters,constrained

class NaturalSearch:
    def __init__(self,settings,catalog,llm): self.settings=settings; self.catalog=catalog; self.llm=llm
    def run(self,question,ui_generation):
        if structured_intent(question)=='moves':
            local=self.catalog.structured_query(question,ui_generation,limit=self.settings.result_limit)
            return dict(local,selection_mode='local_moves',candidate_count=local['search_context']['candidate_count'],filters={},thresholds={},results=[])
        if re.search('이하|미만|제외|아닌|또는|이거나',question):
            raise ServiceError('현재 검색은 타입·특성, 최소값(이상), 높은/빠른 조건과 한 개 세대를 지원해요. 제외·이하·OR 조건은 문장을 바꿔 주세요.')
        local,simple=local_ability_filters(self.catalog,question)
        if simple: filters=local
        else:
            filters=self.llm.structured(prompt('extract_filters.txt'),{'question':question[:2000],'available_generations':self.catalog.generations,'types':TYPE_KO,'recognized_ability_conditions':local.model_dump() if local else None},Filters,'extract_filters')
        if filters.unsupported_conditions: raise ServiceError('지원하지 않는 검색 조건이 포함되어 있어요. 타입·특성·세대·최소 능력치 조건으로 입력해 주세요.')
        if local:
            filters.abilities=list(dict.fromkeys(filters.abilities+local.abilities))
            filters.types=list(dict.fromkeys(filters.types+local.types))
            if local.species_ids: filters.species_ids=local.species_ids
            filters.ability_scope=local.ability_scope
        resolved=[self.catalog.resolve_ability(a) for a in filters.abilities]
        if any(a is None for a in resolved): raise ServiceError('확인할 수 없는 특성 이름이에요. 등록된 한국어 또는 영문 특성명을 입력해 주세요.')
        filters.abilities=list(dict.fromkeys(resolved))
        if '특성' in question and not filters.abilities: raise ServiceError('찾을 특성 이름을 확인하지 못했어요. 예: 부유 특성을 가진 포켓몬 찾아줘.')
        if any(sid not in self.catalog.species for sid in filters.species_ids): raise ServiceError('확인할 수 없는 포켓몬 이름이에요.')
        # Unspecified generation and numeric minima must not be invented by the model.
        explicit={int(n) for n in re.findall(r'(\d+)\s*세대',question)}
        if filters.generation is not None and filters.generation not in explicit:
            raise ServiceError('질문에 없는 세대 조건이 추출됐습니다. 세대를 명시해 다시 검색해 주세요.')
        if explicit and (len(explicit)!=1 or filters.generation not in explicit): raise ServiceError('세대 조건을 하나로 명확하게 입력해 주세요.')
        numbers={int(n) for n in re.findall(r'\d+',question)}
        for field in Filters.model_fields:
            if field.startswith('min_') and getattr(filters,field) is not None and getattr(filters,field) not in numbers:
                raise ServiceError('질문에 없는 최소 능력치가 추출됐습니다. 조건을 다시 입력해 주세요.')
            if field.startswith('min_') and getattr(filters,field) is not None:
                high='high_'+field[4:]
                if high in Filters.model_fields: setattr(filters,high,False)
        matches,gen,limits=filter_rows(self.catalog,filters,ui_generation,self.settings)
        if not filters.types and not limits and not filters.abilities and not filters.species_ids and filters.generation is None:
            raise ServiceError('타입이나 최소 능력치처럼 검색 조건을 구체적으로 입력해 주세요.')
        pool=matches[:max(1,self.settings.candidate_limit)]
        if not pool: return {'filters':filters.model_dump(),'generation':gen,'thresholds':limits,'candidate_count':0,'results':[]}
        facts=[{'pokemon_id':r['pokemon_id'],'name':self.catalog.label(r['pokemon_id']),'generation':gen,'types':r['types'],'stats':r['stats'],'total':stat_total(r)} for r in pool]
        if filters.abilities:
            selected=Picks(candidates=[Pick(pokemon_id=r['pokemon_id'],reason='특성과 검색 조건이 실제 세대 데이터에서 확인됐어요.') for r in pool[:self.settings.result_limit]])
        else:
            selected=self.llm.structured(prompt('select_candidates.txt'),{'question':question,'limits':limits,'candidates':facts,'max_results':self.settings.result_limit},Picks,'select_candidates')
        by_id={r['pokemon_id']:r for r in pool}; seen=set(); results=[]
        for pick in selected.candidates:
            if pick.pokemon_id not in by_id or pick.pokemon_id in seen: continue
            r=by_id[pick.pokemon_id]
            # The final object is built from verified JSONL rows, never model-supplied numbers or names.
            if r not in filter_rows(self.catalog,filters,ui_generation,self.settings)[0]: continue
            seen.add(pick.pokemon_id)
            # Discard free-text numeric claims if they do not occur in the actual record.
            actual={v for v in r['stats'].values() if isinstance(v,int)}|{gen,stat_total(r),r['species_id'],r['pokemon_id']}
            reason=pick.reason
            if any(int(n) not in actual for n in re.findall(r'\d+',reason)):
                reason='요청 조건에 맞는 실제 데이터가 확인된 후보입니다.'
            matched=[dict(name=a['name'],name_ko=self.catalog.ability_names.get(a['name'],'한국어 이름 미등록'),is_hidden=a['is_hidden']) for a in r.get('abilities') or [] if a['name'] in filters.abilities and (filters.ability_scope=='any' or a['is_hidden']==(filters.ability_scope=='hidden'))]
            results.append({'row':r,'reason':reason,'matched_abilities':matched,'verified_reason':', '.join(f'{STAT_KO.get(s,s)} {stat_total(r) if s=="total" else r["stats"].get(s)} ≥ {v}' for s,v in limits.items()),'source':self.catalog.document(r)})
            if len(results)>=self.settings.result_limit: break
        return {'filters':filters.model_dump(),'generation':gen,'thresholds':limits,'candidate_count':len(matches),'results':results,'selection_mode':'local_ability' if filters.abilities else 'llm'}
