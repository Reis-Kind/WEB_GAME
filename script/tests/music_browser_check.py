"""BGM playback/levels/lifecycle checks through CDP, no AI calls."""
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
          const {musicBuffer,BackgroundMusic}=await import('/music.js');
          const {SoundEffects}=await import('/sound.js?v=2');
          const offline=new OfflineAudioContext(1,44100,44100),buffer=musicBuffer(offline),samples=buffer.getChannelData(0);
          let peak=0,energy=0;for(const s of samples){if(!Number.isFinite(s))throw Error('Invalid music');peak=Math.max(peak,Math.abs(s));energy+=s*s;}
          if(buffer.duration!==20||peak>.09||peak<.02||Math.sqrt(energy/samples.length)>.025)throw Error('Music level');
          if(Math.abs(samples[0]-samples[samples.length-1])>.001)throw Error('Loop click');
          localStorage.setItem('kao-bgm','on');localStorage.setItem('kao-sound','off');
          const effects=new SoundEffects(document.createElement('button')),button=document.createElement('button'),music=new BackgroundMusic(effects,button);
          if(effects.context||music.source)throw Error('Autoplay');
          await music.start();const source=music.source;
          if(!source||!source.loop||effects.enabled)throw Error('Music independent of muted effects');
          await music.start();if(music.source!==source)throw Error('Layered loops');
          button.click();if(music.source||localStorage.getItem('kao-bgm')!=='off')throw Error('Mute failed');
          button.click();await new Promise(r=>setTimeout(r,100));if(!music.source)throw Error('Restart failed');
          Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));
          if(music.source)throw Error('Background music did not stop');
          Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));
          await new Promise(r=>setTimeout(r,100));if(!music.source)throw Error('Visibility resume');
          delete document.hidden;music.stop();await effects.context.close();localStorage.setItem('kao-bgm','off');
          return {duration:buffer.duration,peak,rms:Math.sqrt(energy/samples.length)};
        })()''')
        print('PASS: quiet seamless buffer; first gesture, independent mute, no duplicate loops, restart',result)
        # The real global toggle reads the persisted mute choice after reload.
        await call('Page.reload');await asyncio.sleep(.6)
        assert await js('document.getElementById("music-toggle").getAttribute("aria-pressed")==="false"')
        for width in [320,390,1280]:
            await call('Emulation.setDeviceMetricsOverride',{'width':width,'height':844,'deviceScaleFactor':1,'mobile':width<600})
            assert await js('(()=>{const r=document.getElementById("music-toggle").getBoundingClientRect();return r.width>=39&&r.right<=innerWidth+1&&r.left>=0})()'), await js('(()=>{const r=document.getElementById("music-toggle").getBoundingClientRect();return {width:r.width,left:r.left,right:r.right,viewport:innerWidth}})()')
        print('PASS: actual mute toggle restored after reload; 320/390/1280px')

if __name__=='__main__':asyncio.run(main())
