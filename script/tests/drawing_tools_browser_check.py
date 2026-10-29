"""Drawing unit checks plus real touch UI interactions; no AI requests."""
import asyncio,base64,json
from urllib.request import urlopen
import websockets
async def main():
    page=next(p for p in json.load(urlopen('http://127.0.0.1:9222/json')) if p['type']=='page')
    async with websockets.connect(page['webSocketDebuggerUrl']) as ws:
        n=0
        async def call(method,params=None):
            nonlocal n
            n+=1;await ws.send(json.dumps({'id':n,'method':method,'params':params or {}}))
            while True:
                r=json.loads(await ws.recv())
                if r.get('id')==n:
                    assert 'error' not in r,r
                    return r.get('result',{})
        async def js(code):
            r=await call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
            assert 'exceptionDetails' not in r,r
            return r['result'].get('value')
        async def until(code):
            for _ in range(100):
                if await js(code):return
                await asyncio.sleep(.1)
            raise AssertionError(code)
        async def click(id):await js(f'document.getElementById({json.dumps(id)}).click()')
        await call('Page.enable');await call('Page.navigate',{'url':'http://127.0.0.1:8001/tests/index.html'})
        await until('Array.isArray(window.testResults)')
        results=await js('window.testResults');assert all(item['pass'] for item in results),results
        print('PASS:',len(results),'browser core tests including bucket boundaries, undo, eraser, white blank, shapes')
        await call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        await call('Emulation.setTouchEmulationEnabled',{'enabled':True})
        await call('Page.navigate',{'url':'http://127.0.0.1:8001/'})
        await until('document.body.dataset.judgeReady==="true"')
        for id in ['show-rules','begin-drawing','confirm-difficulty','circle']:await click(id)
        rect=await js('(()=>{const r=document.getElementById("drawing").getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()')
        async def touch(kind,x=0,y=0):
            points=[] if kind=='touchEnd' else [{'x':rect['x']+x*rect['w'],'y':rect['y']+y*rect['h'],'id':1}]
            await call('Input.dispatchTouchEvent',{'type':kind,'touchPoints':points})
        await touch('touchStart',.2,.2);await touch('touchMove',.75,.8);await touch('touchEnd')
        await click('bucket')
        await js('document.getElementById("custom-color").value="#f96840";document.getElementById("custom-color").dispatchEvent(new Event("input"))')
        assert await js('document.getElementById("bucket").getAttribute("aria-pressed")==="true"')
        await touch('touchStart',.475,.5);await touch('touchEnd')
        pixel='Array.from(document.getElementById("drawing").getContext("2d").getImageData(304,320,1,1).data)'
        assert all(abs(actual-expected)<=2 for actual,expected in zip(await js(pixel),[249,104,64,255]))
        assert await js('document.getElementById("preview-face").src.startsWith("data:image/png")')
        await until('document.getElementById("preview-face").closest(".clay-head").dataset.contour==="drawn"')
        shot=await call('Page.captureScreenshot',{'format':'png'});open('/tmp/kao-drawing-filled.png','wb').write(base64.b64decode(shot['data']))
        await click('picker');await touch('touchStart',.475,.5);await touch('touchEnd')
        assert await js('document.getElementById("pen").getAttribute("aria-pressed")==="true" && [249,104,64].every((v,i)=>Math.abs(v-parseInt(document.getElementById("custom-color").value.slice(1+i*2,3+i*2),16))<=2)')
        await click('undo');assert (await js(pixel))[3]==0
        for width in [320,390,800,1280]:
            await call('Emulation.setDeviceMetricsOverride',{'width':width,'height':844,'deviceScaleFactor':1,'mobile':width<600})
            assert await js('document.documentElement.scrollWidth<=innerWidth'),width
        await call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        shot=await call('Page.captureScreenshot',{'format':'png'});open('/tmp/kao-drawing-tools.png','wb').write(base64.b64decode(shot['data']))
        print('PASS: real touch ellipse/bucket/eyedropper, color keeps bucket selected, undo, preview, 320–1280px')
if __name__=='__main__':asyncio.run(main())
