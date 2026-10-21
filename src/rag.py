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

def citation_numbers(answer):
    return {int(n) for group in re.findall(r'\[근거\s*([\d,\s]+)\]',answer) for n in group.split(',') if n.strip().isdigit()}
def cited_sources(answer,sources):
    numbers=citation_numbers(answer)
    return [(i,s) for i,s in enumerate(sources,1) if i in numbers]
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
        pid=state['pokemon_id']; gen=state['generation']; question=state['question']
        row=self.catalog.index.get((pid,gen))
        if row is None: raise ServiceError('선택한 형태와 세대의 데이터가 없습니다.')
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
        if not sources: return {'answer':'문서에서 확인되지 않습니다.'}
        # Previous messages are conversational context, never evidence.
        history=[{'role':m['role'],'content':m['content'][:800]} for m in state.get('history',[])[-4:]]
        instructions=prompt('generate_answer.txt'); schema=Answer
        payload={'question':state['question'],'selected_pokemon_id':state['pokemon_id'],'selected_generation':state['generation'],'conversation_context_not_evidence':history,'evidence':[{'number':s['number'],'title':s['title'],'source_type':s['source_type'],'text':s['text']} for s in sources]}
        comparison=state.get('comparison')
        if comparison:
            from .generation_compare import COMPARISON_INSTRUCTIONS,ComparisonAnswer
            instructions+=COMPARISON_INSTRUCTIONS; schema=ComparisonAnswer
            payload['python_comparison']={'before_generation':comparison['before_generation'],'after_generation':comparison['after_generation'],'fields':[f for f in comparison['fields'] if f['status']!='unchanged']}
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
            unsupported=[s['name_ko'] for s in self.catalog.species.values() if s.get('name_ko') and s['name_ko'] in text and s['name_ko'] not in evidence]
            if unsupported: raise ServiceError('답변에 해당 근거에서 확인되지 않는 포켓몬 이름이 포함되어 표시하지 않았습니다. 다시 질문해 주세요.')
            lines.append(text+' '+''.join(f'[근거 {i}]' for i in dict.fromkeys(claim.citations)))
        if result.not_found or not lines: lines.append('질문하신 정보의 일부 또는 전부가 제공된 문서에서 확인되지 않습니다.')
        if comparison and not reason_found: lines.append('변경 이유는 검색된 외부 문서에서 확인되지 않습니다. 이유를 추측하지 않습니다.')
        answer='\n\n'.join(lines)
        if not validate_citations(answer,sources): raise ServiceError('답변 근거 검증에 실패했습니다.')
        return {'answer':answer}
    def ask(self,pokemon_id,generation,question,history=None):
        self.llm.check_key()
        return self.graph.invoke({'pokemon_id':pokemon_id,'generation':generation,'question':question[:2000],'history':history or []})
