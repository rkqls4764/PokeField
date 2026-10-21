import json
from .storage import Cache, Metrics, digest

class ServiceError(RuntimeError): pass

class LanguageModel:
    def __init__(self,settings):
        self.settings=settings; self.cache=Cache(settings.runtime_dir); self.metrics=Metrics(settings.runtime_dir)
        self.namespace=digest([settings.provider,settings.base_url,settings.chat_model])[:16]
    def check_key(self):
        if not self.settings.api_key: raise ServiceError('API 키가 없습니다. .env의 서비스 선택과 키를 확인하세요.')
    def complete(self,system,payload,purpose='answer',json_mode=False,cache=False):
        self.check_key(); key='llm:'+digest([self.namespace,system,payload,json_mode])
        old=self.cache.get(key) if cache else None
        if old is not None: return old
        from langchain_openai import ChatOpenAI
        model=ChatOpenAI(model=self.settings.chat_model,api_key=self.settings.api_key,base_url=self.settings.base_url,timeout=70,max_retries=1,max_completion_tokens=1800)
        if json_mode: model=model.bind(response_format={'type':'json_object'})
        try:
            response=model.invoke([('system',system),('human',json.dumps(payload,ensure_ascii=False))])
            usage=response.usage_metadata or {}
            self.metrics.record('llm',purpose=purpose,model=self.settings.chat_model,provider=self.settings.provider,**usage)
            text=response.content
            if not isinstance(text,str): raise ValueError('Expected text')
            if json_mode: json.loads(text)
            if cache: self.cache.put(key,text)
            return text
        except Exception as exc:
            self.metrics.record('llm_error',purpose=purpose,error_type=type(exc).__name__)
            raise ServiceError('AI 서비스 호출에 실패했습니다. 키·모델·연결 상태를 확인하세요.') from None
    def structured(self,prompt,payload,schema,purpose,cache=True):
        text=self.complete(prompt+'\nJSON 객체만 출력한다. 스키마: '+json.dumps(schema.model_json_schema(),ensure_ascii=False),payload,purpose,True,cache)
        try: return schema.model_validate_json(text)
        except Exception as exc:
            issues=[{'loc':list(e['loc']),'type':e['type']} for e in exc.errors(include_input=False)] if hasattr(exc,'errors') else []
            self.metrics.record('schema_error',purpose=purpose,issues=issues)
            raise ServiceError('AI가 반환한 구조화 결과가 올바르지 않습니다. 다시 시도해 주세요.') from None

class Embeddings:
    def __init__(self,settings):
        self.settings=settings; self.cache=Cache(settings.runtime_dir); self.metrics=Metrics(settings.runtime_dir)
        self.signature=digest([settings.provider,settings.base_url,settings.embedding_model])[:20]
    def embed(self,texts):
        keys=['emb:'+digest([self.signature,t]) for t in texts]
        values=[self.cache.get(k) for k in keys]
        missing=[i for i,v in enumerate(values) if v is None]
        if not missing: return values
        if not self.settings.api_key: raise ServiceError('임베딩 API 키가 없습니다.')
        from openai import OpenAI
        client=OpenAI(api_key=self.settings.api_key,base_url=self.settings.base_url,timeout=70,max_retries=1)
        try:
            for start in range(0,len(missing),32):
                ids=missing[start:start+32]
                response=client.embeddings.create(model=self.settings.embedding_model,input=[texts[i] for i in ids])
                self.metrics.record('embedding',model=self.settings.embedding_model,text_count=len(ids),input_tokens=response.usage.prompt_tokens,total_tokens=response.usage.total_tokens)
                for i,item in zip(ids,sorted(response.data,key=lambda x:x.index)):
                    values[i]=item.embedding; self.cache.put(keys[i],item.embedding)
        except Exception as exc:
            self.metrics.record('embedding_error',error_type=type(exc).__name__)
            raise ServiceError('임베딩 서비스 호출에 실패했습니다. 임베딩 모델과 API 설정을 확인하세요.') from None
        return values
