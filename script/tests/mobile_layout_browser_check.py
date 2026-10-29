"""Requires loaded demo game on CDP :9222. Test phone viewports without external AI."""
import asyncio,json,sys
from urllib.request import urlopen
import websockets
async def main():
 page=next(p for p in json.load(urlopen('http://127.0.0.1:9222/json')) if p['type']=='page')
 async with websockets.connect(page['webSocketDebuggerUrl']) as ws:
  n=0
  async def call(method,params={}):
   nonlocal n
   n+=1;await ws.send(json.dumps({'id':n,'method':method,'params':params}))
   while True:
    r=json.loads(await ws.recv())
    if r.get('id')==n:return r.get('result',{})
  async def js(code):
   r=await call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True});assert 'exceptionDetails' not in r,r
   return r['result'].get('value')
  await js("document.getElementById('result-title').textContent='あなたの勝ち！';document.getElementById('result-detail').textContent='あなたのHP 70 ／ 相手のHP 27';document.getElementById('total-damage').textContent='合計ダメージ 73';document.getElementById('ranking-feedback').textContent='登録すると、名前・顔・発言と採点理由が公開されます。'")
  for width,height in [(390,844),(360,640),(320,568),(390,600)]:
   await call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':True})
   for screen in ['title','rules','difficulty','draw','battle','result','ranking','ranking-log']:
    await js('''(()=>{const name=%s;document.querySelectorAll('main>section').forEach(e=>e.hidden=e.id!==name+'-screen');document.body.classList.toggle('in-battle',name==='battle');document.getElementById('result').hidden=false;document.getElementById('ranking-form').hidden=false;})()'''%json.dumps(screen))
    await asyncio.sleep(.1)
    r=await js('''(()=>{const s=document.querySelector('main>section:not([hidden])');return {page:document.documentElement.scrollHeight,viewport:innerHeight,canvas:document.getElementById('drawing').getBoundingClientRect().width,bad:[...s.querySelectorAll('button,input,select,canvas')].filter(e=>e.getClientRects().length&&!e.closest('#result-log,#ranking-list,#ranking-log-turns')).map(e=>({id:e.id,rect:e.getBoundingClientRect().toJSON()})).filter(e=>e.rect.bottom>innerHeight-7||e.rect.top<0||e.rect.right>innerWidth+1)}})()''')
    assert not r['bad'],(width,height,screen,r)
    assert r['page']<=height+1,(width,height,screen,r)
    if screen=='draw':assert r['canvas']>100,r
   print('PASS viewport',width,height)
asyncio.run(main())
