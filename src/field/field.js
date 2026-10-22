// Python supplies verified region pools and commits captures; JS owns animation only.
export default function(component) {
 const {parentElement:root,data,setTriggerValue}=component;root.__pokemonLabCleanup?.();
 const $=s=>root.querySelector(s),field=$('#field'),creatures=$('#creatures'),ball=$('#throw'),projectile=$('#projectile'),aim=$('#aim'),notice=$('#notice'),background=$('#map-background');
 const regions=data.regions,byId=new Map(data.pool.map(p=>[p.id,p])),storageKey='pokemon-lab-regions-v2';let saved={};try{saved=JSON.parse(sessionStorage.getItem(storageKey)||'{}')}catch(_){}
 let stopped=false,frame=0,last=performance.now(),lastSave=0,flight=null,drag=null,swap=null,rotom=null;const timers=new Set();
 function later(fn,ms){const id=setTimeout(()=>{timers.delete(id);if(!stopped)fn()},ms);timers.add(id);return id}
 let regionIndex=Math.max(0,Math.min(regions.length-1,Number(saved.regionIndex)||0));
 let targetCount=saved.targetCount||randomCount(),actors=(saved.actors||[]).filter(a=>regions[regionIndex].pool_ids.includes(a.id)&&a.phase!=='captured');
 let target=saved.target||null,appliedTarget=saved.appliedTarget||null;
 if(!data.target||!['requested','active'].includes(data.target.status))target=null;
 let pending=saved.pending||null,popup=saved.popup||null,dexOpen=!!saved.dexOpen,nextSpawn=0;
 function current(){return regions[regionIndex]}
 function randomCount(){return Math.min(3+Math.floor(Math.random()*8),regions[regionIndex].pool_ids.length)}
 function save(){try{sessionStorage.setItem(storageKey,JSON.stringify({regionIndex,targetCount,actors:actors.map(({el,...a})=>a),pending,popup,dexOpen,target,appliedTarget}))}catch(_){} }
 function bounds(){const f=field.getBoundingClientRect(),h=$('header').getBoundingClientRect(),footer=$('footer').getBoundingClientRect(),size=f.width<600?72:90,height=f.width<600?90:110;return {w:f.width,h:f.height,size,height,left:62,top:Math.max(12,h.bottom-f.top+20),right:Math.max(62,f.width-size-62),bottom:Math.max(h.bottom-f.top+20,footer.top-f.top-height-12)}}
 function updateControls(){const locked=!!(pending||popup||swap||flight||data.panel||rotom?.isLocked());$('#region-prev').disabled=locked;$('#region-next').disabled=locked;ball.disabled=locked;$('#professor').disabled=!!(pending||popup||swap||rotom?.isLocked());$('#dex').disabled=!!(pending||popup||swap||rotom?.isLocked())}
 function showRegion(){background.style.backgroundImage=`url("${new URL(current().background,document.baseURI).href}")`;$('#region-name').textContent=current().name;$('#region-summary').textContent=` · 9세대 기준 · 목표 ${targetCount}마리`;field.dataset.region=current().id;notice.textContent=current().pool_ids.length?`${current().name}에서 새로운 포켓몬을 만나 보세요!`:'이 지역에 확인된 출현 후보가 없어요.'}
 $('#progress-count').textContent=`${data.count} / ${data.total}`;$('#progress-bar').max=data.total;$('#progress-bar').value=data.count;
 for(const id of ['professor','dex','throw'])$(`#${id} .art`).innerHTML=data.assets[id==='throw'?'ball':id];
 projectile.innerHTML=data.assets.ball;projectile.style.display='none';projectile.classList.remove('shake');showRegion();
 function catchable(a){return a.phase==='wandering'||a.phase==='idle'}
 function direction(a){const directions=[[-1,0],[1,0],[0,-1],[0,1],[-1,-1],[1,-1],[-1,1],[1,1]], [dx,dy]=directions[Math.floor(Math.random()*8)],length=Math.hypot(dx,dy);a.phase='wandering';a.vx=dx/length;a.vy=dy/length;if(dx)a.face=dx;a.turn=1.5+Math.random()*2.5}
 function nextAction(a){if(a.phase!=='idle'&&Math.random()<.3){a.phase='idle';a.vx=0;a.vy=0;a.turn=.8+Math.random()*1.7}else direction(a)}
 function spot(b){let best=null,bestDistance=-1;for(let i=0;i<35;i++){const x=(b.left+Math.random()*Math.max(0,b.right-b.left))/b.w,y=(b.top+Math.random()*Math.max(0,b.bottom-b.top))/b.h,distance=Math.min(...actors.map(a=>{const p=a.phase==='entering'&&a.motion?a.motion.to:a;return Math.hypot((p.x-x)*b.w,(p.y-y)*b.h)}),99999);if(distance>bestDistance){best={x,y};bestDistance=distance}if(distance>b.size*1.3)break}return best}
 function motion(a,to,duration){a.motion={from:{x:a.x,y:a.y},to,elapsed:0,duration};if(Math.abs(to.x-a.x)>.001)a.face=to.x<a.x?-1:1}
 function mount(a){const p=byId.get(a.id),el=document.createElement('button');el.className='pokemon';el.dataset.pokemonId=String(a.id);el.setAttribute('aria-label',`${p.name}에게 몬스터볼 던지기`);const img=document.createElement('img');img.src=p.image;img.alt=p.name;img.draggable=false;img.onerror=()=>img.style.display='none';const label=document.createElement('span');label.textContent=p.name;const badge=document.createElement('small');badge.className='target-badge';badge.textContent='목표 포켓몬';badge.hidden=true;el.append(img,label,badge);creatures.append(el);a.el=el;el.onkeydown=e=>{if((e.key==='Enter'||e.key===' ')&&catchable(a)){e.preventDefault();const r=el.getBoundingClientRect(),f=field.getBoundingClientRect();throwTo(r.x+r.width/2-f.x,r.y+bounds().size/2-f.y)}}}
 function spawn(preferred=null){const available=current().pool_ids.filter(id=>byId.has(id)&&!actors.some(a=>a.id===id)&&(preferred===null||id===preferred));if(!available.length)return;const b=bounds(),to=spot(b),side=Math.floor(Math.random()*4),a={id:available[Math.floor(Math.random()*available.length)],x:to.x,y:to.y,phase:'entering',face:1,speed:25+Math.random()*17,age:0,lifetime:20+Math.random()*25};if(side===0)a.x=-(b.size+8)/b.w;if(side===1)a.x=1.02;if(side===2)a.y=-(b.height+8)/b.h;if(side===3)a.y=1.02;motion(a,to,.9+Math.random()*.6);actors.push(a);mount(a)}
 function remove(a){a.el?.remove();actors=actors.filter(other=>other!==a)}
 function exit(a,quick=false){if(!quick&&target?.pokemon_id===a.id)return;if(!catchable(a)&&a.phase!=='entering')return;const b=bounds(),options=[{x:-(b.size+8)/b.w,y:a.y},{x:1.02,y:a.y},{x:a.x,y:-(b.height+8)/b.h},{x:a.x,y:1.02}];let to=options[Math.floor(Math.random()*4)];if(quick)to=options.sort((p,q)=>Math.hypot((p.x-a.x)*b.w,(p.y-a.y)*b.h)-Math.hypot((q.x-a.x)*b.w,(q.y-a.y)*b.h))[0];a.phase='exiting';motion(a,to,quick?.55:Math.max(.8,Math.hypot((to.x-a.x)*b.w,(to.y-a.y)*b.h)/140))}
 creatures.replaceChildren();actors.forEach(mount);
 function stars(point){const host=$('#particles'),b=bounds();for(let i=0;i<24;i++){const p=document.createElement('span');p.className='spark';p.textContent=i%3?'✦':'★';const angle=i/24*Math.PI*2,distance=45+Math.random()*70;p.style.left=`${point.x*b.w}px`;p.style.top=`${point.y*b.h}px`;p.style.setProperty('--dx',`${Math.cos(angle)*distance}px`);p.style.setProperty('--dy',`${Math.sin(angle)*distance}px`);p.style.color=['#ffd45a','#fff1b8','#fff'][i%3];host.append(p);later(()=>p.remove(),1100)}}
 function renderPopup(){const el=$('#capture-popup');el.hidden=!popup;if(!popup)return;const p=popup.detail||byId.get(popup.record.pokemon_id),record=popup.record;$('#capture-message').textContent=record.catch_count===1?'새로운 포켓몬을 수집했어요!':'포켓몬을 다시 포획했어요!';$('#capture-image').src=p.image||byId.get(p.id)?.image||'';$('#capture-name').textContent=`#${String(p.number).padStart(4,'0')} ${p.name}`;$('#capture-types').textContent=`${p.types.join(' / ')} · ${p.generation}세대`;$('#capture-stats').style.display='none';$('#capture-record').textContent=`수집 완료 · 누적 포획 ${record.catch_count}회`;updateControls()}
 if(pending&&data.ack?.event_id===pending.event_id){const a=actors.find(a=>a.id===pending.pokemon_id);if(data.ack.ok){if(target?.pokemon_id===pending.pokemon_id){const completed=target;target=null;tracking('captured',completed)}if(a){a.phase='captured';remove(a)}popup={detail:{...(data.ack.detail||byId.get(pending.pokemon_id)),image:byId.get(pending.pokemon_id)?.image},record:data.ack.record,point:pending.point};notice.textContent=`${popup.detail.name} 수집 기록 저장 완료!`;const point=popup.point;later(()=>stars(point),20);nextSpawn=.5}else{if(a){a.phase='wandering';a.motion=null;a.el.classList.remove('catching')}notice.textContent='기록을 저장하지 못했어요. 다시 시도해 주세요.'}pending=null;save()}
 if(pending){const a=actors.find(a=>a.id===pending.pokemon_id);if(a)a.phase='capturing';notice.textContent='포획 기록을 저장하고 있어요…';later(()=>setTriggerValue('capture',pending),500)}
 renderPopup();$('#capture-confirm').onclick=()=>{popup=null;renderPopup();save();updateControls()};
 const rotomOptions={root,data:data.rotom,onRequest:request=>setTriggerValue('rotom',request),onTools:action=>setTriggerValue('action',{...action,region:current().id}),onLockChange:updateControls};
 if(root.__rotomController){rotom=root.__rotomController;rotom.update(rotomOptions)}else{rotom=mountRotom(rotomOptions);root.__rotomController=rotom}
 function openDex(pid){if(pending||swap||rotom.isLocked())return;popup=null;renderPopup();rotom.open(pid);save();updateControls()}
 $('#capture-dex').onclick=()=>openDex(popup?.record.pokemon_id);
 $('#professor').onclick=()=>{if(pending||popup||swap||rotom.isLocked())return;save();setTriggerValue('action',{panel:'professor',region:current().id,nonce:crypto.randomUUID()})};$('#dex').onclick=()=>{if(!popup)openDex()};
 function tracking(status,request=target){setTriggerValue('tracking',{request_id:request?.request_id||null,pokemon_id:request?.pokemon_id||null,region:current().id,status,nonce:crypto.randomUUID()})}
 function clearTarget(status='cancelled'){const previous=target;target=null;save();if(previous)tracking(status,previous);trackingUI()}
 function trackingUI(){const box=$('#tracking-controls');if(!box)return;box.hidden=!target;$('#tracking-name').textContent=target?`${byId.get(target.pokemon_id)?.name||'포켓몬'} 추적 중`:'';$('#cancel-target').disabled=!!(pending||flight||swap)}
 $('#cancel-target').onclick=()=>{if(!pending&&!flight&&!swap)clearTarget()};
 function beginSwitch(index){swap={index,phase:'exiting'};actors.forEach(a=>exit(a,true));notice.textContent='다음 지역으로 이동하고 있어요…';save();updateControls()}
 function changeRegion(delta){if(pending||popup||flight||swap||data.panel||rotom?.isLocked())return;clearTarget();beginSwitch((regionIndex+delta+regions.length)%regions.length)}
 function processTarget(){
  const incoming=data.target;
  if(!incoming||!['requested','active'].includes(incoming.status)||incoming.request_id===appliedTarget||pending||popup||flight||swap||data.panel||rotom?.isLocked())return;
  const index=regions.findIndex(r=>r.id===incoming.region&&r.pool_ids.includes(incoming.pokemon_id));
  appliedTarget=incoming.request_id;
  if(index<0||!byId.has(incoming.pokemon_id)){tracking('unavailable',incoming);save();return}
  target={...incoming};save();if(index!==regionIndex)beginSwitch(index);
 }
 function ensureTarget(){
  if(!target||target.region!==current().id||pending||popup||swap||flight||data.panel||rotom?.isLocked())return;
  const existing=actors.find(a=>a.id===target.pokemon_id);
  if(existing){if(existing.phase==='exiting'){existing.phase='entering';motion(existing,spot(bounds()),.9)}if(target.status!=='active'){target.status='active';save();tracking('active')}return}
  if(actors.length>=targetCount){if(!actors.some(a=>a.phase==='exiting')){const other=actors.find(a=>a.id!==target.pokemon_id&&a.phase!=='capturing');if(other)exit(other,true)}return}
  spawn(target.pokemon_id);
 }
 trackingUI();
 $('#region-prev').onclick=()=>changeRegion(-1);$('#region-next').onclick=()=>changeRegion(1);
 function point(e){const r=field.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top}}
 function ballStart(){const f=field.getBoundingClientRect(),b=ball.querySelector('.art').getBoundingClientRect();return{x:b.left+b.width/2-f.left,y:b.top+b.height/2-f.top}}
 function throwTo(x,y){if(flight||pending||popup||swap||data.panel||rotom?.isLocked())return;const p=ballStart();flight={sx:p.x,sy:p.y,tx:x,ty:y,t:0,previous:p};projectile.style.display='block';projectile.classList.remove('shake');notice.textContent='몬스터볼이 날아가요!';updateControls()}
 function hitSegment(from,to,rect){const dx=to.x-from.x,dy=to.y-from.y;let lo=0,hi=1;for(const[p,q]of[[-dx,from.x-rect.left],[dx,rect.right-from.x],[-dy,from.y-rect.top],[dy,rect.bottom-from.y]]){if(p===0){if(q<0)return false}else{const t=q/p;if(p<0)lo=Math.max(lo,t);else hi=Math.min(hi,t);if(lo>hi)return false}}return true}
 function capture(a,p){flight=null;a.phase='capturing';a.motion=null;a.el.classList.add('catching');projectile.classList.add('shake');notice.textContent=`${byId.get(a.id).name} 포획 중…`;const b=bounds();pending={pokemon_id:a.id,event_id:crypto.randomUUID(),region:current().id,target_request_id:target?.pokemon_id===a.id?target.request_id:null,point:{x:p.x/b.w,y:p.y/b.h}};save();updateControls();later(()=>{notice.textContent='포획 기록을 저장하고 있어요…';setTriggerValue('capture',pending)},1000)}
 ball.onpointerdown=e=>{if(flight||pending||popup||swap||data.panel||rotom?.isLocked())return;e.preventDefault();ball.setPointerCapture(e.pointerId);drag=e.pointerId;aim.style.display='block'};
 ball.onpointermove=e=>{if(drag!==e.pointerId)return;const p=point(e);aim.style.left=`${p.x-21}px`;aim.style.top=`${p.y-21}px`};ball.onpointerup=e=>{if(drag!==e.pointerId)return;drag=null;aim.style.display='none';const p=point(e);if(p.x<0||p.x>field.clientWidth||p.y<0||p.y>field.clientHeight){notice.textContent='필드 안으로 조준해 주세요.';return}throwTo(p.x,p.y)};ball.onpointercancel=()=>{drag=null;aim.style.display='none'};
 function animate(now){if(stopped)return;processTarget();ensureTarget();trackingUI();const dt=Math.min((now-last)/1000,.05);last=now;const b=bounds();
  if(!swap&&!popup&&!pending&&!data.panel&&!rotom?.isLocked()){nextSpawn-=dt;if(actors.length<targetCount&&nextSpawn<=0&&(!target||actors.some(a=>a.id===target.pokemon_id))){spawn();nextSpawn=.3+Math.random()*.3}}
  for(const a of [...actors]){
   if(a.phase==='entering'||a.phase==='exiting'){const m=a.motion;if(!m){a.phase='wandering';direction(a)}else{m.elapsed+=dt;const t=Math.min(1,m.elapsed/m.duration),ease=t*t*(3-2*t);a.x=m.from.x+(m.to.x-m.from.x)*ease;a.y=m.from.y+(m.to.y-m.from.y)*ease;if(t===1){if(a.phase==='exiting'){remove(a);continue}a.phase='wandering';a.motion=null;direction(a)}}}
   else if(catchable(a)){a.age+=dt;a.turn-=dt;if(a.turn<=0)nextAction(a);a.x+=a.vx*a.speed*dt/b.w;a.y+=a.vy*a.speed*dt/b.h;if(a.x*b.w<b.left&&a.vx<0||a.x*b.w>b.right&&a.vx>0){a.vx*=-1;if(a.vx)a.face=a.vx}if(a.y*b.h<b.top&&a.vy<0||a.y*b.h>b.bottom&&a.vy>0)a.vy*=-1;a.x=Math.max(b.left/b.w,Math.min(b.right/b.w,a.x));a.y=Math.max(b.top/b.h,Math.min(b.bottom/b.h,a.y));if(a.age>a.lifetime&&!pending&&!popup&&!swap)exit(a)}
   const isTarget=target?.pokemon_id===a.id;a.el.classList.toggle('hunt-target',isTarget);a.el.querySelector('.target-badge').hidden=!isTarget;a.el.dataset.phase=a.phase;a.el.style.transform=`translate(${a.x*b.w}px,${a.y*b.h}px)`;a.el.querySelector('img').style.transform=`scaleX(${a.face<0?-1:1})`;a.el.disabled=!catchable(a)||!!popup||!!swap||!!rotom?.isLocked();
  }
  if(swap?.phase==='exiting'&&!actors.length){swap.phase='fading';background.classList.add('fading');later(()=>{regionIndex=swap.index;targetCount=randomCount();showRegion();background.classList.remove('fading');swap=null;nextSpawn=.2;save();tracking('region');updateControls()},300)}
  if(flight){const f=flight;f.t+=dt;const t=Math.min(1,f.t/.65),p={x:f.sx+(f.tx-f.sx)*t,y:f.sy+(f.ty-f.sy)*t-55*Math.sin(Math.PI*t)};projectile.style.left=`${p.x-17}px`;projectile.style.top=`${p.y-17}px`;projectile.style.rotate=`${t*500}deg`;const a=actors.find(a=>catchable(a)&&hitSegment(f.previous,p,{left:a.x*b.w+8,right:a.x*b.w+b.size-8,top:a.y*b.h+8,bottom:a.y*b.h+b.size}));if(a)capture(a,p);else if(t===1){flight=null;projectile.style.display='none';notice.textContent='아쉬워요! 다음에는 맞힐 수 있어요.';updateControls()}else f.previous=p}
  if(now-lastSave>500){save();lastSave=now}frame=requestAnimationFrame(animate)
 }
 updateControls();frame=requestAnimationFrame(animate);
 const visibility=()=>save(),resize=()=>{if(flight){flight=null;projectile.style.display='none';notice.textContent='화면 크기가 바뀌었어요. 다시 조준해 주세요.';updateControls()}save()};window.addEventListener('pagehide',visibility);window.addEventListener('resize',resize);
 const cleanup=()=>{if(stopped)return;stopped=true;cancelAnimationFrame(frame);for(const t of timers)clearTimeout(t);timers.clear();$('#particles').replaceChildren();save();window.removeEventListener('pagehide',visibility);window.removeEventListener('resize',resize)};root.__pokemonLabCleanup=cleanup;return()=>{cleanup();if(root.__pokemonLabCleanup===cleanup){delete root.__pokemonLabCleanup;root.__rotomController?.cleanup();delete root.__rotomController}}
}
