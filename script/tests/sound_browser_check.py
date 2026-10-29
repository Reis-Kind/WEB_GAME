"""Web Audio checks through CDP; synthesizes into offline buffers, no AI calls."""
import asyncio,json
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
            r=await call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True,'userGesture':True})
            assert 'exceptionDetails' not in r,r
            return r['result'].get('value')
        await call('Page.enable');await call('Page.navigate',{'url':'http://127.0.0.1:8001/'})
        await asyncio.sleep(.8)
        result=await js('''(async()=>{
          const {scheduleSound,SoundEffects}=await import('/sound.js');
          const rendered=[];
          for(const kind of ['tap','cutin','hit','win','lose','draw']){
            const ctx=new OfflineAudioContext(1,44100,44100);
            scheduleSound(ctx,ctx.destination,kind,25);
            const samples=(await ctx.startRendering()).getChannelData(0);
            let peak=0,energy=0;for(const s of samples){if(!Number.isFinite(s))throw Error('Invalid sample');peak=Math.max(peak,Math.abs(s));energy+=s*s;}
            if(peak<.005||peak>.5||energy<=0)throw Error('Silent or clipped '+kind);
            if(samples.slice(35000).some(s=>Math.abs(s)>.0001))throw Error('Effect did not stop');
            rendered.push({kind,peak});
          }
          localStorage.setItem('kao-sound','on');
          const button=document.createElement('button'),audio=new SoundEffects(button);
          if(audio.context)throw Error('Autoplay before gesture');
          await audio.unlock();
          if(!await audio.play('hit',0))throw Error('No zero-damage sound');
          button.click();if(audio.enabled||audio.master.gain.value!==0||await audio.play('win'))throw Error('Mute failed');
          if(localStorage.getItem('kao-sound')!=='off'||button.getAttribute('aria-pressed')!=='false')throw Error('Mute persistence');
          const unavailable=window.AudioContext;window.AudioContext=undefined;
          const legacy=window.webkitAudioContext;window.webkitAudioContext=undefined;
          const b=document.createElement('button'),unsupported=new SoundEffects(b);unsupported.enabled=true;await unsupported.unlock();
          if(await unsupported.play('hit',20))throw Error('Unsupported audio fallback');
          window.AudioContext=unavailable;window.webkitAudioContext=legacy;
          await audio.context.close();
          const backing=new OfflineAudioContext(1,44100,44100);let count=0;
          audio.enabled=true;audio.context={state:'suspended',currentTime:0,destination:backing.destination,
            createGain:()=>backing.createGain(),createOscillator:()=>{count++;return backing.createOscillator()},
            resume:()=>new Promise(resolve=>setTimeout(()=>{audio.context.state='running';resolve()},80))};
          audio.master=backing.createGain();audio.master.connect(backing.destination);
          if(!await audio.play('tap')||count!==1)throw Error('First sound lost during resume');
          audio.context.state='interrupted';if(!await audio.play('tap')||count!==2)throw Error('Interrupted resume failed');
          audio.enabled=false;audio.update();localStorage.setItem('kao-sound','off');
          return rendered;
        })()''')
        print('PASS: offline effects produce finite, audible-level, unclipped, bounded waveforms',json.dumps(result))
        print('PASS: no automatic AudioContext, mute and persistence, zero-damage sound, unsupported audio fallback')
        # The real global toggle reads the persisted mute choice after reload.
        await call('Page.reload');await asyncio.sleep(.6)
        assert await js('document.getElementById("sound-toggle").getAttribute("aria-pressed")==="false"')
        for width in [320,390,1280]:
            await call('Emulation.setDeviceMetricsOverride',{'width':width,'height':844,'deviceScaleFactor':1,'mobile':width<600})
            assert await js('(()=>{const r=document.getElementById("sound-toggle").getBoundingClientRect();return r.width>=40&&r.right<=innerWidth&&r.left>=0})()')
        print('PASS: actual mute toggle restored after reload; 320/390/1280px')
        await js('document.getElementById("sound-test").click()')
        await asyncio.sleep(.3)
        assert await js('document.getElementById("sound-feedback").textContent.includes("テスト音を再生しました") && document.getElementById("sound-toggle").getAttribute("aria-pressed")==="true"')
        print('PASS: suspended and interrupted resumes retain first sound; test sound button enables audio')

if __name__=='__main__':asyncio.run(main())
