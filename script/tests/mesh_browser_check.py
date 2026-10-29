"""Contour/mesh checks through CDP; no external AI calls."""
import asyncio
import base64
import json
from urllib.request import urlopen
import websockets

async def main():
    page=next(p for p in json.load(urlopen('http://127.0.0.1:9222/json')) if p['type']=='page')
    async with websockets.connect(page['webSocketDebuggerUrl']) as ws:
        number=0
        async def call(method,params=None):
            nonlocal number
            number+=1
            await ws.send(json.dumps({'id':number,'method':method,'params':params or {}}))
            while True:
                response=json.loads(await ws.recv())
                if response.get('id')==number:
                    assert 'error' not in response,response
                    return response.get('result',{})
        async def js(code):
            result=await call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
            assert 'exceptionDetails' not in result,result
            return result['result'].get('value')
        await call('Page.enable')
        await call('Network.enable')
        await call('Network.setCacheDisabled', {'cacheDisabled':True})
        await call('Emulation.setDeviceMetricsOverride', {'width':1100,'height':850,'deviceScaleFactor':1,'mobile':False})
        await call('Page.navigate', {'url':'http://127.0.0.1:8001/'})
        await asyncio.sleep(.6)
        result=await js('''(async()=>{
          const {contourFromImage,buildFaceGeometry,FaceMesh}=await import('/face-mesh.js');
          const make=(kind)=>{const c=document.createElement('canvas');c.width=c.height=640;const x=c.getContext('2d');x.lineWidth=10;x.strokeStyle='#292d36';x.beginPath();
            if(kind==='wide')x.ellipse(320,320,245,150,0,0,Math.PI*2);
            if(kind==='tall')x.ellipse(320,320,140,245,0,0,Math.PI*2);
            if(kind==='square')x.rect(135,135,370,370);
            if(kind==='open'){x.moveTo(150,100);x.lineTo(150,500);x.lineTo(500,500);}
            if(kind!=='blank')x.stroke();return c;};
          const results={};
          for(const kind of ['wide','tall','square','open','blank']){
            const contour=contourFromImage(make(kind)),mesh=buildFaceGeometry(contour);
            if(contour.detected!==['wide','tall','square'].includes(kind))throw Error('Detection '+kind);
            if(!mesh.positions.every(Number.isFinite)||!mesh.normals.every(Number.isFinite))throw Error('Nonfinite mesh');
            if(!mesh.indices.every(i=>i<mesh.positions.length/3))throw Error('Bad mesh indices');
            if(Math.max(...mesh.positions.filter((_,i)=>i%3===2))<.4)throw Error('No front depth');
            if(Math.min(...mesh.positions.filter((_,i)=>i%3===2))>-.4)throw Error('No back depth');
            results[kind]={detected:contour.detected,ratio:contour.width/contour.height,triangles:mesh.indices.length/3};
          }
          if(results.wide.ratio<1.4||results.tall.ratio>.8)throw Error('Aspect lost');

          const original=HTMLCanvasElement.prototype.getContext;
          const fallbackHead=document.createElement('div');fallbackHead.className='clay-head';const fallbackImage=new Image();fallbackHead.append(fallbackImage);
          try{HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl'?null:original.call(this,type,...args)};
            const fallback=new FaceMesh(fallbackImage);fallbackImage.src=make('wide').toDataURL();await fallbackImage.decode();await new Promise(r=>setTimeout(r,50));
            if(fallback.available||!fallbackHead.classList.contains('has-mesh')||fallbackHead.dataset.contour!=='drawn')throw Error('No contour fallback');
            const ctx=fallback.canvas.getContext('2d'),pixels=ctx.getImageData(0,0,512,512).data;let minX=512,maxX=0,minY=512,maxY=0;
            for(let y=0;y<512;y++)for(let x=0;x<512;x++)if(pixels[(y*512+x)*4+3]>128){minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);}
            if((maxX-minX)/(maxY-minY)<1.4)throw Error('Fallback clay became round');
            fallbackImage.hidden=true;await new Promise(r=>setTimeout(r,20));if(!fallback.canvas.hidden)throw Error('Fallback clear');
          }finally{HTMLCanvasElement.prototype.getContext=original;}
          results.fallback='drawn clay silhouette without WebGL; clear passed';
          const {ENEMIES}=await import('/enemies.js');
          results.enemies=[];
          for(const enemy of ENEMIES){const image=new Image();image.src=enemy.image;await image.decode();const c=contourFromImage(image);if(!c.detected)throw Error('CPU outline '+enemy.id);const g=buildFaceGeometry(c);if(g.positions.some((v,i)=>i%3!==2&&Math.abs(v)>.91))throw Error('CPU clipped '+enemy.id);const xs=[],ys=[];g.positions.forEach((v,i)=>{if(i%3===0)xs.push(v);if(i%3===1)ys.push(v)});const meshRatio=(Math.max(...xs)-Math.min(...xs))/(Math.max(...ys)-Math.min(...ys));if(Math.abs(meshRatio-c.width/c.height)>.12)throw Error('Clay shape does not match outline '+enemy.id);results.enemies.push({id:enemy.id,ratio:c.width/c.height,meshRatio});}
          // Show shape comparisons on a temporary QA-only strip.
          const strip=document.createElement('div');strip.id='mesh-test-strip';strip.style='position:fixed;inset:0;z-index:200;background:#f4f0e7;display:flex;align-items:center;justify-content:center;gap:25px';document.body.append(strip);
          for(const kind of ['wide','tall','square']){const h=document.createElement('div');h.className='clay-head';h.style='width:240px;height:240px';const i=new Image();h.append(i);strip.append(h);const v=new FaceMesh(i);i.src=make(kind).toDataURL();await i.decode();await new Promise(r=>setTimeout(r,100));if(!h.classList.contains('has-mesh'))throw Error('WebGL unavailable');
            if(kind==='wide'){
              const loss=v.gl.getExtension('WEBGL_lose_context');
              if(loss){loss.loseContext();await new Promise(r=>setTimeout(r,100));if(h.classList.contains('has-mesh')||!v.canvas.hidden)throw Error('Lost-context fallback');loss.restoreContext();for(let n=0;n<30&&!h.classList.contains('has-mesh');n++)await new Promise(r=>setTimeout(r,50));if(!h.classList.contains('has-mesh'))throw Error('Context restore');results.context='fallback and restoration passed';}
            }
          }
          return results;
        })()''')
        print(json.dumps(result,ensure_ascii=False))
        await asyncio.sleep(.3)
        shot=await call('Page.captureScreenshot',{'format':'png'})
        with open('/tmp/kao-mesh-shapes.png','wb') as out:out.write(base64.b64decode(shot['data']))
        await js('document.getElementById("mesh-test-strip").remove()')
        print('PASS: outline detection, aspect ratios, closed front/back meshes, six CPU contours, WebGL rendering')

asyncio.run(main())
