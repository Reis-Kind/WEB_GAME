"""Test startup configuration in Chromium CDP; uses mocked model APIs, no inference."""
import asyncio
import json
from urllib.request import urlopen
import websockets

async def main():
    page = next(p for p in json.load(urlopen('http://127.0.0.1:9222/json')) if p['type'] == 'page')
    async with websockets.connect(page['webSocketDebuggerUrl']) as ws:
        number = 0
        async def call(method, params=None):
            nonlocal number
            number += 1
            await ws.send(json.dumps({'id': number, 'method': method, 'params': params or {}}))
            while True:
                result = json.loads(await ws.recv())
                if result.get('id') == number:
                    if 'error' in result: raise AssertionError(result['error'])
                    return result['result']
        async def js(code):
            result = await call('Runtime.evaluate', {'expression': code, 'returnByValue': True, 'awaitPromise': True})
            if 'exceptionDetails' in result: raise AssertionError(result['exceptionDetails'])
            return result['result'].get('value')
        async def ready():
            for _ in range(100):
                if await js('Boolean(document.getElementById("judge-mode")) && !document.getElementById("judge-mode").disabled'): return
                await asyncio.sleep(.1)
            raise AssertionError('startup timed out')
        await call('Page.enable')
        await call('Runtime.enable')
        await call('Emulation.setDeviceMetricsOverride', {'width':1280, 'height':1400, 'deviceScaleFactor':1, 'mobile':False})
        script_id = None
        for name, mode, ok, valid in [('local success', 'local', True, True), ('missing model', 'local', False, True), ('demo default', 'demo', True, True), ('config error', 'local', True, False)]:
            if script_id:
                await call('Page.removeScriptToEvaluateOnNewDocument', {'identifier': script_id})
            source = '''
            const originalFetch = window.fetch.bind(window);
            window.modelCalls = [];
            window.fetch = async (url, options) => {
              if (url === '/api/config') return new Response(JSON.stringify(CONFIG), {status: CONFIG_STATUS});
              if (url === '/api/model') {
                window.modelCalls.push(JSON.parse(options.body));
                await new Promise(r => setTimeout(r, 200));
                return new Response(JSON.stringify(MODEL), {status: MODEL_STATUS});
              }
              return originalFetch(url, options);
            };
            '''.replace('CONFIG_STATUS', '200' if valid else '500').replace('MODEL_STATUS', '200' if ok else '400').replace('CONFIG', json.dumps({'mode':mode, 'model':'configured-vision-test'})).replace('MODEL', json.dumps({'vision':True} if ok else {'error':'model missing'}))
            script_id = (await call('Page.addScriptToEvaluateOnNewDocument', {'source':source}))['identifier']
            await call('Page.navigate', {'url':'http://127.0.0.1:8001/'})
            await asyncio.sleep(.3)
            await ready()
            state = await js('({mode:document.getElementById("judge-mode").value,status:document.getElementById("connection-status").textContent,model:document.getElementById("model-select").value,calls:window.modelCalls})')
            expected_mode = mode if valid else 'demo'
            assert state['mode'] == expected_mode, (name, state)
            if mode == 'local' and valid:
                assert state['calls'] == [{'model':'configured-vision-test'}], state
                assert state['model'] == 'configured-vision-test', state
                if ok: assert '画像対応' in state['status'] and '接続済み' in state['status'], state
                else: assert 'model missing' in state['status'] and 'config.py' in state['status'], state
            else:
                assert not state['calls'], state
                assert 'デモ判定' in state['status'], state
            # Draw through real browser input to test start-gating after startup.
            rect = await js('(()=>{const r=document.getElementById("drawing").getBoundingClientRect();return {x:r.x+50,y:r.y+50}})()')
            for kind in ['mousePressed', 'mouseReleased']:
                await call('Input.dispatchMouseEvent', {'type':kind, 'x':rect['x'], 'y':rect['y'], 'button':'left', 'clickCount':1})
            disabled = await js('document.getElementById("start").disabled')
            assert disabled == (mode == 'local' and valid and not ok), (name, disabled)
            print('PASS:', name, state['status'], flush=True)
        await call('Page.removeScriptToEvaluateOnNewDocument', {'identifier':script_id})
        # Check that the running server also publishes the real program configuration.
        await call('Page.navigate', {'url':'http://127.0.0.1:8001/api/config'})
        await asyncio.sleep(.3)
        data = await js('JSON.parse(document.body.innerText)')
        assert data == {'mode':'local', 'model':'qwen3-vl:4b-instruct'}, data
        print('PASS: server config endpoint', data)

if __name__ == '__main__': asyncio.run(main())
