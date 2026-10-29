"""CPU damage ranking end-to-end QA. Use a DEMO server :8001 with a throwaway DB,
and Chromium CDP :9222. Adds 2000ms synthetic inference latency. No external inference. Run browser scripts sequentially.
"""
import asyncio,base64,json,math
from urllib.request import urlopen
import websockets

async def main():
    assert json.load(urlopen('http://127.0.0.1:8001/api/config'))['mode']=='demo','Use a demo server'
    page=next(p for p in json.load(urlopen('http://127.0.0.1:9222/json')) if p['type']=='page')
    async with websockets.connect(page['webSocketDebuggerUrl']) as ws:
        n=0;errors=[]
        async def call(method,params=None):
            nonlocal n
            n+=1;await ws.send(json.dumps({'id':n,'method':method,'params':params or {}}))
            while True:
                r=json.loads(await ws.recv())
                if r.get('method')=='Runtime.exceptionThrown':errors.append(r)
                if r.get('id')==n:
                    assert 'error' not in r,r
                    return r.get('result',{})
        async def js(code):
            r=await call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
            assert 'exceptionDetails' not in r,r
            return r['result'].get('value')
        async def until(code):
            for _ in range(300):
                if await js(code):return
                await asyncio.sleep(.1)
            raise AssertionError(code+'; '+str(await js('document.body.innerText')))
        async def click(id):await js(f'document.getElementById({json.dumps(id)}).click()')
        async def fill(id,value):await js(f'(()=>{{const e=document.getElementById({json.dumps(id)});e.value={json.dumps(value)};e.dispatchEvent(new Event("input",{{bubbles:true}}));}})()')
        async def shot(path):
            data=await call('Page.captureScreenshot',{'format':'png'});open(path,'wb').write(base64.b64decode(data['data']))
        await call('Runtime.enable');await call('Page.enable');await call('Network.enable')
        await call('Network.setCacheDisabled',{'cacheDisabled':True})
        await call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        await call('Page.navigate',{'url':'http://127.0.0.1:8001/'})
        await until('document.body.dataset.judgeReady==="true"')
        await js('window.speedFetch=window.fetch.bind(window);window.fetch=async(url,options)=>{if(url==="/api/ranking/round")await new Promise(r=>setTimeout(r,2000));return window.speedFetch(url,options)}')
        assert await js('document.getElementById("open-ranking").getBoundingClientRect().height>=60')
        await shot('/tmp/kao-ranking-title-button.png')
        await click('show-rules');await click('begin-drawing');await click('confirm-difficulty')
        r=await js('(()=>{const r=document.getElementById("drawing").getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()')
        async def point(kind,x,y):await call('Input.dispatchMouseEvent',{'type':kind,'x':r['x']+x*r['w'],'y':r['y']+y*r['h'],'button':'left','buttons':0 if kind=='mouseReleased' else 1,'clickCount':1})
        await point('mousePressed',.8,.5)
        for i in range(33):
            angle=i*math.tau/32;await point('mouseMoved',.5+.3*math.cos(angle),.5+.34*math.sin(angle))
        await point('mouseReleased',.8,.5)
        await click('start');await until('document.body.dataset.screen==="battle"')
        for i,text in enumerate(['眉毛、海苔','鼻みたい','口、パン'],1):
            await fill('attack',text);await js('window.speedStart=performance.now()');await click('submit');await click('submit')
            await until('!document.getElementById("attack-cutin").hidden')
            assert await js('performance.now()-window.speedStart<600'), 'Cut-in should start during inference'
            assert await js('document.getElementById("cpu-bar").value==='+str(100-[0,25,48][i-1]))
            await until('document.getElementById("cpu-card").classList.contains("hit")')
            elapsed=await js('performance.now()-window.speedStart')
            assert 2400<=elapsed<3500,elapsed
            print('PASS: 2000ms simulated inference, first hit after',round(elapsed),'ms; cut-in overlaps inference')
            await until('document.body.dataset.screen==="result"' if i==3 else f'document.getElementById("round").textContent.includes("{i+1} / 3") && !document.getElementById("attack").disabled')
        assert await js('document.getElementById("total-damage").textContent.includes("73")')
        assert await js('!document.getElementById("ranking-form").hidden')
        assert await js('document.getElementById("result-ranking").getBoundingClientRect().height>=60')
        await shot('/tmp/kao-cpu-ranking-result.png')
        await fill('ranking-name','<b>テスト</b>');await js('document.getElementById("ranking-form").requestSubmit()');await js('document.getElementById("ranking-form").requestSubmit()')
        await until('document.getElementById("ranking-feedback").textContent.includes("登録しました")')
        await click('result-ranking');await until('document.getElementById("ranking-list").children.length>0')
        assert await js('document.getElementById("ranking-list").textContent.includes("73 DMG")')
        assert await js('document.getElementById("ranking-list").textContent.includes("<b>テスト</b>") && !document.querySelector("#ranking-list strong b")')
        await until('document.querySelector(".ranking-record .ranking-portrait img")?.naturalWidth>0')
        await js('document.querySelector(".ranking-record").click()')
        await until('document.querySelectorAll("#ranking-log-turns>li").length===3')
        assert await js('document.querySelectorAll("#ranking-log-turns blockquote").length===6')
        assert await js('document.getElementById("ranking-log-title").textContent.includes("<b>テスト</b>") && !document.querySelector("#ranking-log-title b")')
        assert await js('document.getElementById("ranking-log-turns").textContent.includes("眉毛、海苔") && document.getElementById("ranking-log-turns").textContent.includes("難易度補正")')
        await until('document.querySelector("#ranking-log-faces .ranking-portrait img")?.naturalWidth>0')
        await shot('/tmp/kao-ranking-log.png')
        for width in [320,390,1280]:
            await call('Emulation.setDeviceMetricsOverride',{'width':width,'height':844,'deviceScaleFactor':1,'mobile':width<600})
            assert await js('document.documentElement.scrollWidth<=innerWidth'),width
        await click('ranking-log-back')
        assert await js('document.body.dataset.screen==="ranking"')
        for width in [320,390,800,1280]:
            await call('Emulation.setDeviceMetricsOverride',{'width':width,'height':844,'deviceScaleFactor':1,'mobile':width<600})
            assert await js('document.documentElement.scrollWidth<=innerWidth'),width
        await call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        await shot('/tmp/kao-cpu-ranking-list.png')
        await fill('ranking-difficulty','hard');await js('document.getElementById("ranking-difficulty").dispatchEvent(new Event("change"))')
        await until('!document.getElementById("ranking-status").textContent.includes("読み込み中")')
        assert await js('document.getElementById("ranking-list").children.length===0')
        await fill('ranking-difficulty','easy');await js('document.getElementById("ranking-difficulty").dispatchEvent(new Event("change"))')
        await until('document.getElementById("ranking-list").children.length>0')
        await call('Page.reload');await until('document.body.dataset.judgeReady==="true"');await click('open-ranking')
        await until('document.getElementById("ranking-list").textContent.includes("73 DMG")')
        assert not errors,errors
        print('PASS: CPU 3 rounds, 73 damage, server registration, public 3-round logs and back navigation, duplicate lock, safe names, difficulty filters, reload persistence, 320–1280px, no multiplayer UI or JS errors')

if __name__=='__main__':asyncio.run(main())
