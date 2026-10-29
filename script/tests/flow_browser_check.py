"""Phone-first five-screen flow. Requires server :8001 and CDP :9222. Demo only."""
import asyncio,base64,json
from urllib.request import urlopen
import websockets

async def main():
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
            for _ in range(240):
                if await js(code):return
                await asyncio.sleep(.05)
            raise AssertionError(code)
        async def check_screen(name):
            assert await js('JSON.stringify(["title","rules","difficulty","draw","battle","result"].filter(s=>!document.getElementById(s+"-screen").hidden))')==json.dumps([name],separators=(',',':'))
            assert await js('document.documentElement.scrollWidth<=innerWidth')
        async def shot(name):
            r=await call('Page.captureScreenshot',{'format':'png'})
            with open('/tmp/kao-flow-'+name+'.png','wb') as f:f.write(base64.b64decode(r['data']))
        await call('Page.enable');await call('Runtime.enable');await call('Network.enable')
        await call('Network.setCacheDisabled',{'cacheDisabled':True})
        await call('Emulation.setTouchEmulationEnabled',{'enabled':True})
        await call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        fixture=await call('Page.addScriptToEvaluateOnNewDocument',{'source':"const originalFetch=window.fetch.bind(window);window.fetch=(url,options)=>url==='/api/config'?Promise.resolve(new Response(JSON.stringify({mode:'demo',model:'test'}))):originalFetch(url,options);"})
        await call('Page.navigate',{'url':'http://127.0.0.1:8001/'})
        await until('document.body?.dataset.judgeLoaded==="true"')
        await call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':fixture['identifier']})
        await check_screen('title');await asyncio.sleep(.2);await shot('title')
        assert await js('!document.querySelector("#judge-mode,#open-settings,#settings-dialog")'), 'player AI selector still exists'
        await js('document.getElementById("show-rules").click()');await check_screen('rules');await shot('rules')
        await js('history.back()');await until('document.body?.dataset.screen==="title"')
        await js('history.forward()');await until('document.body?.dataset.screen==="rules"')
        await js('document.getElementById("begin-drawing").click()');await check_screen('difficulty')
        await js('document.querySelector("[data-difficulty=hard]").click()')
        assert await js('document.getElementById("difficulty").value==="hard" && document.querySelectorAll("[data-difficulty][aria-pressed=true]").length===1')
        await js('document.querySelector("[data-difficulty=easy]").click()');await shot('difficulty')
        await js('document.getElementById("confirm-difficulty").click()');await check_screen('draw')
        assert await js('document.getElementById("start").disabled')
        point=await js('(()=>{const r=document.getElementById("drawing").getBoundingClientRect();return {x:r.x,y:r.y,w:r.width}})()')
        for i,(x,y) in enumerate([(.25,.2),(.75,.2),(.75,.8),(.25,.8),(.25,.2)]):
            await call('Input.dispatchMouseEvent',{'type':'mousePressed' if i==0 else 'mouseMoved','x':point['x']+x*point['w'],'y':point['y']+y*point['w'],'button':'left','buttons':1,'clickCount':1})
        await call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':point['x']+.25*point['w'],'y':point['y']+.2*point['w'],'button':'left','clickCount':1})
        await until('!document.getElementById("start").disabled')
        await js('document.getElementById("enemy-select").value="kakube"')
        await shot('drawing')
        await js('document.getElementById("start").click()');await until('document.body?.dataset.screen==="battle"');await check_screen('battle')
        assert await js('document.activeElement.id!=="attack"'), 'phone keyboard auto-opened'
        for index,text in enumerate(['顔、食パンじゃん','目、四角っ','口、定規みたい']):
            await js('document.getElementById("attack").value='+json.dumps(text)+';document.getElementById("attack").dispatchEvent(new Event("input"));document.getElementById("attack-form").requestSubmit()')
            if index==0:
                await js('history.back()');await asyncio.sleep(.15)
                assert await js('document.body.dataset.screen==="battle" && history.state.faceScreen==="battle"'), 'left during attack'
            await until('document.getElementById("attack-panel").getAttribute("aria-busy")!=="true" && document.querySelectorAll("#log .log-entry").length==='+str((index+1)*2))
        await check_screen('result');assert await js('!document.getElementById("result").hidden')
        assert await js('document.querySelectorAll("#result-log .log-entry").length===6')
        assert await js('[...document.querySelectorAll("#result-log .log-entry p")].every(p=>p.textContent.length>10)')
        await js('document.getElementById("result-review").open=true')
        assert await js('document.getElementById("result-log").getBoundingClientRect().height>0')
        await shot('result-review')
        await js('document.getElementById("result-review").open=false')
        assert await js('document.getElementById("result-detail").textContent.includes("HP")')
        await shot('result')
        await js('document.getElementById("redraw").click()');await check_screen('draw')
        assert await js('!document.getElementById("start").disabled'), 'drawing lost after result'
        for width,height in [(320,640),(390,844),(800,1000),(1280,900)]:
            await call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<600})
            assert await js('document.documentElement.scrollWidth<=innerWidth'), width
        await js('document.getElementById("draw-back").click();document.getElementById("difficulty-back").click();document.getElementById("rules-back").click()');await check_screen('title')
        assert not errors,errors
        print('PASS: title -> rules -> difficulty -> drawing -> 3-round battle -> separate result; no player AI selector; browser back/forward; drawing retained; no automatic phone keyboard; 320-1280px; no JS exceptions')
        await call('Emulation.setTouchEmulationEnabled',{'enabled':False})

asyncio.run(main())
