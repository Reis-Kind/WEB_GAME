'use strict';
window.CushionFieldItems = class {
  constructor(random=Math.random){this.random=random;this.list=[];this.timer=4;}
  reset(fighters){
    this.list=[];this.timer=4;
    for(let i=0;i<3;i++)this.spawn(fighters);
  }
  spawn(fighters){
    if(this.list.length>=3)return false;
    for(let attempt=0;attempt<40;attempt++){
      const x=(this.random()*2-1)*5.4,z=(this.random()*2-1)*5.4;
      if(fighters.some(p=>Math.hypot(p.x-x,p.z-z)<1.5)||this.list.some(p=>Math.hypot(p.x-x,p.z-z)<1.5))continue;
      this.list.push({x,z,life:18});return true;
    }
    return false;
  }
  step(dt,fighters){
    for(const item of this.list)item.life-=dt;
    this.list=this.list.filter(item=>item.life>0);
    const pickups=[];
    for(let i=this.list.length-1;i>=0;i--){
      const item=this.list[i];let collector=null,distance=.75;
      for(const p of fighters){const d=Math.hypot(p.x-item.x,p.z-item.z);if(p.hp>0&&d<distance){collector=p;distance=d;}}
      if(collector){
        const effect=['inflate','stretch','retract'][Math.min(2,Math.floor(this.random()*3))];
        if(CushionAbilities.collect(collector,effect)){this.list.splice(i,1);pickups.push({fighter:collector,item,effect});}
      }
    }
    this.timer-=dt;
    if(this.timer<=0){this.spawn(fighters);this.timer=4;}
    return pickups;
  }
};
