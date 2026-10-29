"""2.5D UI QA. Requires server :8001 and Chromium CDP :9222; no AI calls."""
import asyncio
import base64
import json
import math
from urllib.request import urlopen
import websockets

async def main():
    page = next(p for p in json.load(urlopen('http://127.0.0.1:9222/json')) if p['type'] == 'page')
    async with websockets.connect(page['webSocketDebuggerUrl']) as ws:
        counter = 0
        errors = []
        async def call(method, params=None):
            nonlocal counter
            counter += 1
            await ws.send(json.dumps({'id': counter, 'method': method, 'params': params or {}}))
            while True:
                result = json.loads(await ws.recv())
                if result.get('method') == 'Runtime.exceptionThrown': errors.append(result)
                if result.get('id') == counter:
                    assert 'error' not in result, result
                    return result.get('result', {})
        async def js(code):
            result = await call('Runtime.evaluate', {'expression': code, 'returnByValue': True, 'awaitPromise': True})
            assert 'exceptionDetails' not in result, result
            return result.get('result', {}).get('value')
        async def until(code):
            for _ in range(150):
                if await js(code): return
                await asyncio.sleep(.05)
            raise AssertionError(code)
        async def screenshot(path):
            data = await call('Page.captureScreenshot', {'format':'png','captureBeyondViewport':False})
            with open(path, 'wb') as output: output.write(base64.b64decode(data['data']))
        await call('Page.enable')
        await call('Runtime.enable')
        await call('Network.enable')
        await call('Network.setCacheDisabled', {'cacheDisabled':True})
        await call('Emulation.setDeviceMetricsOverride', {'width':1280,'height':1100,'deviceScaleFactor':1,'mobile':False})
        fixture=await call('Page.addScriptToEvaluateOnNewDocument',{'source':"const originalFetch=window.fetch.bind(window);window.fetch=(url,options)=>url==='/api/config'?Promise.resolve(new Response(JSON.stringify({mode:'demo',model:'test'}))):originalFetch(url,options);"})
        await call('Page.navigate', {'url':'http://127.0.0.1:8001/'})
        await until('document.body?.dataset.judgeLoaded==="true"')
        await call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':fixture['identifier']})
        await js('document.getElementById("show-rules").click();document.getElementById("begin-drawing").click();document.getElementById("confirm-difficulty").click()')
        await asyncio.sleep(.3)
        rect = await js('(()=>{const r=document.getElementById("drawing").getBoundingClientRect();return {x:r.x,y:r.y,w:r.width}})()')
        assert await js('(()=>{const a=document.getElementById("drawing").getBoundingClientRect(),b=document.querySelector(".preview-card").getBoundingClientRect();return b.left>=a.right && b.top<a.bottom})()')

        async def stroke(points):
            for i,(x,y) in enumerate(points):
                await call('Input.dispatchMouseEvent', {'type':'mousePressed' if i==0 else 'mouseMoved', 'x':rect['x']+x*rect['w'],'y':rect['y']+y*rect['w'],'button':'left','buttons':1,'clickCount':1})
            await asyncio.sleep(.1)
            assert await js('!document.getElementById("preview-face").hidden && document.getElementById("preview-face").src.startsWith("data:image/png")'), 'preview during active stroke'
            x,y=points[-1]
            await call('Input.dispatchMouseEvent', {'type':'mouseReleased','x':rect['x']+x*rect['w'],'y':rect['y']+y*rect['w'],'button':'left','clickCount':1})
        await stroke([(.5+.33*math.cos(t*2*math.pi/50),.5+.36*math.sin(t*2*math.pi/50)) for t in range(51)])
        for x in (.38,.62): await stroke([(x,.42),(x,.45)])
        await stroke([(.5,.48),(.48,.56),(.52,.56)])
        await stroke([(.35+i*.3/20,.65+.08*math.sin(i*math.pi/20)) for i in range(21)])
        assert await js('!document.getElementById("preview-face").hidden && document.querySelector(".preview-empty").hidden')
        await screenshot('/tmp/kao-clay-drawing.png')
        await js('document.getElementById("clear").click()')
        await until('document.getElementById("preview-face").hidden && !document.getElementById("preview-face").closest(".clay-head").classList.contains("has-mesh")')
        assert await js('[...document.getElementById("preview-face").closest(".clay-head").querySelectorAll(".mesh-view")].every(c=>c.hidden)')
        await js('document.getElementById("undo").click()')
        await until('!document.getElementById("preview-face").hidden && document.getElementById("preview-face").complete')
        print('PASS: clear hides old 3D mesh and undo restores the source image')

        for width in (320,390,800):
            await call('Emulation.setDeviceMetricsOverride', {'width':width,'height':950,'deviceScaleFactor':1,'mobile':width<600})
            assert await js('document.documentElement.scrollWidth<=innerWidth')
            assert await js('(()=>{const a=document.getElementById("drawing").getBoundingClientRect(),b=document.querySelector(".preview-card").getBoundingClientRect();return b.left>=a.right && b.top<a.bottom})()')
        await call('Emulation.setDeviceMetricsOverride', {'width':1280,'height':1100,'deviceScaleFactor':1,'mobile':False})
        print('PASS: live preview during strokes, side-by-side at 320/390/800/1280px')

        await js('document.getElementById("enemy-select").value="higemochi";document.getElementById("start").click()')
        await until('!document.getElementById("battle-screen").hidden && document.getElementById("player-face").complete')
        await js('document.activeElement.blur();window.scrollTo(0,document.getElementById("battle-screen").getBoundingClientRect().top+scrollY-15)')
        await asyncio.sleep(.35)
        assert await js('document.querySelectorAll(".fighter .clay-head img").length===2')
        assert await js('document.getElementById("difficulty").value==="easy"')
        assert await js('(()=>{const c=document.createElement("canvas");c.width=c.height=640;const x=c.getContext("2d");x.fillStyle="#fff";x.fillRect(0,0,640,640);x.drawImage(document.getElementById("drawing"),0,0);return c.toDataURL()===document.getElementById("player-face").src})()')
        await screenshot('/tmp/kao-clay-desktop.png')
        print('PASS: drawing preview, clay faces, original PNG unchanged, easy default')
        assert await js('(async()=>{const {ENEMIES}=await import("/enemies.js");const images=new Set();for(const e of ENEMIES){const i=new Image();i.src=e.image;await i.decode();const c=document.createElement("canvas");c.width=c.height=384;c.getContext("2d").drawImage(i,0,0,384,384);images.add(c.toDataURL());}return images.size===6})()')
        print('PASS: all six CPU face assets load and rasterize as distinct images')

        await js('document.getElementById("attack").value="そのひげ、ぜんまいみたい！";document.getElementById("attack").dispatchEvent(new Event("input"));document.getElementById("attack-form").requestSubmit()')
        await until('!document.getElementById("attack-cutin").hidden && document.getElementById("attack-cutin").dataset.actor==="player"')
        assert await js('document.getElementById("player-bar").value===100 && document.getElementById("cpu-bar").value===100 && document.getElementById("submit").disabled')
        assert await js('document.getElementById("cutin-face").src===document.getElementById("player-face").src && document.getElementById("cutin-text").textContent.includes("ひげ")')
        await asyncio.sleep(.3)
        await screenshot('/tmp/kao-cutin-player.png')
        await until('document.getElementById("cpu-card").classList.contains("hit")')
        assert await js('document.getElementById("attack-cutin").hidden && document.getElementById("cpu-bar").value<100 && document.getElementById("player-bar").value===100')
        await asyncio.sleep(.2)
        await screenshot('/tmp/kao-cutin-damage.png')
        await until('!document.getElementById("attack-cutin").hidden && document.getElementById("attack-cutin").dataset.actor==="cpu"')
        assert await js('document.getElementById("player-bar").value===100 && document.getElementById("cutin-face").src===document.getElementById("cpu-face").src')
        await until('document.getElementById("player-card").classList.contains("hit")')
        assert await js('document.getElementById("attack-cutin").hidden && document.getElementById("player-bar").value<100')
        print('PASS: player cut-in -> enemy damage -> CPU cut-in -> player damage, input locked')
        await until('document.getElementById("attack-panel").getAttribute("aria-busy")!=="true" && document.querySelectorAll("#log .log-entry").length===2')
        assert await js('document.getElementById("player-bubble").textContent===document.querySelectorAll("#log .log-entry blockquote")[0].textContent && document.getElementById("cpu-bubble").textContent===document.querySelectorAll("#log .log-entry blockquote")[1].textContent')
        print('PASS: demo round, bubbles match log, animation classes cleaned up')
        for width in (320,390,600,800,1280):
            await call('Emulation.setDeviceMetricsOverride', {'width':width,'height':1000,'deviceScaleFactor':1,'mobile':width<600})
            await js('window.scrollTo(0,document.getElementById("battle-screen").getBoundingClientRect().top+scrollY-15)')
            await asyncio.sleep(.15)
            assert await js('document.documentElement.scrollWidth<=innerWidth'), f'overflow {width}'
            if width==390: await screenshot('/tmp/kao-clay-mobile.png')
        assert await js('[".site-header",".intro",".steps",".battle-top",".fighter-title",".hp-info",".log-panel",".battle-note",".input-meta","#judge-time"].every(s=>[...document.querySelectorAll(s)].every(e=>getComputedStyle(e).display==="none"))')
        assert await js('[...document.querySelectorAll(".fighter progress")].every(e=>getComputedStyle(e).display==="block" && e.getBoundingClientRect().height>0)')
        print('PASS: 320/390/600/800/1280px, no overflow, HP bars visible, auxiliary text hidden')
        await call('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
        assert await js('[...document.querySelectorAll(".clay-float")].every(e=>getComputedStyle(e).animationName==="none")')
        await call('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        await js('document.getElementById("cutin-text").textContent="そのひげ、ぜんまいみたい！".repeat(6);document.getElementById("attack-cutin").hidden=false')
        await screenshot('/tmp/kao-cutin-mobile.png')
        assert await js('document.documentElement.scrollWidth<=innerWidth && document.getElementById("cutin-text").scrollWidth<=document.getElementById("cutin-text").clientWidth')
        await js('document.getElementById("attack-cutin").hidden=true')
        print('PASS: reduced motion, long cut-in text on mobile; no JavaScript exceptions')
        assert not errors, errors
        await call('Emulation.setEmulatedMedia', {'features':[]})

asyncio.run(main())
