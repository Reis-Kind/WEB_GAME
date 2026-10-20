"""Headless Chromium/Brave CDP check. Requires Python websockets for QA only.
Start a browser with --remote-debugging-port=9222 and python3 server.py --port 8001.
"""
import asyncio
import base64
import json
from pathlib import Path
from urllib.request import urlopen
import websockets

async def main():
    pages = json.load(urlopen('http://127.0.0.1:9222/json'))
    page = next(p for p in pages if p['type'] == 'page')
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10_000_000) as ws:
        counter = 0
        errors = []
        async def call(method, params=None):
            nonlocal counter
            counter += 1
            number = counter
            await ws.send(json.dumps({'id':number, 'method':method, 'params':params or {}}))
            while True:
                result = json.loads(await ws.recv())
                if result.get('method') == 'Runtime.exceptionThrown': errors.append(result)
                if result.get('id') == number:
                    if 'error' in result: raise RuntimeError(result['error'])
                    return result.get('result', {})
        async def js(expression):
            result = await call('Runtime.evaluate', {'expression':expression, 'returnByValue':True, 'awaitPromise':True})
            if result.get('exceptionDetails'): raise RuntimeError(result['exceptionDetails'])
            return result.get('result', {}).get('value')
        async def until(expression, seconds=15):
            for _ in range(seconds * 5):
                if await js(expression): return
                await asyncio.sleep(.2)
            raise AssertionError('Timed out: ' + expression)
        def check(condition, name):
            if not condition: raise AssertionError(name)
            print('PASS:', name, flush=True)
        async def click(selector):
            await js(f'document.querySelector({json.dumps(selector)}).click()')
        async def screenshot(path):
            data = await call('Page.captureScreenshot', {'format':'png', 'captureBeyondViewport':True})
            Path(path).write_bytes(base64.b64decode(data['data']))
        await call('Runtime.enable')
        await call('Page.enable')
        await call('Emulation.setDeviceMetricsOverride', {'width':1280,'height':1000,'deviceScaleFactor':1,'mobile':False})
        await call('Page.navigate', {'url':'http://127.0.0.1:8001/tests/index.html'})
        await until('Boolean(window.testResults)')
        results = await js('window.testResults')
        for result in results: check(result['pass'], result['name'] + str(result.get('error','')))
        await call('Page.navigate', {'url':'http://127.0.0.1:8001/'})
        await until('Boolean(document.getElementById("colors")?.children.length)')
        await until('!document.getElementById("judge-mode").disabled', 140)
        await js('document.getElementById("judge-mode").value="demo";document.getElementById("judge-mode").dispatchEvent(new Event("change"))')
        check(await js('document.getElementById("start").disabled'), '白紙では開始できない')
        # Actual browser input, including pointer capture and scaled canvas coordinates.
        rect = await js('(()=>{const r=document.getElementById("drawing").getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}})()')
        x,y = rect['x'] + rect['width']*.3, rect['y'] + rect['height']*.4
        await call('Input.dispatchMouseEvent', {'type':'mousePressed','x':x,'y':y,'button':'left','clickCount':1})
        await call('Input.dispatchMouseEvent', {'type':'mouseMoved','x':x+70,'y':y+50,'button':'left','buttons':1})
        await call('Input.dispatchMouseEvent', {'type':'mouseReleased','x':x+70,'y':y+50,'button':'left','clickCount':1})
        check(await js('!document.getElementById("start").disabled'), '実マウス描画で開始可能')
        await screenshot('/tmp/kao-desktop.png')
        await click('#clear'); check(await js('document.getElementById("start").disabled'), '全消去で開始不可')
        await click('#undo'); check(await js('!document.getElementById("start").disabled'), '全消去を元に戻せる')
        await click('#start'); await until('!document.getElementById("battle-screen").hidden')
        check(await js('document.getElementById("player-face").src.startsWith("data:image/png;base64,")'), '描いた顔を対戦中も表示')
        for number, text in enumerate(['その眉毛、海苔が会議してるみたい！','その鼻、滑走路みたい！','その目、信号みたい！'],1):
            await js(f'(()=>{{const a=document.getElementById("attack");a.value={json.dumps(text)};a.dispatchEvent(new Event("input"));document.getElementById("attack-form").requestSubmit();document.getElementById("attack-form").requestSubmit();}})()')
            check(await js('document.getElementById("submit").disabled'), '送信中ロック')
            await until(f'document.querySelectorAll(".log-entry").length === {number*2} && document.getElementById("turn-status").textContent !== "CPUの番"')
        check(await js('!document.getElementById("result").hidden && document.querySelectorAll(".log-entry").length === 6'), '3回ずつで決着・二重送信なし')
        await screenshot('/tmp/kao-result.png')
        await click('#rematch'); check(await js('document.getElementById("player-bar").value===100 && document.querySelectorAll(".log-entry").length===0'), '再戦でHP・履歴リセット')
        # Complete another round then navigate back via end screen.
        for _ in range(3):
            await js('(()=>{const a=document.getElementById("attack");a.value="眉毛が海苔みたい";a.dispatchEvent(new Event("input"));document.getElementById("attack-form").requestSubmit()})()')
            await until('!document.getElementById("attack").disabled')
        await click('#redraw')
        check(await js('!document.getElementById("draw-screen").hidden && !document.getElementById("start").disabled'), '顔を残して描き直し画面へ戻る')
        await call('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        await call('Emulation.setTouchEmulationEnabled', {'enabled':True, 'maxTouchPoints':5})
        await js('window.scrollTo(0,0)')
        check(await js('document.documentElement.scrollWidth <= innerWidth'), 'スマホ幅で横スクロールなし')
        rect = await js('(()=>{const r=document.getElementById("drawing").getBoundingClientRect();return {x:r.x+30,y:r.y+30}})()')
        await call('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':rect['x'],'y':rect['y']}]})
        await call('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':rect['x']+50,'y':rect['y']+30}]})
        await call('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
        check(await js('!document.getElementById("undo").disabled && !document.getElementById("start").disabled'), 'タッチ入力の描画完了')
        await screenshot('/tmp/kao-mobile.png')
        # Local LLM: connect to an actually installed model, then play one full round.
        await js('document.getElementById("judge-mode").value="local";document.getElementById("judge-mode").dispatchEvent(new Event("change"))')
        check(await js('document.getElementById("start").disabled'), 'LLM未接続では開始不可')
        await click('#load-models'); await until('!document.getElementById("load-models").disabled')
        models = await js('Array.from(document.getElementById("model-select").options).map(o=>o.value)')
        print('Available models:', models, flush=True)
        if 'qwen2.5:7b' in models:
            await js('document.getElementById("model-select").value="qwen2.5:7b"')
        await click('#connect-model'); await until('!document.getElementById("connect-model").disabled',30)
        check(await js('document.getElementById("connection-status").textContent.includes("接続済み")'), '実Ollamaモデル接続')
        await click('#start')
        await js('(()=>{const a=document.getElementById("attack");a.value="その眉毛、海苔が会議してるみたい！";a.dispatchEvent(new Event("input"));document.getElementById("attack-form").requestSubmit()})()')
        await until('!document.getElementById("attack").disabled', 300)
        check(await js('document.querySelectorAll(".log-entry").length===2'), '実LLMで採点・CPU返答・反撃採点・HP更新')
        print('LLM log:', await js('document.getElementById("log").textContent'), flush=True)
        check(await js('document.documentElement.scrollWidth <= innerWidth'), 'スマホ対戦画面で横スクロールなし')
        await screenshot('/tmp/kao-llm-mobile.png')
        check(not errors, 'ブラウザJavaScript例外なし')
        print('ALL BROWSER CHECKS PASSED', flush=True)

if __name__ == '__main__': asyncio.run(main())
