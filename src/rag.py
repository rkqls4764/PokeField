import re
from typing import TypedDict
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from .llm import ServiceError
from .document_service import prompt


class RagState(TypedDict,total=False):
    pokemon_id:int
    generation:int
    question:str
    sources:list[dict]
    answer:str
    warnings:list[str]
    history:list[dict]
    comparison:dict
    global_mode:bool
    search_context:dict

def citation_numbers(answer):
    return {int(n) for group in re.findall(r'\[근거\s*([\d,\s]+)\]',answer) for n in group.split(',') if n.strip().isdigit()}
def cited_sources(answer,sources):
    numbers=citation_numbers(answer)
    return [(i,s) for i,s in enumerate(sources,1) if i in numbers]
def catch_targets(catalog,answer,sources):
    """Intersect locally identified names with the exact sources cited by each claim."""
    import json
    from .natural_search import global_conditions
    targets={};start=0
    for marker in re.finditer(r'\[근거\s*[\d,\s]+\]',answer):
        text=answer[start:marker.start()];start=marker.end()
        # Adjacent citation groups belong to the same claim.
        if not text.strip(): continue
        tail=re.match(r'(?:\s*\[근거\s*[\d,\s]+\])*',answer[start:]).group()
        used=[source for _,source in cited_sources(text+marker.group()+tail,sources)]
        allowed=set()
        for source in used:
            evidence=source.get('text','');sid=source.get('species_id');pid=source.get('pokemon_id')
            if pid in catalog.varieties and catalog.species[catalog.varieties[pid]['species_id']]['name_ko'] in evidence: allowed.add(pid)
            if source.get('source_type')=='pokemon_metadata' and source['id'].startswith('species:'):
                try: profile=json.loads(evidence)
                except (ValueError,TypeError): continue
                species={profile.get('species_id')}
                for edge in profile.get('evolutions',[]): species.update((edge.get('from_species_id'),edge.get('to_species_id')))
                allowed.update(pid for pid,v in catalog.varieties.items() if v['is_default'] and v['species_id'] in species and catalog.species[v['species_id']]['name_ko'] in evidence)
            elif pid is None and sid in catalog.species and catalog.species[sid]['name_ko'] in evidence:
                allowed.update(pid for pid,v in catalog.varieties.items() if v['is_default'] and v['species_id']==sid)
        if not allowed: continue
        evidence='\n'.join(source.get('text','') for source in used)
        if 'red-blue' in evidence: text=re.sub(r'레드\s*[·/ㆍ]\s*(?:그린\s*[·/ㆍ]\s*)?블루','',text)
        try: mentioned=global_conditions(catalog,text)[0]
        except ServiceError: continue
        for pid in mentioned:
            variety=catalog.varieties[pid];species=catalog.species[variety['species_id']]
            aliases=(species.get('name_ko'),species.get('name_en'),variety.get('api_name'))
            exact=any(alias and re.search(r'(?<![가-힣A-Za-z])'+re.escape(alias)+r'(?=$|[^가-힣A-Za-z]|(?:일세|란다|라네|야|은|는|이|가|을|를|의|와|과|으로|로|에|도|만|랑))',text,re.I) for alias in aliases)
            if pid in allowed and exact: targets.setdefault(pid,{'pokemon_id':pid,'name':catalog.species[catalog.varieties[pid]['species_id']]['name_ko'],'form':catalog.form_label(pid)})
    return list(targets.values())

def validate_citations(answer,sources):
    return citation_numbers(answer).issubset(set(range(1,len(sources)+1)))

class Claim(BaseModel):
    model_config=ConfigDict(extra='forbid')
    text:str=Field(min_length=1,max_length=2000)
    citations:list[StrictInt]=Field(min_length=1,max_length=20)
class Answer(BaseModel):
    model_config=ConfigDict(extra='forbid')
    claims:list[Claim]=Field(max_length=40)
    not_found:bool=False

def build_graph(retrieve,generate):
    from langgraph.graph import StateGraph,START,END
    graph=StateGraph(RagState)
    graph.add_node('retrieve',retrieve); graph.add_node('generate',generate)
    graph.add_edge(START,'retrieve'); graph.add_edge('retrieve','generate'); graph.add_edge('generate',END)
    return graph.compile()

class RagService:
    def __init__(self,settings,catalog,store,llm,documents=None):
        self.settings=settings; self.catalog=catalog; self.store=store; self.llm=llm; self.documents=documents
        self.graph=build_graph(self.retrieve,self.generate)
    def retrieve(self,state):
        if state.get('global_mode'): return self.retrieve_global(state)
        pid=state['pokemon_id']; gen=state['generation']; question=state['question']
        row=self.catalog.index.get((pid,gen))
        if row is None: raise ServiceError('선택한 형태와 세대의 데이터가 없습니다.')
        if '진화' in question and '메가' not in question:
            return {'sources':[dict(self.catalog.profile_source(row['species_id'],full_chain=True),number=1)],'warnings':[]}
        sources=self.store.get_meta(pid,gen)
        if not sources: raise ServiceError('선택한 포켓몬의 색인이 없습니다. 메타데이터 색인 스크립트를 실행하세요.')
        mentioned={int(n) for n in re.findall(r'(\d+)\s*세대',question)} & set(self.catalog.generations)
        if not mentioned and re.search('언제|바뀌|변경|달라|세대별|부터|변했',question):
            mentioned={r['generation'] for r in self.catalog.records_for(pid)}
        for g in sorted(mentioned-{gen}):
            found=self.store.get_meta(pid,g)
            if found: sources.extend(found)
        if '진화' in question: sources.append(self.catalog.profile_source(row['species_id']))
        warnings=[]
        if not state.get('comparison') and self.settings.auto_collect and self.documents:
            try: self.documents.collect(row['species_id'],question)
            except ServiceError as e: warnings.append(str(e))
        external=self.store.search_docs(question,row['species_id'],self.settings.top_k)
        if not external: warnings.append('이 포켓몬의 외부 설명 문서가 없습니다. 메타데이터로 확인되는 내용만 답합니다.')
        sources.extend(external)
        unique={}
        for s in sources:
            if s['species_id']!=row['species_id']: continue
            unique.setdefault(s['id'],s)
        comparison=state.get('comparison')
        if not comparison:
            for source in unique.values():
                metadata_row=self.catalog.index.get((source.get('pokemon_id'),source.get('generation')))
                if source['source_type']=='pokemon_metadata' and metadata_row:
                    source['title'],source['text']=self.catalog.answer_metadata(metadata_row,question)
        if comparison:
            from .generation_compare import comparison_snapshot
            expected={f'pokemon:{pid}:gen:{g}' for g in (comparison['before_generation'],comparison['after_generation'])}
            if not expected.issubset(unique):
                raise ServiceError('비교 대상 두 세대의 메타데이터 근거가 모두 필요합니다. 기존 색인 상태를 확인하세요.')
            for s in unique.values():
                if s['id'] in expected:
                    s['text']=comparison_snapshot(comparison,s['generation'])
        numbered=[dict(s,number=i) for i,s in enumerate(unique.values(),1)]
        return {'sources':numbered,'warnings':warnings}
    def generate(self,state):
        sources=state.get('sources',[])
        if not sources: return {'answer':state.get('answer','흠, 지금 가진 근거만으로는 확인하기 어렵구나.')}
        # Previous messages are conversational context, never evidence.
        history=[{'role':m['role'],'content':m['content'][:800]} for m in state.get('history',[])[-4:]]
        instructions=prompt('generate_answer.txt'); schema=Answer
        payload={'question':state['question'],'selected_generation':state['generation'],'conversation_context_not_evidence':history,'evidence':[{'number':s['number'],'title':s['title'],'source_type':s['source_type'],'text':s['text']} for s in sources]}
        if state.get('global_mode'):
            payload['python_search']=state.get('search_context',{})
            instructions+='\n전체 포켓몬 질문입니다. 특정 포켓몬을 임의로 선택하지 마세요. Python 검색 조건·개수·기준 세대를 지키고 제공된 후보만 설명하세요. 후보는 전체 결과의 일부일 수 있어요. 여러 세대의 사실을 구분하고 변경 이유는 외부 근거에 명시된 경우에만 설명하세요. 메타데이터만으로 변경 이유를 추측하지 마세요.'
        else:
            payload['selected_pokemon_id']=state['pokemon_id']
            payload['selected_form']={'name':self.catalog.species[self.catalog.varieties[state['pokemon_id']]['species_id']]['name_ko'],'form':self.catalog.form_label(state['pokemon_id'])}
        comparison=state.get('comparison')
        if comparison:
            from .generation_compare import COMPARISON_INSTRUCTIONS,ComparisonAnswer
            instructions+=COMPARISON_INSTRUCTIONS; schema=ComparisonAnswer
            payload['python_comparison']={'before_generation':comparison['before_generation'],'after_generation':comparison['after_generation'],'fields':[f for f in comparison['fields'] if f['status']!='unchanged']}
        cache_key=None
        if state.get('global_mode'):
            from .storage import Cache,digest
            cache=Cache(self.settings.runtime_dir)
            cache_parts={'global_answer_v1':payload,'instructions':instructions,'model':self.settings.chat_model,'provider':self.settings.provider}
            if '진화' in state['question']: cache_parts['evolution_validation']=2
            cache_key=digest(cache_parts)
            cached=cache.get(cache_key)
            if cached is not None and not ('진화' in state['question'] and '확인하기 어렵구나' in cached): return {'answer':cached}
        self.llm.check_key()
        result=self.llm.structured(instructions,payload,schema,'generate_answer',cache=False)
        lines=[]
        reason_found=False
        for claim in result.claims:
            if not set(claim.citations).issubset(set(range(1,len(sources)+1))):
                raise ServiceError('답변의 근거 번호가 실제 문서와 일치하지 않아 답변을 표시하지 않았습니다.')
            inline=citation_numbers(claim.text)
            if not inline.issubset(set(claim.citations)):
                raise ServiceError('본문과 구조화 응답의 근거 번호가 일치하지 않아 표시하지 않았습니다.')
            text=re.sub(r'\[근거\s*[\d,\s]+\]','',claim.text).strip()
            if state.get('global_mode') and re.search('언제|바뀌|변경|세대별|변했',state['question']):
                from .generation_compare import CAUSAL
                if CAUSAL.search(text) and not any(s['source_type']=='external_document' and text in s['text'] for s in (sources[i-1] for i in claim.citations)):
                    continue
            if not comparison:
                pids=list(dict.fromkeys(s['pokemon_id'] for s in sources if s.get('pokemon_id') in self.catalog.varieties))
                for pid in ([state['pokemon_id']] if not state.get('global_mode') else pids): text=self.catalog.humanize_answer(text,pid)
            if comparison:
                from .generation_compare import CAUSAL,reason_quote
                if claim.kind=='reason' or CAUSAL.search(text):
                    verified=reason_quote(claim,sources)
                    if verified:
                        quote,number=verified
                        lines.append(f'외부 문서에 명시된 변경 이유: “{quote}” [근거 {number}]')
                        reason_found=True
                    continue
                required={f'pokemon:{state["pokemon_id"]}:gen:{g}' for g in (comparison['before_generation'],comparison['after_generation'])}
                if not required.issubset({sources[i-1]['id'] for i in claim.citations}): continue
            evidence='\n'.join(sources[i-1]['text'] for i in claim.citations)
            unsupported=self.catalog.unsupported_species(text,evidence)
            if unsupported: raise ServiceError('답변에 해당 근거에서 확인되지 않는 포켓몬 이름이 포함되어 표시하지 않았습니다. 다시 질문해 주세요.',stage='citation_validation',diagnostic={'unsupported_species_ids':unsupported})
            lines.append(text+' '+''.join(f'[근거 {i}]' for i in dict.fromkeys(claim.citations)))
        if result.not_found or not lines: lines.append('흠, 지금 가진 근거만으로는 질문한 내용을 확인하기 어렵구나.')
        if comparison and not reason_found: lines.append('변경 이유는 검색된 외부 문서에서 찾지 못했구나. 근거 없이 추측하지는 않겠네.')
        answer='\n\n'.join(lines)
        if not validate_citations(answer,sources): raise ServiceError('답변 근거 검증에 실패했습니다.')
        if cache_key: cache.put(cache_key,answer)
        return {'answer':answer}
    def retrieve_global(self,state):
        from .natural_search import global_conditions,filter_rows
        question=state['question']
        pids,generations,filters,constrained=global_conditions(self.catalog,question)
        if not pids and not constrained and re.match(r'\s*(?:그럼|그 포켓몬|이 포켓몬|걔)',question):
            for message in reversed(state.get('history',[])):
                if message['role']!='user': continue
                previous,previous_gens,_,_=global_conditions(self.catalog,message['content'])
                if previous:
                    pids=previous; generations=generations or previous_gens; break
        gen=generations[-1] if generations else 9
        context={'generation':gen,'pokemon_ids':pids,'filters':filters.model_dump()}
        sources=[]; warnings=[]
        if pids and '진화' in question and '메가' not in question:
            species_ids=list(dict.fromkeys(self.catalog.varieties[pid]['species_id'] for pid in pids))
            if len(species_ids)>6: raise ServiceError('한 번에 비교할 포켓몬은 6마리까지 지정해 주세요.')
            sources=[self.catalog.profile_source(sid,full_chain=True) for sid in species_ids]
            return {'sources':[dict(source,number=i) for i,source in enumerate(sources,1)],'generation':gen,'search_context':context,'warnings':[]}
        if constrained:
            rows,gen,limits=filter_rows(self.catalog,filters,gen,self.settings)
            # Explicit form names narrow species-level filters to the requested form.
            if pids: rows=[r for r in rows if r['pokemon_id'] in pids]
            context.update(candidate_count=len(rows),thresholds=limits,shown_limit=self.settings.result_limit)
            for row in rows[:self.settings.result_limit]: sources.extend(self.store.get_meta(row['pokemon_id'],gen))
            if not rows: return {'sources':[],'generation':gen,'search_context':context,'answer':'흠, 조건에 맞는 포켓몬을 찾지 못했구나. 조건을 조금 바꿔 보게나.','warnings':[]}
        elif pids:
            if len(pids)>6: raise ServiceError('한 번에 비교할 포켓몬은 6마리까지 지정해 주세요.')
            history_question=bool(re.search('언제|바뀌|변경|달라|세대별|부터|변했',question))
            for pid in pids:
                gens=generations or ([r['generation'] for r in self.catalog.records_for(pid)] if history_question else [9])
                for g in gens: sources.extend(self.store.get_meta(pid,g))
                if history_question:
                    from .generation_compare import compare_generations
                    changes=[]
                    for before,after in zip(gens,gens[1:]):
                        comparison=compare_generations(self.catalog,pid,before,after)
                        changes.extend({'before_generation':before,'after_generation':after,'field':f['label'],'before':f['before_display'],'after':f['after_display']} for f in comparison['fields'] if f['status']=='changed')
                    context.setdefault('verified_changes',{})[str(pid)]=changes
                sid=self.catalog.varieties[pid]['species_id']
                if '진화' in question: sources.append(self.catalog.profile_source(sid))
                sources.extend(self.store.search_docs(question,sid,self.settings.top_k))
        else:
            # Unknown names must not be replaced with a semantically similar Pokémon.
            if re.search('타입|속성|특성|종족값|차이|비교',question) or not re.search('포켓몬|진화|세대|배틀|전투|도감',question):
                warnings.append('포켓몬 이름이나 검색 조건을 확인하지 못했어요. 이름을 정확하게 입력해 주세요.')
            else: sources=self.store.search_global(question,gen,self.settings.top_k)
        unique={s['id']:dict(s) for s in sources}
        for source in unique.values():
            row=self.catalog.index.get((source.get('pokemon_id'),source.get('generation')))
            if source['source_type']=='pokemon_metadata' and row:
                source['title'],source['text']=self.catalog.answer_metadata(row,question)
        if not unique: warnings.append('해당 조건의 색인된 근거가 없습니다.')
        return {'sources':[dict(s,number=i) for i,s in enumerate(unique.values(),1)],'generation':gen,'search_context':context,'warnings':warnings}
    def ask_global(self,question,history=None):
        return self.graph.invoke({'global_mode':True,'generation':9,'question':question.strip()[:2000],'history':history or []})
    def ask(self,pokemon_id,generation,question,history=None):
        self.llm.check_key()
        return self.graph.invoke({'pokemon_id':pokemon_id,'generation':generation,'question':question[:2000],'history':history or []})
