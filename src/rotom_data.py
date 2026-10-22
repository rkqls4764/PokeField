"""Native device data adapter. Reuses the existing exact catalog filter and collection."""
import json
from .collection import dex_rows
from .catalog import TYPE_KO,STAT_KO

DISPLAY={'image_width':314,'image_height':325,'left':34,'top':126,'width':271,'height':138,
         'notch_max_x':57,'notch_center_y':195}

def query_dex(catalog,records,request,image_loader):
    gen=request.get('generation',9)
    if type(gen) is not int or gen not in catalog.generations: raise ValueError('Unknown generation')
    query=str(request.get('query',''))[:80]
    kind=request.get('type','전체');owned=request.get('ownership','전체')
    if kind!='전체' and kind not in TYPE_KO: raise ValueError('Unknown type')
    if owned not in ('전체','수집','미수집'): raise ValueError('Unknown ownership')
    rows=dex_rows(catalog,records,gen,query,None if kind=='전체' else kind,owned)
    pages=max(1,(len(rows)+17)//18)
    requested_page=request.get('page',1)
    if type(requested_page) is not int: raise ValueError('Invalid page')
    page=max(1,min(pages,requested_page));selected=request.get('selected_id')
    row=next((r for r in rows if r['pokemon_id']==selected),None)
    if row is None and rows: row=rows[(page-1)*18]
    def brief(r):
        return {'id':r['pokemon_id'],'number':r['species_id'],'name':r['name_ko'],
                'types':[TYPE_KO.get(t,t) for t in r.get('types') or []],'caught':r['pokemon_id'] in records}
    detail=None
    if row:
        pid=row['pokemon_id'];sid=row['species_id'];species=catalog.species[sid]
        profile=json.loads(catalog.profile_source(sid)['text'])
        abilities=[{'name':catalog.ability_names.get(a['name'],'한국어 이름 미확인'),'hidden':a['is_hidden']} for a in row.get('abilities') or []]
        detail=dict(brief(row),generation=gen,image=image_loader(pid),stats={STAT_KO.get(k,k):v for k,v in row['stats'].items() if v is not None},abilities=abilities,
                    ability_note='도입 이전' if gen<3 else '미확인' if row.get('abilities') is None else '',
                    evolutions=profile.get('evolutions',[]),record=records.get(pid),
                    description=(species.get('flavor_texts_ko') or [{}])[0].get('text','설명 미확인').replace('\n',' '))
    return {'request_id':request.get('request_id'),'generation':gen,'query':query,'type':kind,'ownership':owned,
            'page':page,'pages':pages,'total':len(rows),'rows':[brief(r) for r in rows[(page-1)*18:page*18]],'detail':detail}
