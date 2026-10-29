"""Skill and mobility regression checks. Requires websockets and a headless browser CDP.
Run game server --port 8002 and browser --remote-debugging-port=9223 first.
"""
import asyncio
import base64
import json
from urllib.request import urlopen
import websockets


async def main():
    page = next(p for p in json.load(urlopen('http://localhost:9223/json')) if p['type'] == 'page')
    async with websockets.connect(page['webSocketDebuggerUrl']) as ws:
        sequence = 0
        errors = []

        async def call(method, params=None):
            nonlocal sequence
            sequence += 1
            await ws.send(json.dumps({'id': sequence, 'method': method, 'params': params or {}}))
            while True:
                result = json.loads(await ws.recv())
                if result.get('method') == 'Runtime.exceptionThrown':
                    errors.append(result)
                if result.get('id') == sequence:
                    assert 'error' not in result, result
                    return result.get('result', {})

        async def js(source):
            result = await call('Runtime.evaluate', {'expression': source, 'returnByValue': True, 'awaitPromise': True, 'userGesture': True})
            assert 'exceptionDetails' not in result, result
            return result['result'].get('value')

        await call('Runtime.enable')
        await call('Page.enable')
        fixture = await call('Page.addScriptToEvaluateOnNewDocument', {'source': 'window.requestAnimationFrame=()=>0;'})
        await call('Emulation.setDeviceMetricsOverride', {'width': 1280, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
        await call('Page.navigate', {'url': 'http://localhost:8002/'})
        await asyncio.sleep(1)
        result = await js('''(async()=>{
 const assert=(b,m)=>{if(!b)throw new Error(m)},A=CushionAbilities,P=CushionPhysics;
 let seed=7;const rng=()=>((seed=(seed*1664525+1013904223)>>>0)/4294967296);
 const stroke=[{x:200,y:100},{x:160,y:112},{x:100,y:105},{x:30,y:100}];
 const normalized=P.drawingShape(stroke,.01);
 const shifted=P.drawingShape(stroke.map(p=>({x:p.x+230,y:p.y+50})),.01);
 assert(JSON.stringify(normalized)===JSON.stringify(shifted),'canvas location changed weapon');
 for(const source of [stroke,[...stroke].reverse(),[{x:20,y:250},{x:25,y:180},{x:20,y:30}]]){
  const mesh=P.drawingShape(source,.01);
  assert(mesh.every(p=>p.z>=0)&&mesh.some(p=>p.x===0&&p.z===0),'weapon behind body or detached');
 }
 const dense=Array.from({length:160},(_,i)=>({x:Math.abs(i-71),y:100}));
 assert(P.drawingShape(dense,.01).some(p=>p.x===0&&p.z===0),'downsampling lost root');
 const zig=[{x:10,y:50},{x:80,y:50},{x:80,y:120},{x:140,y:120},{x:140,y:40},{x:210,y:40}];
 assert(P.drawingShape(zig,.01).length===zig.length,'corners simplified away');
 const ring=Array.from({length:101},(_,i)=>({x:140+100*Math.cos(i/100*Math.PI*2),y:140+100*Math.sin(i/100*Math.PI*2)}));
 const ringShape=P.drawingShape(ring,.01),mesh=P.tubeMesh(ringShape,.08);
 assert(ringShape.length>20&&ringShape.length<=128,'round outline lost');
 assert(mesh.length>0&&mesh.every(f=>f.points.every(p=>Number.isFinite(p.x+p.y+p.z))),'invalid tube mesh');
 const capped=P.tubeMesh([{x:0,y:0,z:0},{x:0,y:0,z:2}],.4).flatMap(f=>f.points);
 assert(Math.abs(Math.min(...capped.map(p=>p.z))+.4)<1e-6&&Math.abs(Math.max(...capped.map(p=>p.z))-2.4)<1e-6,'hemisphere tips missing');
 assert(capped.every(p=>Number.isFinite(p.x+p.y+p.z)&&Math.hypot(p.x,p.y)<=.400001),'rounded end geometry invalid');
 const p=A.init({x:-2,z:0}),e=A.init({x:2,z:0});
 assert(p.build.move===3.86&&A.builds.speedy.move===4.83&&A.builds.tank.move===3.24,'speed increase');
 assert(A.collect(p,'stretch')&&p.effectTime===6,'free pickup');assert(A.movement(p,true,true,1)===A.movement(p),'dash remains');
 assert(A.mods(p).length===1.65,'stretch modifiers');
 A.step(p,6.1);assert(!p.effect&&A.mods(p).length===1,'effect expiry');
 A.collect(p,'inflate');assert(A.mods(p).radius===1.7,'inflate modifier');
 A.collect(p,'retract');assert(p.effect==='retract'&&p.effectTime===5,'replacement');
 p.hp=0;assert(!A.collect(p,'inflate'),'dead fighter pickup');p.hp=100;
 const field=new CushionFieldItems(rng);field.reset([p,e]);
 assert(field.list.length===3&&field.list.every(i=>!('type' in i)),'initial items');
 assert(field.list.every(i=>Math.abs(i.x)<=5.4&&Math.abs(i.z)<=5.4&&Math.hypot(i.x-p.x,i.z-p.z)>=1.5),'safe spawn');
 const first=field.list[0];p.x=first.x;p.z=first.z;
 const pickups=field.step(.01,[p,e]);assert(pickups.length===1&&field.list.length===2&&p.effect===pickups[0].effect,'pickup once');
 assert(field.step(.01,[p,e]).length===0,'duplicate pickup');
 field.step(4,[p,e]);assert(field.list.length===3,'replenishment');
 for(let i=0;i<8;i++){field.step(4,[p,e]);assert(field.list.length<=3,'item cap');}
 field.list=[{type:'stretch',x:0,z:0,life:18}];p.x=.6;p.z=0;e.x=.1;e.z=0;
 const nearest=field.step(.01,[p,e]);assert(nearest.length===1&&nearest[0].fighter===e,'nearest winner');
 field.list=[{type:'inflate',x:5,z:5,life:.01}];assert(field.step(.02,[p,e]).length===0&&field.list.length===0,'item expiry');
 for(const [roll,effect]of [[.1,'inflate'],[.5,'stretch'],[.9,'retract']]){
  const mystery=new CushionFieldItems(()=>roll);mystery.list=[{x:p.x,z:p.z,life:18}];
  const result=mystery.step(.01,[p]);assert(result.length===1&&p.effect===effect,'random effect '+effect);
 }
 const source=await(await fetch('game.js')).text(),ending="sample();syncItems();syncAttackButtons();showScreen('draw','replace',false);requestAnimationFrame(frame);";
 assert(source.includes(ending),'fixture anchor');
 eval(source.replace(ending,`sample();syncItems();window.test={reset,tick,render,project,damageNumbers,dealDamage,stepDamageNumbers,performAttack,syncAttackButtons,keys,stick,attackPointers,fieldItems,weapon,weaponRadius,attack,pause,edit,syncItems,pixel:(x,y)=>{const ratio=scene.width/scene.getBoundingClientRect().width;return [...ctx.getImageData(Math.round(x*ratio),Math.round(y*ratio),1,1).data]},get p(){return player},get e(){return enemy}};`));
 const T=test,$=id=>document.getElementById(id),advance=s=>{for(let i=0;i<Math.round(s*240);i++)T.tick(1/240);T.syncItems();};
 assert(!document.querySelector('#loadout,#selectedSkill,[data-skill],#staminaBar,#maxStamina'),'removed controls remain');
 assert(document.body.dataset.screen==='draw'&&!$('workshop').hidden&&$('arena').hidden&&$('result').hidden,'initial draw screen');
 const preview=$('shapePreview').getContext('2d').getImageData(0,0,560,210).data;assert(preview.some((v,i)=>i%4===3&&v>0),'empty 3D preview');
 const drawing=$('draw').toDataURL(),color=$('color').value,thickness=$('thickness').value;
 $('start').click();assert(document.body.dataset.screen==='battle'&&$('workshop').hidden&&!$('arena').hidden&&$('result').hidden,'battle view');
 $('backDraw').click();assert(document.body.dataset.screen==='draw'&&$('arena').hidden&&$('draw').toDataURL()===drawing,'back preserved drawing');
 T.reset();T.p.hp=0;T.tick(1/240);
 assert(document.body.dataset.screen==='result'&&$('arena').hidden&&!$('result').hidden,'standalone result');
 $('retry').click();assert(document.body.dataset.screen==='battle'&&T.p.hp===200,'retry returns to battle');
 T.p.hp=0;T.tick(1/240);$('edit').click();
 assert(document.body.dataset.screen==='draw'&&$('draw').toDataURL()===drawing&&$('color').value===color&&$('thickness').value===thickness,'result edit preserved setup');
 $('start').click();history.back();await new Promise(r=>setTimeout(r,100));
 assert(document.body.dataset.screen==='draw'&&$('arena').hidden,'browser back returns to drawing');

 $('build').value='tank';$('build').dispatchEvent(new Event('input'));T.reset();
 assert(T.p.hp===280&&$('pbar').max===280,'build HP');
 assert(T.fieldItems.list.length===3&&!T.p.effect&&!T.e.effect,'round initial state');
 T.p.x=-6;T.e.x=6;T.fieldItems.list=[{x:-6,z:0,type:'inflate',life:18}];
 const radius=T.weaponRadius(T.p,false),normalRandom=T.fieldItems.random;T.fieldItems.random=()=>.1;T.tick(1/240);T.fieldItems.random=normalRandom;T.syncItems();
 assert(T.p.effect==='inflate'&&T.weaponRadius(T.p,false)>radius*1.6,'pickup geometry and collision radius');
 assert(!$('activeItem').textContent&&$('activeItem').getAttribute('aria-label').includes('ふくらむ'),'quiet pickup HUD');
 const effectTime=T.p.effectTime,timer=T.fieldItems.timer;T.pause();advance(1);
 assert(T.p.effectTime===effectTime&&T.fieldItems.timer===timer,'pause effects/spawns');T.pause();
 T.fieldItems.list=[];T.fieldItems.timer=100;advance(6.1);assert(!T.p.effect,'expiry in game');
 T.reset();T.p.x=-6;T.e.x=6;T.fieldItems.list=[{x:6,z:0,type:'stretch',life:18}];T.fieldItems.random=()=>.5;T.tick(1/240);T.fieldItems.random=normalRandom;
 assert(T.e.effect==='stretch'&&T.fieldItems.list.length===0,'CPU pickup');
 T.reset();T.p.x=-6;T.e.x=6;T.e.cd=100;T.fieldItems.list=[];T.fieldItems.timer=100;
 const initialEnemyX=T.e.x;T.keys.add('w');T.tick(.1);
 assert(Math.abs(initialEnemyX-T.e.x-2.16*.1)<.001,'CPU speed');
 assert(Math.abs(T.p.z+3.24*.1)<.001,'player speed');
 // CPU should stay in its comfort band even during attack cooldowns.
 T.reset();T.p.x=-6;T.e.x=6;T.e.cd=100;T.fieldItems.list=[];T.fieldItems.timer=100;
 advance(5);let distance=Math.hypot(T.p.x-T.e.x,T.p.z-T.e.z);
 assert(distance>=3.59&&distance<=3.61,'CPU pursued past stopping distance '+distance);
 T.p.x=0;T.e.x=2;T.p.z=T.e.z=0;T.e.cd=100;const closeX=T.e.x;advance(.3);
 assert(T.e.x>closeX,'CPU did not back off');
 T.p.x=0;T.e.x=3.2;T.p.z=T.e.z=0;T.e.cd=100;const stableX=T.e.x;advance(.3);
 assert(Math.abs(T.e.x-stableX)<.001,'CPU jittered inside comfort band');
 T.fieldItems.list=[{x:-.5,z:0,type:'inflate',life:18}];advance(.3);
 assert(Math.abs(T.e.x-stableX)<.001,'CPU crossed player for item');
 T.reset();T.p.x=0;T.e.x=4.59;T.fieldItems.list=[];T.fieldItems.timer=100;A.collect(T.e,'stretch');T.tick(1/240);
 assert(T.e.wind>0,'stretched CPU stopped outside attack range');
 T.reset();T.p.x=-6;T.e.x=6;T.e.cd=100;
 T.fieldItems.list=[{x:6,z:-2,type:'stretch',life:18}];T.fieldItems.random=()=>.5;advance(1);T.fieldItems.random=normalRandom;
 assert(T.e.effect==='stretch','CPU seeks item');
 T.reset();T.p.x=-1;T.e.x=1;T.e.cd=100;T.fieldItems.list=[];T.fieldItems.timer=100;
 const before=[T.p.x,T.p.z,T.e.x,T.e.z];
 assert(P.separate(T.p,T.e,T.weapon,T.weaponRadius),'expected contact');
 assert(before.every((n,i)=>n===[T.p.x,T.p.z,T.e.x,T.e.z][i]),'contact moved fighters');
 T.keys.add('w');advance(.25);assert(T.p.z<-.69&&Math.abs(T.p.x+1)<.01,'contact blocked movement');
 assert(T.p.hp===280&&T.e.hp===200,'idle contact damage');
 // Match target defense and attack power: weapon contact versus unguarded body.
 function damageTrial(body,inflated){
  T.reset();T.fieldItems.list=[];T.fieldItems.timer=100;T.e.cd=100;
  T.p.x=body?-1:-2.3;T.e.x=body?1:2.3;T.p.angle=Math.PI/2;T.e.angle=body?0:-Math.PI/2;
  T.attack(T.p,false);T.p.swing=.18;if(body){T.e.fold=.04;const path=T.weapon(T.p,false),point=path[Math.floor(path.length*.65)];T.e.x=point.x;T.e.z=point.z;}
  if(inflated)A.collect(T.p,'inflate');
  advance(.0042);return T.e.maxHP-T.e.hp;
 }
 // Weapon contact must not stop, fold, or repeatedly damage an attack.
 T.reset();T.fieldItems.list=[];T.fieldItems.timer=100;T.e.cd=100;
 T.p.x=-1;T.e.x=1;T.p.fold=.08;T.p.bend=1.4;
 T.attack(T.p,false);assert(T.p.fold===1&&T.p.bend===0,'swing started pinned');
 advance(.08);const afterFirst=T.e.hp;
 assert(afterFirst<T.e.maxHP&&T.p.swing>0&&T.p.fold===1&&T.p.bend===0,'contact stopped or deformed swing');
 advance(.08);assert(T.e.hp===afterFirst&&T.p.swing>0,'repeat damage or canceled follow-through');
 advance(.2);assert(T.p.swing===0,'swing never completed');
 const rod=damageTrial(false,false),body=damageTrial(true,false),boosted=damageTrial(false,true);
 assert(rod>0&&body>rod&&boosted>rod,'rod/body/boosted damage '+[rod,body,boosted]);
 T.reset();T.keys.add('shift');
 for(let i=0;i<6000;i++){
  T.keys.delete('w');T.keys.delete('s');T.keys.add(Math.floor(i/480)%2?'w':'s');if(i%300===0)T.performAttack(i%600===0?'thrust':'sweep');T.tick(1/240);
  assert(Number.isFinite(T.p.x)&&Math.abs(T.p.x)<=6.41&&Math.abs(T.p.z)<=6.41,'bounds');
 }
 assert(T.e.hp<T.e.maxHP,'combat damage');
 T.reset();T.e.x=6;T.e.z=6;T.fieldItems.list=[];
 for(const z of [-6.4,-4,0,4,6.4])for(const x of [-5,0,5]){
  T.p.x=x;T.p.z=z;T.p.flash=0;T.render();const at=T.project({x,y:.55,z}),pixel=T.pixel(at.x,at.y);
  assert(pixel[0]>pixel[1]&&pixel[2]>pixel[0]*1.2,'floor hid body');
 }
 for(const [id,type]of [['attack','thrust'],['sweep','sweep']]){
  T.reset();T.p.x=-6;T.e.x=6;T.fieldItems.list=[];T.fieldItems.timer=100;T.e.cd=100;
  $(id).click();assert(T.p.move===type&&T.p.swing>0,'tap did not attack immediately '+type);
  assert(!T.performAttack(type==='thrust'?'sweep':'thrust'),'shared cooldown bypass');
  advance(2.2);assert(T.p.swing===0&&T.p.cd===0,'tap repeated automatically');
 }
 T.reset();window.dispatchEvent(new KeyboardEvent('keydown',{key:'k'}));
 assert(T.p.move==='sweep'&&T.p.swing>0,'keyboard sweep');
 T.reset();window.dispatchEvent(new KeyboardEvent('keydown',{key:' '}));
 assert(T.p.move==='thrust'&&T.p.swing>0,'keyboard thrust');
 T.reset();window.dispatchEvent(new KeyboardEvent('keydown',{key:'k',repeat:true}));
 assert(T.p.swing===0,'held key repeated attack');
 assert(!document.querySelector('#chargeBar,#chargeText'),'charging UI remains');
 T.reset();T.render();T.syncItems();
 assert(!$('toast').textContent&&getComputedStyle($('activeItem')).display==='none','battle announcements remain');
 T.e.hp=5;const lost=T.dealDamage(T.e,100);
 assert(lost===5&&T.damageNumbers.at(-1).damage===5,'overkill popup did not match HP');
 T.render();T.stepDamageNumbers(.7);assert(T.damageNumbers.length===0,'popup did not expire');
 for(const [id,profile]of Object.entries(CushionEnemies)){
  T.edit();$('enemyType').value=id;$('enemyType').dispatchEvent(new Event('change'));T.reset();
  assert(T.e.hp===profile.hp&&$('ebar').max===profile.hp,'enemy HP '+id);
  assert(T.e.profile===profile&&T.weapon(T.e,true).length===profile.shape.length,'enemy shape '+id);
  assert($('enemyType').disabled,'enemy changed during battle');
  T.p.x=-6;T.e.x=6;T.fieldItems.list=[];T.fieldItems.timer=100;T.e.cd=100;
  const x=T.e.x;T.tick(.1);assert(Math.abs(x-T.e.x-profile.speed*.1)<.001,'enemy speed '+id);
  T.e.cd=0;T.attack(T.e,true);assert(T.e.move===profile.move,'enemy attack '+id);
  T.render();T.edit();assert($('enemyType').value===id,'enemy selection lost on edit');
 }
 T.edit();$('enemyType').value='pop';$('enemyType').dispatchEvent(new Event('change'));T.reset();
 assert(T.damageNumbers.length===0,'popups not reset');
 return {passed:true,items:3,enemies:4,damage:{rod,body,boosted}};
})()
''')
        print(result)
        for width in [320, 390, 800, 1280]:
            await call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': width < 600})
            assert await js('document.documentElement.scrollWidth<=innerWidth'), width
        for width, height in [(320,640),(390,844),(844,390)]:
            await call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': True})
            layout = await js("""(()=>{
              test.render();const stage=document.querySelector('.viewport').getBoundingClientRect();
              const stick=document.getElementById('joystick').getBoundingClientRect(),attack=document.getElementById('attack').getBoundingClientRect();
              window.scrollTo(0,150);
              return {locked:document.documentElement.classList.contains('battle-lock')&&scrollY===0,
                overlay:[stick,attack].every(r=>r.width>0&&r.height>0&&r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight),
                clearField:innerWidth>innerHeight?[stick,attack].every(r=>r.right<=stage.left||r.left>=stage.right):[stick,attack].every(r=>r.top>=stage.bottom),
                transparent:parseFloat(getComputedStyle(document.getElementById('joystick')).opacity)<1,
                height:stage.height};
            })()""")
            assert layout['locked'] and layout['overlay'] and layout['clearField'] and layout['transparent'] and layout['height']>=100, (width,height,layout)
        await call('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': True})
        await js('test.render();document.getElementById("arena").scrollIntoView()')
        shot = await call('Page.captureScreenshot', {'format': 'png'})
        with open('/tmp/cushion-items-mobile.png', 'wb') as f:
            f.write(base64.b64decode(shot['data']))
        # Real multi-touch events exercise pointer capture and independent thumbs.
        await call('Emulation.setTouchEmulationEnabled', {'enabled': True})
        await js('test.reset();document.getElementById("touch").scrollIntoView({block:"center",behavior:"instant"})')
        await asyncio.sleep(.2)
        await call('Emulation.setPageScaleFactor', {'pageScaleFactor': 1})
        await js('document.getElementById("touch").scrollIntoView({block:"center",behavior:"instant"})')
        await js('window.gestureLog=[];for(const name of ["pointerdown","pointermove","pointerup","pointercancel","lostpointercapture"])document.addEventListener(name,e=>gestureLog.push([name,e.pointerId,e.target.id,e.clientX,e.clientY]))')
        boxes = await js('Object.fromEntries(["joystick","attack","sweep"].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return [id,{x:r.x+r.width/2,y:r.y+r.height/2,r:r.width*.34}]}))')
        stick = {'id': 1, 'x': boxes['joystick']['x'], 'y': boxes['joystick']['y'], 'radiusX': 6, 'radiusY': 6}
        attack = {'id': 2, 'x': boxes['attack']['x'], 'y': boxes['attack']['y'], 'radiusX': 6, 'radiusY': 6}
        async def touch(kind, points):
            await call('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': points})
            await asyncio.sleep(.08)
        assert await js('(()=>{const r=document.getElementById("joystick").getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight})()'), 'stick not visible for gesture'
        # Swipe on the non-control part of the battle page: it must not pan.
        await touch('touchStart', [{'id':9,'x':12,'y':20}])
        await touch('touchMove', [{'id':9,'x':12,'y':150}])
        await touch('touchEnd', [])
        assert await js('scrollY===0&&document.documentElement.scrollTop===0'), 'background gesture scrolled battle'
        await touch('touchStart', [stick])
        stick['x'] += boxes['joystick']['r'] * .45
        await touch('touchMove', [stick])
        assert await js('test.stick.x>.2&&test.stick.x<.6'), 'analog walk'
        stick['x'] = boxes['joystick']['x'] + boxes['joystick']['r']
        await touch('touchMove', [stick])
        assert await js('test.stick.x>.99'), 'full analog movement'
        await touch('touchStart', [stick, attack])
        assert await js('test.attackPointers.size===1&&test.stick.x>.99'), 'move and attack'
        await js('test.tick(.35)')
        await touch('touchEnd', [attack])
        assert await js('test.attackPointers.size===0&&test.stick.x>.99'), await js('JSON.stringify({stick:test.stick,attack:[...test.attackPointers],events:gestureLog})')
        assert await js('test.p.move==="thrust"&&test.p.swing===0'), 'release unexpectedly attacked'
        await js('test.tick(2)')
        sweep = {'id':3,'x':boxes['sweep']['x'],'y':boxes['sweep']['y'],'radiusX':6,'radiusY':6}
        await touch('touchStart', [stick,sweep])
        assert await js('test.p.move==="sweep"&&test.p.swing>0'), 'touch sweep not immediate'
        await touch('touchEnd', [])
        assert await js('test.stick.pointer===null&&test.stick.x===0&&test.stick.x===0'), 'stick release'
        await touch('touchStart', [stick, attack])
        await js('test.pause()')
        assert await js('test.stick.pointer===null&&test.attackPointers.size===0'), 'pause cleared touch'
        await touch('touchCancel', [])
        await js('test.pause()')
        assert await js('test.stick.x===0&&test.attackPointers.size===0'), 'resume stuck input'
        await call('Emulation.setDeviceMetricsOverride', {'width': 320, 'height': 640, 'deviceScaleFactor': 1, 'mobile': True})
        await js('test.edit();window.scrollTo(0,120)')
        assert await js('!document.documentElement.classList.contains("battle-lock")&&scrollY>0'), 'drawing scroll was not restored'
        # Horizontal canvas gestures are drawing, not browser navigation.
        await call('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
        await js('test.edit();document.getElementById("draw").scrollIntoView({block:"center",behavior:"instant"})')
        draw_box = await js('(()=>{const r=document.getElementById("draw").getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()')
        assert draw_box['x'] >= 40, draw_box
        before = await js('document.getElementById("draw").toDataURL()')
        start_scroll = await js('scrollY')
        finger = {'id': 11, 'x': draw_box['x'] + 4, 'y': draw_box['y'] + draw_box['h'] * .65}
        await touch('touchStart', [finger])
        for fraction in [.15,.4,.7,.95,.6,.2]:
            finger['x'] = draw_box['x'] + draw_box['w'] * fraction
            await touch('touchMove', [finger])
        await touch('touchEnd', [])
        assert await js('location.hash==="#draw"&&document.body.dataset.screen==="draw"'), 'canvas swipe navigated'
        assert abs(await js('scrollY') - start_scroll) < 1, 'canvas swipe scrolled page'
        assert before != await js('document.getElementById("draw").toDataURL()'), 'touch stroke missing'
        assert await js('!document.getElementById("start").disabled'), 'touch drawing invalid'
        assert await js('!document.getElementById("draw").dispatchEvent(new TouchEvent("touchstart",{bubbles:true,cancelable:true}))'), 'native canvas gesture not canceled'
        finger['y'] = draw_box['y'] + draw_box['h'] * .3
        await touch('touchStart', [finger])
        finger['x'] += 30
        await touch('touchMove', [finger])
        interrupted = await js('document.getElementById("draw").toDataURL()')
        await touch('touchCancel', [])
        assert interrupted == await js('document.getElementById("draw").toDataURL()'), 'interrupted stroke lost'
        await call('Page.removeScriptToEvaluateOnNewDocument', {'identifier': fixture['identifier']})
        await call('Page.reload', {'ignoreCache': True})
        await asyncio.sleep(.6)
        await js('document.getElementById("start").click()')
        await asyncio.sleep(.5)
        assert await js('document.getElementById("status").textContent==="対戦中"'), 'live game loop'
        audio = await js("""(async()=>{
          const S=CushionSound,previous=S.enabled;S.setEnabled(true);S.setMuted(false);
          if(!await S.unlock())return {available:false};
          S.play('heavy');await new Promise(r=>setTimeout(r,50));const level=S.level();
          const played=S.state.played;S.setEnabled(false);S.play('body');
          const muted=S.state.played===played;S.setEnabled(previous);
          return {available:true,level,muted};
        })()""")
        assert audio['available'] and audio['level'] > 0 and audio['muted'], audio
        print('Web Audio synthesized output:', audio)
        assert not errors, errors
        print('PASS: item spawning/pickup/expiry/replacement, rod/body damage, defense/builds, keyboard/buttons, size and hit radius, pause/reset, soft contact mobility, combat, multi-touch/analog/release, two immediate attacks/shared cooldown/no hold-repeat, synthesized sound/mute, 320–1280px; no JS errors')


if __name__ == '__main__':
    asyncio.run(main())
