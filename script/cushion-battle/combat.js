'use strict';
window.CushionCombat = (() => {
  const moves={
    thrust:{name:'つき',duration:.28,damage:.9,recovery:.8},
    sweep:{name:'なぎ払い',duration:.44,damage:1.2,recovery:1.05},
    heavy:{name:'ため打ち',duration:.65,damage:1.9,recovery:1.5}
  };
  function launch(p,type,baseCooldown){
    if(p.cd>0||p.swing>0||!moves[type])return false;
    const move=moves[type];p.fold=1;p.bend=0;p.deflect=0;p.move=type;p.swingDuration=move.duration;p.swing=move.duration;p.hit=false;p.cd=baseCooldown*move.recovery;return true;
  }
  function progress(p){return p.swing>0?1-p.swing/(p.swingDuration||.36):0;}
  function pose(p){
    if(!p.swing)return {angle:0,length:1,lean:0};
    const t=progress(p),pulse=Math.sin(t*Math.PI);
    if(p.move==='thrust')return {angle:0,length:1+pulse*.28,lean:pulse*.15};
    if(p.move==='heavy')return {angle:-1.3+t*2.6,length:1+pulse*.12,lean:pulse*.24};
    return {angle:-.9+t*1.8,length:1,lean:pulse*.1};
  }
  function active(p){const t=progress(p);return p.swing>0&&t>=.13&&t<=.86;}
  return {moves,launch,pose,active};
})();
