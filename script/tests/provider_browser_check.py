"""Fixed-provider UI QA; config/status/round endpoints are mocked, no inference."""
import asyncio,json
from urllib.request import urlopen
import websockets

async def run_provider(mode):
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
        await call('Page.enable');await call('Runtime.enable');await call('Network.enable')
        await call('Network.setCacheDisabled',{'cacheDisabled':True})
        await call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        script=None
        for configured in (False,True):
            if script:await call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':script})
            source='''const originalFetch=window.fetch.bind(window);window.roundCalls=[];window.failRound=true;
            window.fetch=async(url,options)=>{
              if(url==='/api/config')return new Response(JSON.stringify({mode:MODE,model:'mock-local'}));
              if(url==='/api/'+MODE+'/status')return new Response(JSON.stringify({configured:READY,model:'mock-'+MODE}));
              if(url==='/api/'+MODE+'/round'){
                window.roundCalls.push(JSON.parse(options.body));
                if(window.failRound)return new Response(JSON.stringify({error:'利用上限テスト'}),{status:429});
                return new Response(JSON.stringify({player:{damage:23,reason:'短い的確な一言'},cpu:{text:'その目、お豆みたい！',score:{damage:24,reason:'反撃'}},mode:MODE}));
              }
              if(url.startsWith('/api/'))throw new Error('Unexpected provider '+url);
              return originalFetch(url,options);
            };'''.replace('MODE',json.dumps(mode)).replace('READY',str(configured).lower())
            script=(await call('Page.addScriptToEvaluateOnNewDocument',{'source':source}))['identifier']
            await call('Page.navigate',{'url':'http://127.0.0.1:8001/'})
            await until('document.body?.dataset.judgeLoaded==="true"')
            assert await js('!document.querySelector("#judge-mode,#open-settings")')
            assert await js('document.body.dataset.judgeReady')==str(configured).lower()
            await js('document.getElementById("show-rules").click();document.getElementById("begin-drawing").click();document.getElementById("confirm-difficulty").click()')
            point=await js('(()=>{const r=document.getElementById("drawing").getBoundingClientRect();return{x:r.x+45,y:r.y+45}})()')
            for kind in ('mousePressed','mouseReleased'):await call('Input.dispatchMouseEvent',{'type':kind,**point,'button':'left','clickCount':1})
            assert await js('document.getElementById("start").disabled') is not configured
            if not configured:
                assert await js('document.getElementById("connection-status").textContent.includes("準備ができません")')
                continue
            await js('document.getElementById("start").click()');await until('document.body.dataset.screen==="battle"')
            async def attack():await js('document.getElementById("attack").value="目、豆じゃん";document.getElementById("attack").dispatchEvent(new Event("input"));document.getElementById("attack-form").requestSubmit();document.getElementById("attack-form").requestSubmit()')
            await attack();await until('document.getElementById("battle-error").textContent.includes("利用上限")')
            assert await js('document.getElementById("player-bar").value===100 && document.getElementById("cpu-bar").value===100 && roundCalls.length===1')
            await js('window.failRound=false')
            for index in range(3):
                await attack();await until('document.getElementById("attack-panel").getAttribute("aria-busy")!=="true" && document.querySelectorAll("#log .log-entry").length==='+str((index+1)*2))
            assert await js('document.body.dataset.screen==="result" && document.getElementById("player-bar").value===58 && document.getElementById("cpu-bar").value===31 && roundCalls.length===4')
            assert await js('roundCalls[3].playerHistory.length===2 && roundCalls.every(c=>c.playerImage.startsWith("data:image/png")&&c.cpuImage.startsWith("data:image/png")&&!c.apiKey)')
            assert await js('document.documentElement.scrollWidth<=innerWidth')
            await js('document.getElementById("rematch").click()');await until('document.body.dataset.screen==="battle"')
            assert await js('document.getElementById("player-bar").value===100 && document.querySelectorAll("#log .log-entry").length===0')
        await call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':script})
        assert not errors,errors
        print('PASS:',mode,'operator config, missing key blocks start, no player selector, error retry, double-submit lock, 3 rounds, separate result, original images, rematch; no real AI calls')
