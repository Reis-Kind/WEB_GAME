'use strict';
window.CushionAbilities = (() => {
  const builds = {
    balanced: {name:'バランス', hp:200, defense:.08, move:3.86},
    speedy: {name:'スピード', hp:170, defense:0, move:4.83},
    tank: {name:'タフ', hp:280, defense:.25, move:3.24}
  };
  const items = {
    inflate: {name:'ふくらむ', icon:'●', color:'#ff7676', description:'太さ×1.7・威力×1.5', duration:6, length:.95, radius:1.7, damage:1.5, move:.82},
    stretch: {name:'のびる', icon:'↔', color:'#8ce7ff', description:'長さ×1.65・威力×0.9', duration:6, length:1.65, radius:.85, damage:.9, move:.95},
    retract: {name:'ちぢむ', icon:'»', color:'#c7f88c', description:'長さ半分・移動×1.5', duration:5, length:.5, radius:.85, damage:.8, move:1.5}
  };
  function init(p, build='balanced') {
    p.build=builds[build]||builds.balanced;p.maxHP=p.hp=p.build.hp;
    p.effect=null;p.effectTime=0;
    p.bend=0;p.fold=1;
    return p;
  }
  function collect(p,id) {
    if(!items[id]||p.hp<=0)return false;
    p.effect=id;p.effectTime=items[id].duration;
    return true;
  }
  function step(p,dt) {
    p.effectTime=Math.max(0,p.effectTime-dt);if(!p.effectTime)p.effect=null;
  }
  function mods(p) {return p.effect?items[p.effect]:{length:1,radius:1,damage:1,move:1};}
  function damage(p,amount) {const n=Math.max(1,Math.round(amount*(1-p.build.defense)));p.hp=Math.max(0,p.hp-n);return n;}
  function movement(p) {return p.build.move*mods(p).move;}
  return {builds,items,init,collect,step,mods,damage,movement};
})();

'use strict';
window.CushionEnemies = {
 pop:{name:'ポップ',description:'HP200。ほどよい距離でなぎ払いを使う、基本の相手。',hp:200,defense:.08,damage:17,interval:1.3,wind:.65,speed:2.16,retreat:.9,near:2.8,move:'sweep',color:'#ff9c7c',weaponColor:'#ffbe99',radius:.23,orbit:0,shape:[[0,0],[.25,.8],[.1,1.7],[-.3,2.1]]},
 rock:{name:'ロック',description:'HP300。動きはゆっくり。太いクッションで、予告の長いため打ち。',hp:300,defense:.22,damage:24,interval:1.9,wind:.95,speed:1.7,retreat:.9,near:3.1,move:'heavy',color:'#91b9d9',weaponColor:'#bdd8e9',radius:.34,orbit:0,shape:[[0,0],[0,.7],[.15,1.5],[.05,2.15]]},
 zip:{name:'ジップ',description:'HP160。横へ回り込みながら、細いクッションで素早くつく。',hp:160,defense:0,damage:13,interval:1.05,wind:.55,speed:2.6,retreat:1.2,near:3,move:'thrust',color:'#c7ed86',weaponColor:'#e0f9ad',radius:.17,orbit:.85,shape:[[0,0],[0,.8],[.05,1.6],[0,2.25]]},
 curl:{name:'カール',description:'HP210。少し離れて動き、曲がったクッションでなぎ払う。',hp:210,defense:.08,damage:18,interval:1.45,wind:.75,speed:2,retreat:1.1,near:3.4,move:'sweep',color:'#e6a4e1',weaponColor:'#f4c6ec',radius:.22,orbit:.5,shape:[[0,0],[0,.8],[.15,1.7],[.7,2.2],[1.05,1.9],[.75,1.5]]}
};
