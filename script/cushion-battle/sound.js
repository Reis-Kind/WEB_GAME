'use strict';
window.CushionSound = (() => {
 let context,master,analyser,enabled=true,muted=false,played=0;
 try{enabled=localStorage.getItem('cushion-sound')!=='off';}catch{}
 function volume(){if(master)master.gain.setValueAtTime(enabled&&!muted?.12:0,context.currentTime);}
 async function unlock(){
  if(!enabled)return false;
  try{
   const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return false;
   if(!context){context=new Audio();master=context.createGain();analyser=context.createAnalyser();master.connect(analyser);analyser.connect(context.destination);volume();}
   if(context.state!=='running')await context.resume();return context.state==='running';
  }catch{return false;}
 }
 function tone(frequency,duration,type='sine',delay=0,end=frequency){
  const start=context.currentTime+delay,o=context.createOscillator(),g=context.createGain();
  o.type=type;o.frequency.setValueAtTime(frequency,start);o.frequency.exponentialRampToValueAtTime(Math.max(30,end),start+duration);
  g.gain.setValueAtTime(.001,start);g.gain.exponentialRampToValueAtTime(.45,start+.008);g.gain.exponentialRampToValueAtTime(.001,start+duration);
  o.connect(g);g.connect(master);o.start(start);o.stop(start+duration+.02);o.onended=()=>{o.disconnect();g.disconnect();};
 }
 function play(id){
  if(!enabled||muted||!context||context.state!=='running')return;
  played++;
  if(id==='thrust')tone(400,.11,'triangle',0,110);
  else if(id==='sweep')tone(650,.2,'triangle',0,90);
  else if(id==='heavy'){tone(130,.28,'triangle',0,40);tone(650,.12,'sine');}
  else if(id==='body'){tone(110,.18,'triangle',0,35);tone(70,.22);}
  else if(id==='clash'){tone(700,.1,'triangle',0,220);tone(950,.09,'sine',.025,360);}
  else if(id==='charge')tone(220,.12,'sine',0,440);
  else if(id==='ready'){tone(660,.12);tone(880,.15,'sine',.08);}
  else if(id==='pickup'||id==='start'){tone(440,.12);tone(660,.12,'sine',.08);tone(880,.18,'sine',.16);}
  else if(id==='win'){[523,659,784,1046].forEach((f,i)=>tone(f,.25,'sine',i*.13));}
  else if(id==='lose'){[330,294,220].forEach((f,i)=>tone(f,.3,'triangle',i*.16));}
 }
 function setEnabled(value){enabled=value;try{localStorage.setItem('cushion-sound',value?'on':'off');}catch{}volume();}
 function setMuted(value){muted=value;volume();}
 function level(){if(!analyser)return 0;const data=new Float32Array(analyser.fftSize);analyser.getFloatTimeDomainData(data);return Math.max(...data.map(Math.abs));}
 return {unlock,play,setEnabled,setMuted,level,get enabled(){return enabled;},get state(){return {context:context?.state||'unavailable',played,muted};}};
})();
