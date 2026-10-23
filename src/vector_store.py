"""Chroma persistence with explicit embeddings and content-addressed skip logic."""
import os
from .llm import Embeddings, ServiceError

class VectorStore:
    def __init__(self,settings,embeddings=None):
        os.environ.setdefault('ANONYMIZED_TELEMETRY','False')
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        self.settings=settings; self.embeddings=embeddings or Embeddings(settings)
        settings.chroma_dir.mkdir(parents=True,exist_ok=True)
        self.client=chromadb.PersistentClient(path=str(settings.chroma_dir),settings=ChromaSettings(anonymized_telemetry=False))
        self.collections={}
        signature=getattr(self.embeddings,'signature','test')
        for name in ('pokemon_meta','pokemon_docs'):
            col=self.client.get_or_create_collection(name=name,embedding_function=None,metadata={'embedding_signature':signature})
            if col.count() and (col.metadata or {}).get('embedding_signature')!=signature:
                raise ServiceError('기존 색인의 임베딩 모델과 설정이 다릅니다. CHROMA_DIR를 새 경로로 설정하세요.')
            self.collections[name]=col
    def counts(self): return {n:c.count() for n,c in self.collections.items()}
    def upsert(self,name,documents,batch_size=32):
        col=self.collections[name]; changed=[]
        for start in range(0,len(documents),200):
            batch=documents[start:start+200]
            if not batch: continue
            old=col.get(ids=[d['id'] for d in batch],include=['metadatas'])
            hashes={i:m.get('content_hash') for i,m in zip(old['ids'],old['metadatas'])}
            changed.extend(d for d in batch if hashes.get(d['id'])!=d['metadata']['content_hash'])
        for start in range(0,len(changed),batch_size):
            batch=changed[start:start+batch_size]
            vectors=self.embeddings.embed([d['text'] for d in batch])
            col.upsert(ids=[d['id'] for d in batch],documents=[d['text'] for d in batch],metadatas=[d['metadata'] for d in batch],embeddings=vectors)
        return {'changed':len(changed),'skipped':len(documents)-len(changed),'count':col.count()}
    def get_meta(self,pokemon_id,generation):
        r=self.collections['pokemon_meta'].get(ids=[f'pokemon:{pokemon_id}:gen:{generation}'],include=['documents','metadatas'])
        return self._rows(r)
    @staticmethod
    def _rows(result):
        return [dict(id=i,text=t,**m) for i,t,m in zip(result['ids'],result.get('documents') or [],result.get('metadatas') or [])]
    def search_docs(self,query,species_id,top_k):
        col=self.collections['pokemon_docs']
        count=len(col.get(where={'species_id':species_id},include=[])['ids'])
        if not count: return []
        r=col.query(query_embeddings=self.embeddings.embed([query]),where={'species_id':species_id},n_results=min(top_k,count),include=['documents','metadatas','distances'])
        return self._rows({k:v[0] for k,v in r.items() if k in ('ids','documents','metadatas')})
    def replace_document(self,document_key,chunks):
        # Write new chunks before removing stale ones; an interrupted embed retains old evidence.
        result=self.upsert('pokemon_docs',chunks)
        old=self.collections['pokemon_docs'].get(where={'document_key':document_key},include=[])['ids']
        keep={d['id'] for d in chunks}; stale=[i for i in old if i not in keep]
        if stale: self.collections['pokemon_docs'].delete(ids=stale)
        return result
    def search_global(self,query,generation,top_k):
        """Bounded semantic retrieval from the existing two collections."""
        vector=None; sources=[]
        for name in ('pokemon_meta','pokemon_docs'):
            col=self.collections[name]
            where={'generation':generation} if name=='pokemon_meta' else None
            kwargs={'where':where} if where else {}
            count=len(col.get(include=[],**kwargs)['ids'])
            if not count: continue
            if vector is None: vector=self.embeddings.embed([query])
            result=col.query(query_embeddings=vector,n_results=min(top_k,count),include=['documents','metadatas'],**kwargs)
            sources.extend(self._rows({k:v[0] for k,v in result.items() if k in ('ids','documents','metadatas')}))
        return sources
