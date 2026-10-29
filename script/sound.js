// Tiny synthesized effects: no downloads, music loop, or external audio assets.
const noiseBuffers=new WeakMap();
function noiseBuffer(ctx){
  if(!noiseBuffers.has(ctx)){
    const buffer=ctx.createBuffer(1,Math.ceil(ctx.sampleRate*.12),ctx.sampleRate),data=buffer.getChannelData(0);
    for(let i=0;i<data.length;i++)data[i]=Math.random()*2-1;
    noiseBuffers.set(ctx,buffer);
  }
  return noiseBuffers.get(ctx);
}
export function scheduleSound(ctx,output,kind,damage=0){
  const now=ctx.currentTime+.005;
  function tone(frequency,end,duration,volume=.1,type='sine',offset=0){
    const oscillator=ctx.createOscillator(),gain=ctx.createGain(),start=now+offset;
    oscillator.type=type;oscillator.frequency.setValueAtTime(frequency,start);
    oscillator.frequency.exponentialRampToValueAtTime(Math.max(30,end),start+duration);
    gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(volume,start+.008);
    gain.gain.exponentialRampToValueAtTime(.0001,start+duration);
    oscillator.connect(gain);gain.connect(output);oscillator.start(start);oscillator.stop(start+duration+.02);
    oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();};
  }
  switch(kind){
    case 'cutin':tone(260,720,.18,.12,'triangle');tone(720,520,.12,.065,'sine',.07);break;
    case 'hit':{
      if(damage<=0){tone(450,250,.17,.045);break;}
      tone(320+Math.min(30,damage)*3,110,.24,.16,'triangle');
      const source=ctx.createBufferSource(),filter=ctx.createBiquadFilter(),gain=ctx.createGain();
      source.buffer=noiseBuffer(ctx);filter.type='lowpass';filter.frequency.value=1600;
      gain.gain.setValueAtTime(.08,now);gain.gain.exponentialRampToValueAtTime(.0001,now+.1);
      source.connect(filter);filter.connect(gain);gain.connect(output);source.start(now);source.stop(now+.12);
      source.onended=()=>{source.disconnect();filter.disconnect();gain.disconnect();};break;
    }
    case 'win':[523,659,784,1047].forEach((n,i)=>tone(n,n,.2,.065,'triangle',i*.11));break;
    case 'lose':[392,330,262].forEach((n,i)=>tone(n,n*.95,.22,.05,'triangle',i*.15));break;
    case 'draw':tone(523,523,.2,.055,'triangle');tone(659,659,.25,.04,'triangle',.18);break;
    case 'tap':tone(660,880,.18,.12);break;
  }
}
export class SoundEffects{
  constructor(button){
    this.button=button;this.enabled=true;this.context=null;this.master=null;
    try{this.enabled=localStorage.getItem('kao-sound')!=='off';}catch{}
    const unlock=()=>{if(this.enabled)this.unlock();};
    for(const event of ['pointerdown','touchend','click','keydown'])document.addEventListener(event,unlock,{passive:true});
    document.addEventListener('visibilitychange',()=>{if(this.master)this.master.gain.value=document.hidden||!this.enabled?0:.9;});
    button.onclick=async()=>{
      this.enabled=!this.enabled;
      try{localStorage.setItem('kao-sound',this.enabled?'on':'off');}catch{}
      this.update();if(this.enabled)await this.play('tap');
    };
    this.update();
  }
  update(){
    this.button.textContent=this.enabled?'🔊':'🔇';
    this.button.setAttribute('aria-pressed',String(this.enabled));
    this.button.setAttribute('aria-label',this.enabled?'効果音をオフにする':'効果音をオンにする');
    this.button.title=this.enabled?'効果音 ON':'効果音 OFF';
    if(this.master)this.master.gain.value=this.enabled&&!document.hidden ? .9 : 0;
  }
  async unlock(){
    try{
      const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return false;
      if(!this.context||this.context.state==='closed'){
        this.context=new Audio();this.master=this.context.createGain();this.master.connect(this.context.destination);this.update();
      }
      // Safari can also use "interrupted" after calls or switching applications.
      if(this.context.state!=='running'){
        let timer;
        try{await Promise.race([this.context.resume(),new Promise(resolve=>{timer=setTimeout(resolve,900);})]);}
        finally{clearTimeout(timer);}
      }
      return this.context.state==='running';
    }catch{return false;}
  }
  async play(kind,damage=0){
    if(!this.enabled||document.hidden)return false;
    const requested=performance.now();
    // Wait for resume instead of silently dropping the first effect.
    if(!await this.unlock()||!this.enabled||document.hidden||performance.now()-requested>1000)return false;
    try{scheduleSound(this.context,this.master,kind,damage);return true;}catch{return false;}
  }
  async test(){
    this.enabled=true;
    try{localStorage.setItem('kao-sound','on');}catch{}
    this.update();return this.play('win');
  }
}
