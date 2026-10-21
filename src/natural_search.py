import re
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from .catalog import TYPE_KO, stat_total, STAT_KO
from .llm import ServiceError
from .document_service import prompt

class Filters(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    generation:int|None=None
    types:list[str]=Field(default_factory=list,max_length=2)
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
        ok=True
        for stat,minimum in limits.items():
            value=stat_total(row) if stat=='total' else row['stats'].get(stat)
            if value is None or value<minimum: ok=False; break
        if ok: matches.append(row)
    ranked_stats=[s for s in limits if s!='total']
    def rank(r): return sum(r['stats'].get(s) or 0 for s in ranked_stats) if ranked_stats else stat_total(r) or 0
    matches.sort(key=lambda r:(-rank(r),r['pokemon_id']))
    return matches,gen,limits

class NaturalSearch:
    def __init__(self,settings,catalog,llm): self.settings=settings; self.catalog=catalog; self.llm=llm
    def run(self,question,ui_generation):
        if re.search('이하|미만|제외|아닌|또는|이거나',question):
            raise ServiceError('현재 자연어 검색은 타입, 최소값(이상), 높은/빠른 조건과 한 개 세대를 지원합니다. 제외·이하·OR 조건은 선택형 검색을 활용하거나 문장을 바꿔 주세요.')
        filters=self.llm.structured(prompt('extract_filters.txt'),{'question':question[:2000],'available_generations':self.catalog.generations,'types':TYPE_KO},Filters,'extract_filters')
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
        if not filters.types and not limits and filters.generation is None:
            raise ServiceError('타입이나 최소 능력치처럼 검색 조건을 구체적으로 입력해 주세요.')
        pool=matches[:max(1,self.settings.candidate_limit)]
        if not pool: return {'filters':filters.model_dump(),'generation':gen,'thresholds':limits,'candidate_count':0,'results':[]}
        facts=[{'pokemon_id':r['pokemon_id'],'name':self.catalog.label(r['pokemon_id']),'generation':gen,'types':r['types'],'stats':r['stats'],'total':stat_total(r)} for r in pool]
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
            results.append({'row':r,'reason':reason,'verified_reason':', '.join(f'{STAT_KO.get(s,s)} {stat_total(r) if s=="total" else r["stats"].get(s)} ≥ {v}' for s,v in limits.items()),'source':self.catalog.document(r)})
            if len(results)>=self.settings.result_limit: break
        return {'filters':filters.model_dump(),'generation':gen,'thresholds':limits,'candidate_count':len(matches),'results':results}
