/** Optional browser regression: PLAYWRIGHT_MODULE may point to a bundled Playwright package.
 * Run against the locally running app; this test never submits an AI question or analysis.
 */
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{channel:'chrome'})});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   const request=window.requestAnimationFrame.bind(window),cancel=window.cancelAnimationFrame.bind(window);
   window.labAnimationFrames=new Set();
   window.requestAnimationFrame=callback=>{
    if(callback.name!=='animate')return request(callback);
    const id=request(time=>{window.labAnimationFrames.delete(id);callback(time)});
    window.labAnimationFrames.add(id);return id;
   };
   window.cancelAnimationFrame=id=>{window.labAnimationFrames.delete(id);cancel(id)};
  });
  await page.goto(process.env.BROWSER_TEST_URL||'http://127.0.0.1:8505');
  await page.locator('.pokemon').first().waitFor({timeout:45000});
  async function check(width,height){
   await page.setViewportSize({width,height});await page.waitForTimeout(200);
   const field=await page.locator('#field').boundingBox();assert.deepEqual(field,{x:0,y:0,width,height});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth||document.documentElement.scrollHeight>innerHeight),false);
   const header=await page.locator('.lab header').boundingBox(),footer=await page.locator('.lab footer').boundingBox();
   for(const actor of await page.locator('.pokemon').all()){
    const r=await actor.boundingBox();assert.ok(r.x>=0&&r.x+r.width<=width&&r.y>=header.y+header.height&&r.y+r.height<=footer.y);
   }
   assert.equal(await page.evaluate(()=>window.labAnimationFrames.size),1);
  }
  await check(1440,900);const ids=await page.locator('.pokemon').evaluateAll(es=>es.map(e=>e.dataset.pokemonId).sort());
  for(const [w,h] of [[390,844],[844,390],[320,568]])await check(w,h);
  assert.deepEqual(await page.locator('.pokemon').evaluateAll(es=>es.map(e=>e.dataset.pokemonId).sort()),ids);
  await check(1440,900);
  const dialog=page.getByRole('dialog');
  for(let i=0;i<4;i++){
   await page.locator(i%2?'#professor':'#dex').click();await dialog.waitFor();
   await dialog.getByRole('button',{name:'닫기 · 필드로 돌아가기',exact:true}).click();await dialog.waitFor({state:'hidden'});
   await page.locator('#dex-transition').waitFor({state:'hidden'});
   await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>window.labAnimationFrames.size),1);
  }
  assert.deepEqual(errors,[]);console.log('PASS fullscreen bounds, no scroll, resize persistence, repeated overlays and one animation loop');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
