'use strict';
(() => {
const $=id=>document.getElementById(id), draw=$('draw'), dc=draw.getContext('2d'), scene=$('scene'), ctx=scene.getContext('2d');
let points=[],draft=[],drawing=false,drawingPointer=null,shape=[],reach=2.5,drawRadius=.08,power=18,cooldown=.8,running=false,paused=false,last=0,time=0;
const keys=new Set(), particles=[],damageNumbers=[];
const Ab=CushionAbilities,Combat=CushionCombat,Sound=CushionSound;
const ARENA={limit:6.4,edge:7,half:7.2};
let player,enemy,clashCooldown=0;
const fieldItems=new CushionFieldItems();
function enemyProfile(){return enemy?.profile||CushionEnemies.pop;}
function updateEnemy(){$('enemyDescription').textContent=CushionEnemies[$('enemyType').value].description;}
$('enemyType').onchange=updateEnemy;updateEnemy();
const stick={pointer:null,x:0,z:0},attackPointers=new Map();
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function showScreen(name,mode='push',focus=true){
 clearInputs();document.body.dataset.screen=name;document.documentElement.classList.toggle('battle-lock',name==='battle');document.documentElement.classList.toggle('drawing-screen',name==='draw');
 $('workshop').hidden=name!=='draw';document.querySelector('.intro').hidden=name!=='draw';
 $('arena').hidden=name!=='battle';$('result').hidden=name!=='result';
 const hash='#'+name;
 if(location.hash!==hash)history[mode==='replace'?'replaceState':'pushState']({cushionScreen:name},'',hash);
 window.scrollTo({top:0,behavior:'instant'});
 if(focus)$(name==='draw'?'drawTitle':name==='battle'?'battleTitle':'resultTitle').focus({preventScroll:true});
}
// Keep gestures outside the controls from panning/bouncing the game page on mobile.
window.addEventListener('touchmove',e=>{if(document.body.dataset.screen==='battle'&&e.cancelable)e.preventDefault();},{passive:false});
window.addEventListener('wheel',e=>{if(document.body.dataset.screen==='battle'&&e.cancelable)e.preventDefault();},{passive:false});
window.addEventListener('popstate',()=>{
 const requested=location.hash.slice(1);
 if(requested==='battle'&&player&&player.hp>0&&enemy.hp>0){showScreen('battle','replace');if(running&&!paused)pause();}
 else if(requested==='result'&&player&&(player.hp<=0||enemy.hp<=0))showScreen('result','replace');
 else edit('replace');
});
function sample(){points=Array.from({length:25},(_,i)=>({x:65+i*17,y:175-Math.sin(i/24*Math.PI)*80+Math.sin(i/24*Math.PI*3)*24})); update();}
function paint(){dc.clearRect(0,0,560,320);dc.strokeStyle='#dedacf';dc.lineWidth=1;for(let x=20;x<560;x+=24)for(let y=16;y<320;y+=24){dc.beginPath();dc.arc(x,y,1,0,7);dc.stroke();} const p=drawing?draft:points;if(!p.length)return;dc.beginPath();dc.moveTo(p[0].x,p[0].y);for(const q of p)dc.lineTo(q.x,q.y);dc.lineWidth=+$('thickness').value;dc.lineCap='round';dc.lineJoin='round';dc.strokeStyle=$('color').value;dc.stroke();}
function update(){$('thicknessValue').value=$('thickness').value;paint();const build=Ab.builds[$('build').value];$('maxHP').textContent=build.hp;$('defense').textContent=Math.round(build.defense*100)+'%';$('mobility').textContent=build.move.toFixed(1);if(points.length<2){shape=[];paintPreview();$('start').disabled=true;for(const id of ['reach','power','speed'])$(id).textContent='—';return;}let length=0;for(let i=1;i<points.length;i++)length+=Math.hypot(points[i].x-points[i-1].x,points[i].y-points[i-1].y);if(length<25){shape=[];paintPreview();$('start').disabled=true;$('drawHint').textContent='もう少し長い線を描いてね。';return;}const radius=+$('thickness').value/70;const xs=points.map(p=>p.x),ys=points.map(p=>p.y);const scale=2.8/Math.max(80,Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys));drawRadius=+$('thickness').value*scale/2;shape=CushionPhysics.drawingShape(points,scale);reach=Math.max(...shape.map(p=>Math.hypot(p.x,p.z)))+drawRadius;power=Math.round(12+radius*30);cooldown=.48+radius*1.2+length/1600;$('reach').textContent=reach.toFixed(1)+' m';$('power').textContent=power;$('speed').textContent=(1/cooldown).toFixed(1)+'/秒';$('start').disabled=false;$('drawHint').textContent='描いた線をそのまま丸いチューブに。左端（縦長なら上端）が根元になります。';paintPreview();}
function paintPreview(){
 const canvas=$('shapePreview'),c=canvas.getContext('2d');c.clearRect(0,0,canvas.width,canvas.height);
 if(shape.length<2)return;
 const project=p=>({x:p.z*.85+p.x*.5,y:p.z*.28-p.x*.5-p.y*.9,d:p.x+p.z-p.y});
 const mesh=CushionPhysics.tubeMesh(shape,drawRadius),vertices=mesh.flatMap(f=>f.points.map(project));
 const minX=Math.min(...vertices.map(p=>p.x)),maxX=Math.max(...vertices.map(p=>p.x)),minY=Math.min(...vertices.map(p=>p.y)),maxY=Math.max(...vertices.map(p=>p.y));
 const fit=Math.min((canvas.width-36)/(maxX-minX||1),(canvas.height-36)/(maxY-minY||1));
 const faces=mesh.map(f=>({points:f.points.map(project),light:f.light}));faces.sort((a,b)=>b.points.reduce((n,p)=>n+p.d,0)/b.points.length-a.points.reduce((n,p)=>n+p.d,0)/a.points.length);
 for(const face of faces){c.fillStyle=shade($('color').value,face.light);c.beginPath();face.points.forEach((p,i)=>{const x=canvas.width/2+(p.x-(minX+maxX)/2)*fit,y=canvas.height/2+(p.y-(minY+maxY)/2)*fit;i?c.lineTo(x,y):c.moveTo(x,y);});c.closePath();c.fill();}
 const root=project({x:0,y:.95,z:0});c.fillStyle='#c7f88c';c.beginPath();c.arc(canvas.width/2+(root.x-(minX+maxX)/2)*fit,canvas.height/2+(root.y-(minY+maxY)/2)*fit,4,0,Math.PI*2);c.fill();
}
function pos(e){const r=draw.getBoundingClientRect();return{x:clamp((e.clientX-r.left)*560/r.width,10,550),y:clamp((e.clientY-r.top)*320/r.height,10,310)};}
// Cancel browser swipe navigation over the canvas, including Safari touch gestures.
for(const event of ['touchstart','touchmove'])draw.addEventListener(event,e=>{if(document.body.dataset.screen==='draw'&&e.cancelable)e.preventDefault();},{passive:false});
draw.onpointerdown=e=>{if(running||drawing||e.isPrimary===false)return;if(e.cancelable)e.preventDefault();drawing=true;drawingPointer=e.pointerId;draft=[pos(e)];draw.setPointerCapture(e.pointerId);paint();};draw.onpointermove=e=>{if(drawing&&e.pointerId===drawingPointer){if(e.cancelable)e.preventDefault();const p=pos(e);if(Math.hypot(p.x-draft.at(-1).x,p.y-draft.at(-1).y)>4)draft.push(p);paint();}};draw.onpointerup=e=>{if(!drawing||e.pointerId!==drawingPointer)return;drawing=false;drawingPointer=null;points=draft;update();};draw.onpointercancel=e=>{if(!drawing||e.pointerId!==drawingPointer)return;drawing=false;drawingPointer=null;if(draft.length>1){points=draft;update();}else paint();};$('clear').onclick=()=>{if(!running){points=[];update();}};$('sample').onclick=()=>{if(!running)sample();};for(const id of ['thickness','color','build'])$(id).oninput=()=>{if(!running)update();};
function fighter(x,z){return Ab.init({x,z,hp:100,angle:0,cd:0,swing:0,hit:false,flash:0,wind:0,vx:0,vz:0,deflect:0,move:'thrust',swingDuration:.28});}
function reset(){player=Ab.init(fighter(-2,0),$('build').value);enemy=fighter(2,0);enemy.profile=CushionEnemies[$('enemyType').value]||CushionEnemies.pop;enemy.hp=enemy.maxHP=enemy.profile.hp;enemy.build={...enemy.build,defense:enemy.profile.defense};enemy.angle=-Math.PI/2;player.angle=Math.PI/2;particles.length=0;damageNumbers.length=0;time=0;fieldItems.reset([player,enemy]);clashCooldown=0;running=true;paused=false;clearInputs();$('pause').textContent='一時停止';$('result').hidden=true;$('overlay').hidden=true;$('hud').hidden=false;$('status').textContent='対戦中';for(const id of ['thickness','color','clear','sample','build','enemyType'])$(id).disabled=true;draw.style.opacity='.65';$('start').disabled=true;sync();syncItems();showScreen('battle');Sound.setMuted(false);Sound.play('start');}
function edit(mode='push'){running=false;fieldItems.list=[];damageNumbers.length=0;player=enemy=null;paused=false;clearInputs();$('result').hidden=true;$('hud').hidden=true;$('overlay').hidden=false;$('status').textContent='プレビュー';for(const id of ['thickness','color','clear','sample','build','enemyType'])$(id).disabled=false;draw.style.opacity='1';update();syncItems();showScreen('draw',mode);Sound.setMuted(false);}
$('start').onclick=()=>{if(shape.length)reset();};$('retry').onclick=reset;$('edit').onclick=()=>edit();$('backDraw').onclick=()=>edit();
function pause(){if(!running)return;paused=!paused;clearInputs();$('pause').textContent=paused?'再開':'一時停止';$('status').textContent=paused?'一時停止中':'対戦中';Sound.setMuted(paused);if(!paused)Sound.unlock();} $('pause').onclick=pause;document.addEventListener('visibilitychange',()=>{clearInputs();if(document.hidden&&running&&!paused)pause();Sound.setMuted(document.hidden||paused);});window.addEventListener('blur',()=>{clearInputs();if(running&&!paused)pause();});
function resetStick(){
 const pointer=stick.pointer;stick.pointer=null;stick.x=stick.z=0;
 $('stickKnob').style.transform='translate(-50%,-50%)';$('stickState').textContent='移動';
 if(pointer!==null&&$('joystick').hasPointerCapture(pointer))$('joystick').releasePointerCapture(pointer);
}
function clearInputs(){keys.clear();resetStick();attackPointers.clear();for(const id of ['attack','sweep'])$(id).classList.remove('pressed');}
function moveStick(e){
 const r=$('joystick').getBoundingClientRect(),limit=r.width*.34;
 let x=(e.clientX-r.left-r.width/2)/limit,z=(e.clientY-r.top-r.height/2)/limit;
 const distance=Math.hypot(x,z),magnitude=Math.min(1,distance);
 x/=distance||1;z/=distance||1;
 const amount=magnitude<.14?0:(magnitude-.14)/.86;
 stick.x=x*amount;stick.z=z*amount;
 $('stickKnob').style.transform=`translate(calc(-50% + ${x*magnitude*limit}px),calc(-50% + ${z*magnitude*limit}px))`;

}
$('joystick').onpointerdown=e=>{if(!running||paused||stick.pointer!==null)return;e.preventDefault();stick.pointer=e.pointerId;$('joystick').setPointerCapture(e.pointerId);moveStick(e);};
$('joystick').onpointermove=e=>{if(e.pointerId===stick.pointer){e.preventDefault();moveStick(e);}};
for(const event of ['pointerup','pointercancel','lostpointercapture'])$('joystick').addEventListener(event,e=>{if(e.pointerId===stick.pointer)resetStick();});
function performAttack(type){
 if(!running||paused)return false;
 if(!Combat.launch(player,type,cooldown))return false;
 Sound.play(type);return true;
}
for(const [id,type]of [['attack','thrust'],['sweep','sweep']]){
 const button=$(id);
 button.onpointerdown=e=>{e.preventDefault();if(!performAttack(type))return;button.setPointerCapture(e.pointerId);attackPointers.set(e.pointerId,id);button.classList.add('pressed');};
 for(const event of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(event,e=>{if(attackPointers.get(e.pointerId)!==id)return;attackPointers.delete(e.pointerId);button.classList.remove('pressed');});
 button.onclick=e=>{if(e.detail===0)performAttack(type);};
}
window.addEventListener('keydown',e=>{
 if(e.target instanceof HTMLInputElement||e.target instanceof HTMLSelectElement)return;
 if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight',' ','j','k','J','K'].includes(e.key)&&running)e.preventDefault();
 if(!e.repeat){if(e.key===' '||e.key.toLowerCase()==='j')performAttack('thrust');if(e.key.toLowerCase()==='k')performAttack('sweep');}
 keys.add(e.key.toLowerCase());
 if(e.key==='Escape'&&!e.repeat)pause();
});
window.addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));
function syncItems(){
 const p=player;
 const item=running&&p&&p.effect?Ab.items[p.effect]:null;
 $('activeItem').textContent='';$('activeItem').setAttribute('aria-label',item?item.name+' '+Math.ceil(p.effectTime)+'秒':'');
 $('activeItem').style.color=item?item.color:'';
 $('itemDescription').textContent=item?item.description+' / 別のアイテムを拾うと切り替わります':'光るアイテムに近づくと自動発動。CPUも拾います。';
}
function syncSound(){$('sound').textContent=Sound.enabled?'音 ON':'音 OFF';$('sound').setAttribute('aria-pressed',String(Sound.enabled));}
$('sound').onclick=async()=>{Sound.setEnabled(!Sound.enabled);syncSound();if(await Sound.unlock())Sound.play('pickup');};
for(const event of ['pointerdown','keydown'])window.addEventListener(event,()=>{Sound.unlock();},{capture:true});
function syncAttackButtons(){
 const ready=running&&!paused&&player&&player.cd<=0&&player.swing<=0;
 for(const id of ['attack','sweep']){$(id).classList.toggle('cooling',!ready);$(id).setAttribute('aria-disabled',String(!ready));}
}
syncSound();
function dealDamage(target,amount){
 const before=target.hp;Ab.damage(target,amount);const damage=before-target.hp;
 if(damage>0){damageNumbers.push({x:target.x,z:target.z,y:1.65,damage,life:.65,player:target===player});if(damageNumbers.length>8)damageNumbers.shift();}
 return damage;
}
function stepDamageNumbers(dt){for(let i=damageNumbers.length-1;i>=0;i--){damageNumbers[i].life-=dt;damageNumbers[i].y+=dt*.65;if(damageNumbers[i].life<=0)damageNumbers.splice(i,1);}}
function sync(){for(const [p,n]of[[player,'p'],[enemy,'e']]){$(n+'hp').textContent=Math.ceil(p.hp);$(n+'bar').max=p.maxHP;$(n+'bar').value=p.hp;}}
function attack(p,isEnemy){const type=isEnemy?enemyProfile().move:'thrust';if(Combat.launch(p,type,isEnemy?enemyProfile().interval:cooldown))Sound.play(type);}
function weapon(p,isEnemy){let a=p.angle+p.deflect+p.bend+Combat.pose(p).angle;const source=isEnemy?enemyProfile().shape.map(([x,z])=>({x,y:.95,z})):shape;const length=Ab.mods(p).length*p.fold*Combat.pose(p).length;return source.map(q=>({x:p.x+(q.x*Math.cos(a)+q.z*Math.sin(a))*length,y:q.y,z:p.z+(-q.x*Math.sin(a)+q.z*Math.cos(a))*length}));}
function weaponRadius(p,isEnemy){return (isEnemy?enemyProfile().radius:drawRadius)*Ab.mods(p).radius*(.5+.5*p.fold);}
function attackPower(p,isEnemy){return (isEnemy?enemyProfile().damage:power*(Combat.moves[p.move]?.damage||1))*Ab.mods(p).damage;}
function segmentDistance(p,a,b){const dx=b.x-a.x,dz=b.z-a.z,t=clamp(((p.x-a.x)*dx+(p.z-a.z)*dz)/(dx*dx+dz*dz||1),0,1);return Math.hypot(p.x-a.x-t*dx,p.z-a.z-t*dz);}
function tick(dt){if(!running||paused)return;clashCooldown=Math.max(0,clashCooldown-dt);time+=dt;for(const p of [player,enemy])Ab.step(p,dt);let x=(keys.has('d')||keys.has('arrowright')?1:0)-(keys.has('a')||keys.has('arrowleft')?1:0),z=(keys.has('s')||keys.has('arrowdown')?1:0)-(keys.has('w')||keys.has('arrowup')?1:0),keyboardLength=Math.hypot(x,z);if(!keyboardLength){x=stick.x;z=stick.z;}let n=Math.max(1,Math.hypot(x,z)),move=Ab.movement(player);player.x+=x/n*dt*move;player.z+=z/n*dt*move;let dx=player.x-enemy.x,dz=player.z-enemy.z,d=Math.hypot(dx,dz)||1;const turn=(p,a,speed)=>{const delta=Math.atan2(Math.sin(a-p.angle),Math.cos(a-p.angle));p.angle+=clamp(delta,-speed*dt,speed*dt);};turn(enemy,Math.atan2(dx,dz),1.8);turn(player,Math.atan2(-dx,-dz),3.5);// Keep a comfortable band instead of pursuing the player's body.
const cpuMods=Ab.mods(enemy),near=Math.max(enemyProfile().near,2.3*cpuMods.length),far=near+.8;
const itemTarget=!enemy.effect&&d>near?fieldItems.list
 .filter(item=>Math.hypot(item.x-enemy.x,item.z-enemy.z)<4&&segmentDistance(player,enemy,item)>=near)
 .sort((a,b)=>Math.hypot(a.x-enemy.x,a.z-enemy.z)-Math.hypot(b.x-enemy.x,b.z-enemy.z))[0]:null;
if(d<near){
 const step=Math.min(near-d,dt*enemyProfile().retreat*cpuMods.move);
 enemy.x-=dx/d*step;enemy.z-=dz/d*step;
}else if(enemy.wind<=0&&enemy.swing<=0){
 if(itemTarget){
  const ix=itemTarget.x-enemy.x,iz=itemTarget.z-enemy.z,len=Math.hypot(ix,iz)||1;
  const step=Math.min(len,dt*enemyProfile().speed*cpuMods.move);
  enemy.x+=ix/len*step;enemy.z+=iz/len*step;
 }else if(d>far){
  const step=Math.min(d-far,dt*enemyProfile().speed*cpuMods.move);
  enemy.x+=dx/d*step;enemy.z+=dz/d*step;
 }else if(enemyProfile().orbit&&d>near+.1){
  const orbit=enemyProfile().orbit*dt*Math.sin(time*.8);
  enemy.x+=dz/d*orbit;enemy.z-=dx/d*orbit;
 }
}
const attackRange=Math.max(far+.2,reach+1.8,2.1*cpuMods.length+.6);
if(enemy.wind>0){enemy.wind-=dt;if(enemy.wind<=0&&d<=attackRange)attack(enemy,true);}
else if(!itemTarget&&d<=attackRange&&enemy.cd<=0&&enemy.swing<=0)enemy.wind=enemyProfile().wind;


for(const p of [player,enemy]){p.bend*=Math.exp(-dt*3);p.fold=Math.min(1,p.fold+dt*2);p.cd=Math.max(0,p.cd-dt);p.flash=Math.max(0,p.flash-dt);p.deflect*=Math.exp(-dt*5);p.x=clamp(p.x+p.vx*dt,-ARENA.limit,ARENA.limit);p.z=clamp(p.z+p.vz*dt,-ARENA.limit,ARENA.limit);p.vx*=Math.exp(-dt*9);p.vz*=Math.exp(-dt*9);p.swing=Math.max(0,p.swing-dt);}
for(const pickup of fieldItems.step(dt,[player,enemy])){
 Sound.play('pickup');const p=pickup.fighter;for(let i=0;i<10;i++)particles.push({x:p.x,y:1,z:p.z,vx:(Math.random()-.5)*3,vy:Math.random()*3,vz:(Math.random()-.5)*3,life:.5});
}
const hitsBody=(p,target,isEnemy)=>Combat.active(p)&&weapon(p,isEnemy).some((q,i,w)=>i>0&&segmentDistance(target,w[i-1],q)<.43+weaponRadius(p,isEnemy));
const playerBody=hitsBody(player,enemy,false),enemyBody=hitsBody(enemy,player,true);
// During a swing, contact deals damage but cannot pin or cancel either weapon.
const swinging=player.swing>0||enemy.swing>0;
const colliding=swinging
 ?CushionPhysics.overlap(weapon(player,false),weapon(enemy,true),weaponRadius(player,false)+weaponRadius(enemy,true))>0
 :CushionPhysics.separate(player,enemy,weapon,weaponRadius);
if(colliding){
 const striking=Combat.active(player)||Combat.active(enemy);
 if(striking){
  const outgoing=Combat.active(player)&&!player.hit?Math.round(attackPower(player,false)*(playerBody?1:.5)):0;
  const incoming=Combat.active(enemy)&&!enemy.hit?Math.round(attackPower(enemy,true)*(enemyBody?1:.5)):0;
  const dealt=outgoing?dealDamage(enemy,outgoing):0,taken=incoming?dealDamage(player,incoming):0;
  if(outgoing){enemy.flash=.15;player.hit=true;}
  if(incoming){player.flash=.15;enemy.hit=true;}
  if(outgoing||incoming)sync();
  if((outgoing||incoming)&&clashCooldown<=0){Sound.play(playerBody||enemyBody?'body':'clash');clashCooldown=.35;const w=weapon(player,false),tip=w.at(-1);for(let i=0;i<10;i++)particles.push({x:tip.x,y:1,z:tip.z,vx:(Math.random()-.5)*4,vy:Math.random()*3,vz:(Math.random()-.5)*4,life:.4});}
 }
}
for(const [p,target,isEnemy]of[[player,enemy,false],[enemy,player,true]]){
 const w=weapon(p,isEnemy),r=weaponRadius(p,isEnemy);
 if(!p.hit&&Combat.active(p)&&w.some((q,i)=>i>0&&segmentDistance(target,w[i-1],q)<.43+r)){
  p.hit=true;const damage=dealDamage(target,attackPower(p,isEnemy));target.flash=.22;
  const a=Math.atan2(target.x-p.x,target.z-p.z);target.vx=Math.sin(a)*2.2;target.vz=Math.cos(a)*2.2;
  for(let i=0;i<12;i++)particles.push({x:target.x,y:1,z:target.z,vx:(Math.random()-.5)*5,vy:Math.random()*4,vz:(Math.random()-.5)*5,life:.6});Sound.play('body');sync();
 }
}
dx=enemy.x-player.x;dz=enemy.z-player.z;d=Math.hypot(dx,dz);if(d<.9){const a=d||1;if(!d)dx=1;player.x-=dx/a*(.9-d)/2;player.z-=dz/a*(.9-d)/2;enemy.x+=dx/a*(.9-d)/2;enemy.z+=dz/a*(.9-d)/2;}if(player.hp<=0||enemy.hp<=0){running=false;clearInputs();Sound.play(enemy.hp<=0?'win':'lose');$('result').hidden=false;$('resultTitle').textContent=enemy.hp<=0?(player.hp<=0?'DRAW!':'YOU WIN!'):'TRY AGAIN!';$('resultText').textContent='残りHP '+Math.ceil(player.hp)+' / 形を変えて戦い方を試そう。';$('status').textContent='対戦終了';showScreen('result');}}
// Perspective projection of true 3D polygon meshes, rendered back to front.
let faces=[],renderLayer=0,W=800,H=520;function project(p){const cx=p.x,cy=p.y-.1,cz=p.z;const yaw=.15,X=cx*Math.cos(yaw)-cz*Math.sin(yaw),Z=cx*Math.sin(yaw)+cz*Math.cos(yaw),Y=cy*.8-Z*.6,D=22-cy*.6-Z*.8,s=Math.min(W,H*(innerWidth>innerHeight&&innerHeight<=600?1.5:1))*1.2/D;return{x:W/2+X*s,y:H*.49-Y*s,d:D};}
function poly(points,color){const ps=points.map(project);faces.push({ps,color,layer:renderLayer,d:ps.reduce((a,p)=>a+p.d,0)/ps.length});}
function sphere(x,y,z,r,color){const rings=6,sides=10;for(let i=0;i<rings;i++)for(let j=0;j<sides;j++){const pts=[];for(const [a,b]of[[i,j],[i,j+1],[i+1,j+1],[i+1,j]]){const t=a/rings*Math.PI,v=b/sides*Math.PI*2;pts.push({x:x+Math.sin(t)*Math.cos(v)*r,y:y+Math.cos(t)*r,z:z+Math.sin(t)*Math.sin(v)*r});}poly(pts,shade(color,.68+.3*Math.sin(j/sides*Math.PI*2)+.13*Math.cos(i/rings*Math.PI)));}}
function shade(hex,f){const n=parseInt(hex.slice(1),16);return`rgb(${[n>>16,n>>8&255,n&255].map(c=>clamp(Math.round(c*f),0,255)).join(',')})`;}
function tube(a,b,r,color){const dx=b.x-a.x,dy=b.y-a.y,dz=b.z-a.z,len=Math.hypot(dx,dy,dz);if(len<.001)return;const ux=-dz/Math.hypot(dx,dz||.001),uz=dx/Math.hypot(dx,dz||.001);for(let i=0;i<8;i++){const pts=[];for(const [p,j]of[[a,i],[a,i+1],[b,i+1],[b,i]]){const t=j/8*Math.PI*2;pts.push({x:p.x+ux*Math.cos(t)*r,y:p.y+Math.sin(t)*r,z:p.z+uz*Math.cos(t)*r});}poly(pts,shade(color,.85+.22*Math.sin(i/8*Math.PI*2)));}}
function render(){if($('arena').hidden)return;const rect=scene.getBoundingClientRect(),ratio=Math.min(window.devicePixelRatio||1,2);W=rect.width;H=rect.height;if(scene.width!==Math.round(W*ratio)||scene.height!==Math.round(H*ratio)){scene.width=Math.round(W*ratio);scene.height=Math.round(H*ratio);}ctx.setTransform(ratio,0,0,ratio,0,0);ctx.fillStyle='#141a2a';ctx.fillRect(0,0,W,H);faces=[];renderLayer=0;const {edge,half}=ARENA;poly([{x:-half,y:-.16,z:-half},{x:half,y:-.16,z:-half},{x:half,y:-.16,z:half},{x:-half,y:-.16,z:half}],'#343c55');for(let i=-edge;i<=edge;i++){const c=i%2===0?'#424b65':'#3a435d';poly([{x:i,y:-.15,z:-edge},{x:i+.025,y:-.15,z:-edge},{x:i+.025,y:-.15,z:edge},{x:i,y:-.15,z:edge}],c);poly([{x:-edge,y:-.15,z:i},{x:edge,y:-.15,z:i},{x:edge,y:-.15,z:i+.025},{x:-edge,y:-.15,z:i+.025}],c);}for(const z of [-edge,edge])tube({x:-edge,y:0,z},{x:edge,y:0,z},.045,'#b29aff');for(const x of [-edge,edge])tube({x,y:0,z:-edge},{x,y:0,z:edge},.045,'#b29aff');
// Floor/grid/border are always behind fighters; depth-sort only within each layer.
renderLayer=1;
if(running||player)for(const item of fieldItems.list){
 const info={color:'#a8eaff'},y=.42+Math.sin(time*3+item.x)*.1;
 sphere(item.x,y,item.z,.23,info.color);
 tube({x:item.x,y:.02,z:item.z},{x:item.x,y:.19,z:item.z},.07,info.color);
}
const fighters=player?[player,enemy]:[fighter(-1.7,0),fighter(2,1)];if(!player){fighters[0].angle=Math.PI/2;fighters[1].angle=-Math.PI/2;}
fighters.forEach((p,i)=>{const c=p.flash>0?'#ffffff':i?enemyProfile().color:'#8d7aff';const lean=Combat.pose(p).lean; sphere(p.x,.55,p.z,.44,c);sphere(p.x+Math.sin(p.angle)*lean,1.28,p.z+Math.cos(p.angle)*lean,.33,c);for(const side of [-1,1]){sphere(p.x+side*.23,.13,p.z,.19,'#252c42');const a=p.angle; sphere(p.x+Math.sin(a)*.29+Math.cos(a)*side*.12,1.33,p.z+Math.cos(a)*.29-Math.sin(a)*side*.12,.055,'#191c31');}if(i&&p.profile===CushionEnemies.rock){for(const side of [-1,1])sphere(p.x+side*.27,1.49,p.z,.13,'#bdd8e9');}if(i&&p.profile===CushionEnemies.zip){for(const side of [-1,1])tube({x:p.x+side*.15,y:1.5,z:p.z},{x:p.x+side*.22,y:1.95,z:p.z},.075,p.profile.color);}if(i&&p.profile===CushionEnemies.curl)sphere(p.x,1.72,p.z,.14,'#f4c6ec');const w=weapon(p,!!i),r=weaponRadius(p,!!i),weaponColor=p.effect?Ab.items[p.effect].color:i?enemyProfile().weaponColor:$('color').value;for(const face of CushionPhysics.tubeMesh(w,r))poly(face.points,shade(i&&p.wind>0?'#ff435d':weaponColor,face.light));});
for(const p of particles)sphere(p.x,p.y,p.z,.06,'#d6ff95');faces.sort((a,b)=>a.layer-b.layer||b.d-a.d);for(const f of faces){ctx.fillStyle=f.color;ctx.beginPath();f.ps.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();ctx.fill();}
ctx.save();ctx.textAlign='center';ctx.font='bold 14px system-ui';ctx.lineWidth=3;
for(const n of damageNumbers){const at=project(n);ctx.globalAlpha=Math.min(1,n.life/.2);ctx.strokeStyle='#111725';ctx.fillStyle=n.player?'#ffad9d':'#e5ffc8';const label=String(n.damage);ctx.strokeText(label,at.x,at.y);ctx.fillText(label,at.x,at.y);}
ctx.restore();
}
function frame(t){const dt=Math.min((t-last)/1000||0,.035);last=t;for(let remaining=dt;remaining>0;){const step=Math.min(remaining,1/240);tick(step);remaining-=step;}if(!paused){stepDamageNumbers(dt);for(let i=particles.length-1;i>=0;i--){const p=particles[i];p.life-=dt;p.x+=p.vx*dt;p.y+=p.vy*dt;p.z+=p.vz*dt;p.vy-=9*dt;if(p.life<=0)particles.splice(i,1);}}syncItems();syncAttackButtons();render();requestAnimationFrame(frame);}sample();syncItems();syncAttackButtons();showScreen('draw','replace',false);requestAnimationFrame(frame);
})();
