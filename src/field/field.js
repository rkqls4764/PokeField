// No network calls, game engine, or per-frame Python reruns.
export default function(component) {
  const {parentElement:root,data,setTriggerValue}=component;
  // v2 runs JS again on data changes, but invokes returned cleanup only on unmount.
  // Stop the previous controller before restoring its latest state on every render.
  root.__pokemonLabCleanup?.();
  const field=root.querySelector('#field'),creatures=root.querySelector('#creatures');
  const ball=root.querySelector('#throw'),projectile=root.querySelector('#projectile');
  const aim=root.querySelector('#aim'),notice=root.querySelector('#notice');
  const storageKey='pokemon-lab-field-v1';
  let saved={}; try {saved=JSON.parse(sessionStorage.getItem(storageKey)||'{}');} catch (_) {}
  const pool=data.pool||[],byId=new Map(pool.map(p=>[p.id,p]));
  let stopped=false,frame=0,last=performance.now(),lastSave=0,drag=null,flight=null;
  const timers=new Set();
  function later(fn,ms){const id=setTimeout(()=>{timers.delete(id);if(!stopped)fn();},ms);timers.add(id);return id;}
  let actors=(saved.actors||[]).filter(a=>byId.has(a.id)).slice(0,3);
  let pending=saved.pending||null;
  let dexOpen=!!saved.dexOpen;
  const count=root.querySelector('#progress-count'); count.textContent=`${data.count} / ${data.total}`;
  const bar=root.querySelector('#progress-bar'); bar.max=data.total; bar.value=data.count;
  for (const id of ['professor','dex','throw']) root.querySelector(`#${id} .art`).innerHTML=data.assets[id==='throw'?'ball':id];
  projectile.innerHTML=data.assets.ball;
  projectile.style.display='none';projectile.classList.remove('shake');
  function save() {try {sessionStorage.setItem(storageKey,JSON.stringify({actors:actors.map(({el,...a})=>a),pending,dexOpen}));} catch (_) {}}
  function bounds() {
    const f=field.getBoundingClientRect(),header=root.querySelector('header').getBoundingClientRect(),footer=root.querySelector('footer').getBoundingClientRect();
    const size=f.width<600?72:90,height=f.width<600?90:110;
    const left=12,top=Math.max(12,header.bottom-f.top+12);
    return {w:f.width,h:f.height,size,height,left,top,right:Math.max(left,f.width-size-12),bottom:Math.max(top,footer.top-f.top-height-12)};
  }
  function direction(a) {const d=Math.floor(Math.random()*4); a.vx=d===0?-1:d===1?1:0; a.vy=d===2?-1:d===3?1:0; if(a.vx) a.face=a.vx; a.turn=1.2+Math.random()*2.4;}
  function spawn() {const available=pool.filter(p=>!actors.some(a=>a.id===p.id)); if(!available.length)return; const p=available[Math.floor(Math.random()*available.length)]; const a={id:p.id,x:.05+Math.random()*.8,y:.12+Math.random()*.65,face:1,speed:22+Math.random()*16,age:0}; direction(a); actors.push(a);}
  while(actors.length<Math.min(3,pool.length))spawn();
  creatures.replaceChildren();
  function mount(a) {const p=byId.get(a.id),el=document.createElement('button'); el.className='pokemon'; el.dataset.pokemonId=String(a.id); el.setAttribute('aria-label',`${p.name}에게 몬스터볼 던지기`); const img=document.createElement('img'); img.src=p.image||''; img.alt=p.name; img.draggable=false; img.onerror=()=>{img.style.display='none';el.classList.add('missing-image');}; const label=document.createElement('span'); label.textContent=p.name; el.append(img,label); creatures.append(el); a.el=el; el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();const r=el.getBoundingClientRect(),f=field.getBoundingClientRect();throwTo(r.x+r.width/2-f.x,r.y+r.height/2-f.y);}};}
  actors.forEach(mount);
  function replace(a) {a.el?.remove();actors=actors.filter(x=>x!==a);spawn();actors.filter(x=>!x.el).forEach(mount);save();}
  if(pending && data.ack?.event_id===pending.event_id) {
    const target=actors.find(a=>a.id===pending.pokemon_id);
    if(data.ack.ok){notice.textContent=`${byId.get(pending.pokemon_id)?.name||'포켓몬'} 수집 기록 저장 완료!`;if(target)replace(target);}
    else {notice.textContent='기록을 저장하지 못했어요. 다시 던져 주세요.';if(target)target.frozen=false;}
    pending=null;save();
  }
  if(pending) {notice.textContent='포획 기록을 저장하고 있어요…';const a=actors.find(a=>a.id===pending.pokemon_id);if(a)a.frozen=true;later(()=>setTriggerValue('capture',pending),500);}
  function point(e){const r=field.getBoundingClientRect();return {x:e.clientX-r.left,y:e.clientY-r.top};}
  function ballStart(){const f=field.getBoundingClientRect(),b=ball.querySelector('.art').getBoundingClientRect();return {x:b.left+b.width/2-f.left,y:b.top+b.height/2-f.top};}
  function throwTo(x,y) {if(flight||pending)return; const start=ballStart(); flight={x:start.x,y:start.y,sx:start.x,sy:start.y,tx:x,ty:y,t:0,previous:start};projectile.style.display='block';projectile.classList.remove('shake');notice.textContent='몬스터볼이 날아가요!';}
  function hitSegment(from,to,rect) {
    const dx=to.x-from.x,dy=to.y-from.y;let lo=0,hi=1;
    for(const [p,q] of [[-dx,from.x-rect.left],[dx,rect.right-from.x],[-dy,from.y-rect.top],[dy,rect.bottom-from.y]]){if(p===0){if(q<0)return false;}else{const t=q/p;if(p<0)lo=Math.max(lo,t);else hi=Math.min(hi,t);if(lo>hi)return false;}}
    return true;
  }
  function capture(a) {flight=null;a.frozen=true;a.el.classList.add('catching');notice.textContent=`${byId.get(a.id).name} 포획 중…`;projectile.classList.add('shake');
    pending={pokemon_id:a.id,event_id:crypto.randomUUID()};save();
    later(()=>{notice.textContent='포획 기록을 저장하고 있어요…';setTriggerValue('capture',pending);},1000);
  }
  ball.onpointerdown=e=>{if(pending||flight)return;e.preventDefault();ball.setPointerCapture(e.pointerId);drag=e.pointerId;aim.style.display='block';};
  ball.onpointermove=e=>{if(drag!==e.pointerId)return;const p=point(e);aim.style.left=`${p.x-21}px`;aim.style.top=`${p.y-21}px`;};
  ball.onpointerup=e=>{if(drag!==e.pointerId)return;drag=null;aim.style.display='none';const p=point(e);if(p.x<0||p.x>field.clientWidth||p.y<0||p.y>field.clientHeight){notice.textContent='필드 안의 포켓몬 쪽으로 끌어서 놓아 주세요.';return;}throwTo(p.x,p.y);};
  ball.onpointercancel=()=>{drag=null;aim.style.display='none';};
  const transition=root.querySelector('#dex-transition');
  if(dexOpen){transition.style.display='flex';transition.className='opening';if(data.panel!=='dex'){transition.classList.add('closing');later(()=>{transition.style.display='none';transition.className='';dexOpen=false;save();},450);}}
  root.querySelector('#professor').onclick=()=>{save();setTriggerValue('action',{panel:'professor',nonce:crypto.randomUUID()});};
  root.querySelector('#dex').onclick=()=>{transition.style.display='flex';dexOpen=true;requestAnimationFrame(()=>transition.className='opening');save();later(()=>setTriggerValue('action',{panel:'dex',nonce:crypto.randomUUID()}),750);};
  function animate(now){if(stopped)return;const dt=Math.min((now-last)/1000,.05);last=now;const b=bounds();
    for(const a of [...actors]){if(!a.frozen){a.turn-=dt;a.age+=dt;if(a.turn<=0)direction(a);a.x+=a.vx*a.speed*dt/Math.max(1,b.w);a.y+=a.vy*a.speed*dt/Math.max(1,b.h);if((a.x*b.w<=b.left&&a.vx<0)||(a.x*b.w>=b.right&&a.vx>0)){a.vx*=-1;if(a.vx)a.face=a.vx;}if((a.y*b.h<=b.top&&a.vy<0)||(a.y*b.h>=b.bottom&&a.vy>0))a.vy*=-1;if(a.age>65&&!flight&&!pending){replace(a);continue;}}
      // Clamp frozen actors too: resizing during capture must keep the target visible.
      a.x=Math.max(b.left/b.w,Math.min(b.right/b.w,a.x));a.y=Math.max(b.top/b.h,Math.min(b.bottom/b.h,a.y));
      a.el.style.transform=`translate(${a.x*b.w}px,${a.y*b.h}px)`;a.el.querySelector('img').style.transform=`scaleX(${a.face<0?-1:1})`;
    }
    if(flight){const f=flight;f.t+=dt;const t=Math.min(1,f.t/.65);const p={x:f.sx+(f.tx-f.sx)*t,y:f.sy+(f.ty-f.sy)*t-55*Math.sin(Math.PI*t)};projectile.style.left=`${p.x-17}px`;projectile.style.top=`${p.y-17}px`;projectile.style.rotate=`${t*500}deg`;
      const candidates=actors.filter(a=>!a.frozen&&hitSegment(f.previous,p,{left:a.x*b.w+8,right:a.x*b.w+b.size-8,top:a.y*b.h+8,bottom:a.y*b.h+b.size}));
      if(candidates.length)capture(candidates[0]);else if(t===1){flight=null;projectile.style.display='none';notice.textContent='아쉬워요! 다음에는 맞힐 수 있어요.';}else f.previous=p;
    }
    if(now-lastSave>500){save();lastSave=now;}frame=requestAnimationFrame(animate);
  }
  frame=requestAnimationFrame(animate);
  const visibility=()=>save();window.addEventListener('pagehide',visibility);
  const resize=()=>{if(flight){flight=null;projectile.style.display='none';notice.textContent='화면 크기가 바뀌었어요. 다시 조준해 주세요.';}save();};
  window.addEventListener('resize',resize);
  const cleanup=()=>{if(stopped)return;stopped=true;cancelAnimationFrame(frame);for(const id of timers)clearTimeout(id);timers.clear();save();window.removeEventListener('pagehide',visibility);window.removeEventListener('resize',resize);};
  root.__pokemonLabCleanup=cleanup;
  return ()=>{cleanup();if(root.__pokemonLabCleanup===cleanup)delete root.__pokemonLabCleanup;};
}
