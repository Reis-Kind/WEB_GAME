// A quiet original 8-bar loop, synthesized locally with soft plucked notes.
const loops=new WeakMap();
export function musicBuffer(ctx){
  if(loops.has(ctx))return loops.get(ctx);
  const beat=60/96,duration=32*beat,buffer=ctx.createBuffer(1,Math.round(ctx.sampleRate*duration),ctx.sampleRate),data=buffer.getChannelData(0);
  function note(midi,start,length,level){
    const frequency=440*2**((midi-69)/12),offset=Math.round(start*ctx.sampleRate),count=Math.ceil(length*ctx.sampleRate);
    for(let i=0;i<count;i++){
      const t=i/ctx.sampleRate,attack=Math.min(1,t/.018),release=Math.min(1,(length-t)/.08),envelope=attack*release*Math.exp(-t*5/length);
      const phase=2*Math.PI*frequency*t;
      data[(offset+i)%data.length]+=level*envelope*(Math.sin(phase)+.14*Math.sin(phase*2));
    }
  }
  const melody=[72,null,76,79,null,76,74,null,71,null,74,79,null,74,72,null,69,null,72,76,null,72,69,null,67,null,71,74,null,71,67,null];
  const bass=[48,48,43,43,45,45,43,43];
  melody.forEach((pitch,i)=>{if(pitch!==null)note(pitch,i*beat,.36,.035);});
  bass.forEach((pitch,bar)=>{note(pitch,bar*4*beat,.65,.024);note(pitch+7,(bar*4+2)*beat,.4,.015);});
  loops.set(ctx,buffer);return buffer;
}
export class BackgroundMusic{
  constructor(sounds,button){
    this.sounds=sounds;this.button=button;this.enabled=true;this.source=null;this.gain=null;this.starting=false;this.revision=0;
    try{this.enabled=localStorage.getItem('kao-bgm')!=='off';}catch{}
    const start=()=>this.start();
    for(const event of ['pointerdown','touchend','click','keydown'])document.addEventListener(event,start,{passive:true});
    document.addEventListener('visibilitychange',()=>{if(document.hidden)this.stop();else if(this.sounds.context)this.start();});
    button.onclick=()=>{
      this.enabled=!this.enabled;
      try{localStorage.setItem('kao-bgm',this.enabled?'on':'off');}catch{}
      this.update();if(this.enabled)this.start();else this.stop();
    };
    this.update();
  }
  update(){
    this.button.textContent='♫';
    this.button.setAttribute('aria-pressed',String(this.enabled));
    this.button.setAttribute('aria-label',this.enabled?'BGMをオフにする':'BGMをオンにする');
    this.button.title=this.enabled?'BGM ON':'BGM OFF';
  }
  async start(){
    if(!this.enabled||document.hidden||this.starting)return;
    this.starting=true;const revision=this.revision;
    try{
      if(!await this.sounds.unlock()||revision!==this.revision||!this.enabled||document.hidden)return;
      if(this.source)return;
      const ctx=this.sounds.context,source=ctx.createBufferSource(),gain=ctx.createGain();
      source.buffer=musicBuffer(ctx);source.loop=true;
      gain.gain.setValueAtTime(0,ctx.currentTime);gain.gain.linearRampToValueAtTime(.5,ctx.currentTime+.4);
      source.connect(gain);gain.connect(ctx.destination);source.start();
      this.source=source;this.gain=gain;
      source.onended=()=>{source.disconnect();gain.disconnect();};
    }catch{/* Music failure must never interrupt a battle. */}
    finally{this.starting=false;}
  }
  stop(){
    this.revision++;
    if(this.source){
      const ctx=this.sounds.context;this.gain.gain.cancelScheduledValues(ctx.currentTime);
      this.gain.gain.setTargetAtTime(0,ctx.currentTime,.012);this.source.stop(ctx.currentTime+.06);
      this.source=null;this.gain=null;
    }
  }
}
