/* A native HTML device display. Coordinates are measured against the original 314×325 frame. */
function mountRotom({root,data,onRequest,onTools,onLockChange}) {
 const $=s=>root.querySelector(s),overlay=$('#dex-transition'),stage=$('#rotom-stage'),flip=$('#rotom-flip'),screen=$('#rotom-screen'),content=$('.rotom-content'),button=$('#dex');
 const key='pokemon-lab-rotom-v1';let saved={};try{saved=JSON.parse(sessionStorage.getItem(key)||'{}')}catch(_){}
 let phase=saved.phase==='closed'||!saved.phase?'closed':saved.phase.includes('clos')||['shrinking','screen-deactivating'].includes(saved.phase)?'closed':'opened';
 let filters={generation:9,query:'',type:'전체',ownership:'전체',page:1,selected_id:null,...saved.filters},tab=saved.tab||'list',requestId=saved.requestId||null;
 let listScroll=saved.listScroll||0,detailScroll=saved.detailScroll||0,revealPending=null,scrollFrame=null,restoring=false,layoutWidth=innerWidth,layoutHeight=innerHeight;
 let token=0,disposed=false,debounce=null,response=null;const animations=new Set();
 const display=data?.display||{image_width:314,image_height:325,left:34,top:126,width:271,height:138};
 screen.style.left=`${display.left/display.image_width*100}%`;screen.style.top=`${display.top/display.image_height*100}%`;screen.style.width=`${display.width/display.image_width*100}%`;screen.style.height=`${display.height/display.image_height*100}%`;
 function save(){try{sessionStorage.setItem(key,JSON.stringify({phase,filters,tab,requestId,listScroll,detailScroll}))}catch(_){} }
 function setPhase(next){phase=next;stage.dataset.state=phase;save();onLockChange?.()}
 function sourceRect(){const r=$('#dex .art img').getBoundingClientRect();return{left:r.left,top:r.top,width:r.width,height:r.height}}
 function destination(){const w=Math.min(innerWidth-24,(innerHeight-24)*314/325);return{left:(innerWidth-w)/2,top:(innerHeight-w*325/314)/2,width:w,height:w*325/314}}
 function place(rect){Object.assign(stage.style,Object.fromEntries(Object.entries(rect).map(([k,v])=>[k,`${v}px`])))}
 function freeze(){for(const animation of animations){try{animation.commitStyles()}catch(_){}animation.cancel()}animations.clear()}
 async function animate(el,frames,duration,id){const animation=el.animate(frames,{duration,easing:'cubic-bezier(.4,0,.2,1)',fill:'forwards'});animations.add(animation);try{await animation.finished;if(disposed||id!==token)return false;animation.commitStyles();animation.cancel();return true}catch(_){return false}finally{animations.delete(animation)}}
 function option(select,value,label){const o=document.createElement('option');o.value=String(value);o.textContent=label;select.append(o)}
 $('#rotom-generation').replaceChildren();for(const gen of data?.generations||[1,2,3,4,5,6,7,8,9])option($('#rotom-generation'),gen,`${gen}세대`);
 $('#rotom-type').replaceChildren();option($('#rotom-type'),'전체','모든 타입');for(const [id,ko] of Object.entries(data?.types||{}))option($('#rotom-type'),id,ko);
 $('#rotom-query').value=filters.query;$('#rotom-generation').value=String(filters.generation);$('#rotom-type').value=filters.type;$('#rotom-owned').value=filters.ownership;
 function send(){if(phase!=='opened')return;clearTimeout(debounce);requestId=crypto.randomUUID();$('#rotom-status').textContent='조회 중…';save();onRequest({...filters,request_id:requestId})}
 function render(result){if(!result||result.request_id!==requestId||result===response)return;response=result;if(result.error){$('#rotom-status').textContent=result.error;return}
  restoring=true;filters.page=result.page;$('#rotom-status').textContent=`${result.total}종`;$('#rotom-page').textContent=`${result.page}/${result.pages}`;$('#rotom-prev').disabled=result.page<=1;$('#rotom-next').disabled=result.page>=result.pages;
  const list=$('#rotom-list');list.replaceChildren();
  if(result.reveal_id&&result.reveal_id===filters.reveal_id){revealPending=result.reveal_id;delete filters.reveal_id;detailScroll=0}
  for(const row of result.rows){const el=document.createElement('button');el.className='rotom-row';el.dataset.pokemonId=String(row.id);el.setAttribute('aria-label',`#${row.number} ${row.name}`);const thumb=document.createElement('img');thumb.src=row.image||'';thumb.alt='';thumb.loading='lazy';thumb.onerror=()=>thumb.style.visibility='hidden';const info=document.createElement('span');info.className='rotom-row-info';const name=document.createElement('strong');name.textContent=`${String(row.number).padStart(4,'0')} ${row.name}`;const types=document.createElement('small');types.textContent=(row.types||[]).join(' / ');info.append(name,types);const owned=document.createElement('span');owned.className='rotom-owned';owned.textContent=row.caught?'●':'○';owned.setAttribute('aria-label',row.caught?'수집':'미수집');el.append(thumb,info,owned);el.classList.toggle('selected',row.id===result.detail?.id);el.onclick=()=>{delete filters.reveal_id;revealPending=null;detailScroll=0;filters.selected_id=row.id;tab='detail';applyTab();send()};list.append(el)}
  if(!result.rows.length)list.textContent='조건에 맞는 포켓몬이 없습니다.';
  const detail=$('#rotom-detail');detail.replaceChildren();const p=result.detail;
  function element(tag,value,parent=detail,cls=''){const e=document.createElement(tag);if(value)e.textContent=value;if(cls)e.className=cls;parent.append(e);return e}
  function section(title){const e=element('section','',detail,'rotom-section');element('h4',title,e);return e}
  if(p){filters.selected_id=p.id;$('#rotom-number').textContent=`#${String(p.number).padStart(4,'0')}`;
   const hero=element('div','',detail,'rotom-hero'),image=element('img','',hero,'rotom-pokemon');image.src=p.image;image.alt=p.name;image.onerror=()=>image.remove();
   const info=element('div','',hero);element('small',`No. ${String(p.number).padStart(4,'0')}`,info);element('h3',p.name,info);element('p',p.types.join(' / '),info);element('p',`${p.generation}세대`,info);
   const basics=section('기본 정보');element('p',p.description,basics);element('h4','특성',basics);element('p',p.abilities.map(a=>`${a.name} · ${a.hidden?'숨겨진 특성':'일반 특성'}`).join(' / ')||p.ability_note||'미확인',basics);
   const stats=section('능력치'),grid=element('dl','',stats,'rotom-stats');for(const [label,value] of Object.entries(p.stats)){const cell=element('div','',grid);element('dt',label,cell);element('dd',String(value),cell)}if(!Object.keys(p.stats).length)element('p','능력치 데이터 미확인',stats);
   const evolution=section('진화 정보');for(const route of p.evolution_routes||[])element('p',route,evolution);if(!p.evolution_routes?.length)element('p','확인된 진화 관계 없음',evolution);
   const record=section('수집 기록');element('p',p.record?`수집 완료 · 누적 ${p.record.catch_count}회`:'미수집 · 정보는 모두 열람할 수 있어요.',record);if(p.record){element('p',`최초(UTC): ${p.record.first_caught}`,record);element('p',`최근(UTC): ${p.record.last_caught}`,record)}
   const actions=element('div','',detail,'rotom-detail-actions');const ask=element('button','이 포켓몬에 대해 질문하기',actions);ask.id='rotom-ask';ask.onclick=()=>openPanel('professor',p.id,p.generation);
   for(const label of ['세대 비교','조건 검색']){const action=element('button',label,actions);action.onclick=()=>openPanel('tools',p.id,p.generation,label)}
  }else{$('#rotom-number').textContent='';detail.textContent='목록에서 포켓몬을 선택해 주세요.'}save();applyTab();restoreScroll();
 }
 function restoreScroll(){cancelAnimationFrame(scrollFrame);scrollFrame=requestAnimationFrame(()=>{if(disposed)return;const list=$('#rotom-list');if(getComputedStyle(list).display!=='none')list.scrollTop=listScroll;if(getComputedStyle($('#rotom-detail')).display!=='none')$('#rotom-detail').scrollTop=detailScroll;if(revealPending&&getComputedStyle(list).display!=='none'){const row=list.querySelector(`[data-pokemon-id="${revealPending}"]`);if(row){list.scrollTop=row.offsetTop-list.offsetTop-Math.max(0,(list.clientHeight-row.clientHeight)/2);listScroll=list.scrollTop;revealPending=null;save()}}requestAnimationFrame(()=>{restoring=false})})}
 $('#rotom-list').onscroll=e=>{if(phase==='opened'&&!restoring&&getComputedStyle(e.target).display!=='none'){listScroll=e.target.scrollTop;save()}};$('#rotom-detail').onscroll=e=>{if(phase==='opened'&&!restoring&&getComputedStyle(e.target).display!=='none'){detailScroll=e.target.scrollTop;save()}};
 async function openPanel(panel,pid,generation,tab){await close();if(!disposed&&phase==='closed')onTools({panel,pokemon_id:pid,generation,tab,nonce:crypto.randomUUID()})}
 function applyTab(){stage.dataset.tab=tab;$('#rotom-list-tab').setAttribute('aria-pressed',String(tab==='list'));$('#rotom-detail-tab').setAttribute('aria-pressed',String(tab==='detail'));save()}
 $('#rotom-list-tab').onclick=()=>{tab='list';applyTab();restoreScroll()};$('#rotom-detail-tab').onclick=()=>{tab='detail';applyTab();restoreScroll()};
 $('#rotom-filters-toggle').onclick=()=>{const open=!stage.classList.contains('filters-open');stage.classList.toggle('filters-open',open);$('#rotom-filters-toggle').setAttribute('aria-expanded',String(open))};
 $('#rotom-query').oninput=e=>{filters.query=e.target.value;filters.page=1;filters.selected_id=null;delete filters.reveal_id;revealPending=null;listScroll=0;detailScroll=0;clearTimeout(debounce);debounce=setTimeout(send,250);save()};$('#rotom-query').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();send()}};
 for(const [selector,field] of [['#rotom-generation','generation'],['#rotom-type','type'],['#rotom-owned','ownership']])$(selector).onchange=e=>{filters[field]=field==='generation'?Number(e.target.value):e.target.value;filters.page=1;filters.selected_id=null;delete filters.reveal_id;revealPending=null;listScroll=0;detailScroll=0;send()};
 $('#rotom-prev').onclick=()=>{filters.page--;filters.selected_id=null;delete filters.reveal_id;revealPending=null;listScroll=0;detailScroll=0;send()};$('#rotom-next').onclick=()=>{filters.page++;filters.selected_id=null;delete filters.reveal_id;revealPending=null;listScroll=0;detailScroll=0;send()};
 async function open(pid){if(phase!=='closed'||disposed)return;if(layoutWidth!==innerWidth||layoutHeight!==innerHeight){revealPending=filters.selected_id;layoutWidth=innerWidth;layoutHeight=innerHeight}const id=++token;freeze();if(pid){filters={...filters,generation:9,query:'',type:'전체',ownership:'전체',page:1,selected_id:pid,reveal_id:pid};$('#rotom-query').value='';$('#rotom-generation').value='9';$('#rotom-type').value='전체';$('#rotom-owned').value='전체';tab='detail';listScroll=0;detailScroll=0}
  overlay.hidden=false;overlay.classList.remove('dim');button.style.visibility='hidden';place(sourceRect());flip.style.transform='rotateY(0deg)';screen.classList.remove('lit');content.classList.remove('ready');setPhase('rotating-open');
  if(!await animate(flip,[{transform:'rotateY(0deg)'},{transform:'rotateY(180deg)'}],600,id))return;
  setPhase('expanding');overlay.classList.add('dim');const target=destination();if(!await animate(stage,[{},Object.fromEntries(Object.entries(target).map(([k,v])=>[k,`${v}px`]))],230,id))return;place(target);
  setPhase('screen-activating');screen.classList.add('lit');if(!await animate(content,[{opacity:0},{opacity:1}],380,id))return;content.classList.add('ready');setPhase('opened');applyTab();send();$('#rotom-query').focus({preventScroll:true});
 }
 async function close(){if(phase==='closed'||disposed)return;if(['screen-deactivating','shrinking','rotating-close'].includes(phase))return;const id=++token;clearTimeout(debounce);freeze();setPhase('screen-deactivating');content.classList.remove('ready');screen.classList.remove('lit');
  if(!await animate(content,[{}, {opacity:0}],220,id))return;setPhase('shrinking');const target=sourceRect();if(!await animate(stage,[{},Object.fromEntries(Object.entries(target).map(([k,v])=>[k,`${v}px`]))],520,id))return;place(target);
  setPhase('rotating-close');if(!await animate(flip,[{transform:getComputedStyle(flip).transform},{transform:'rotateY(0deg)'}],600,id))return;overlay.hidden=true;overlay.classList.remove('dim');button.style.visibility='';setPhase('closed');button.focus({preventScroll:true});
 }
 $('#rotom-close').onclick=close;overlay.onclick=e=>{if(e.target===overlay)close()};
 const keydown=e=>{if(e.key==='Escape'&&phase!=='closed'){e.preventDefault();e.stopPropagation();close()}};
 const resize=()=>{if(phase==='closed')return;layoutWidth=innerWidth;layoutHeight=innerHeight;revealPending=filters.selected_id;const closing=['screen-deactivating','shrinking','rotating-close'].includes(phase);token++;freeze();if(closing){overlay.hidden=true;button.style.visibility='';setPhase('closed')}else{place(destination());flip.style.transform='rotateY(180deg)';overlay.hidden=false;overlay.classList.add('dim');screen.classList.add('lit');content.classList.add('ready');content.style.opacity='1';setPhase('opened');restoreScroll();if(!response)send()}};
 window.addEventListener('keydown',keydown,true);window.addEventListener('resize',resize);
 if(phase==='opened'){overlay.hidden=false;overlay.classList.add('dim');place(destination());flip.style.transform='rotateY(180deg)';screen.classList.add('lit');content.classList.add('ready');content.style.opacity='1';button.style.visibility='hidden'}else{overlay.hidden=true;button.style.visibility='';screen.classList.remove('lit');content.classList.remove('ready')}
 stage.dataset.state=phase;applyTab();render(data?.response);
 return {open,close,isLocked:()=>phase!=='closed',update(next){data=next.data;onRequest=next.onRequest;onTools=next.onTools;onLockChange=next.onLockChange;render(data?.response)},cleanup(){if(disposed)return;disposed=true;token++;cancelAnimationFrame(scrollFrame);clearTimeout(debounce);freeze();save();window.removeEventListener('keydown',keydown,true);window.removeEventListener('resize',resize)}};
}
