import {FaceMesh} from './face-mesh.js?v=contour-2';
import {ENEMIES, chooseEnemy} from './enemies.js?v=contour-2';
import {Drawing} from './drawing.js';
import {Battle} from './game.js';
import {BackgroundMusic} from './music.js';
import {SoundEffects} from './sound.js?v=2';
import {setupRankings} from './rankings.js?v=1';
import {DemoJudge} from './judge.js';
import {connectModel} from './local-judge.js';
import {configuredGPT} from './gpt-judge.js';
import {configuredGemini} from './gemini-judge.js';
const $ = id => document.getElementById(id);
const sounds = new SoundEffects($('sound-toggle'));
new BackgroundMusic(sounds,$('music-toggle'));
$('sound-test').onclick = async () => {
  $('sound-test').disabled=true;
  const played=await sounds.test();
  $('sound-feedback').textContent=played?'♪ テスト音を再生しました':'音を開始できません。もう一度タップしてください。';
  $('sound-test').disabled=false;
};
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
let battle, busy = false;
let rankings = null;
let preparing = false;
let enemy = ENEMIES[0];
$('title-face').src = ENEMIES[0].image;
$('cpu-face').src = enemy.image;
$('cpu-face').alt = enemy.description;
$('cpu-name').textContent = enemy.name;
for (const item of ENEMIES) {
  const option = document.createElement('option'); option.value = item.id; option.textContent = item.name; $('enemy-select').append(option);
}
$('enemy-select').onchange = () => {
  const item = ENEMIES.find(item => item.id === $('enemy-select').value);
  $('enemy-description').textContent = item ? item.description : '個性豊かな6人から、前回と違う相手が登場します。';
};
let setupBusy = true;
let judge = null;
function judgeReady() { return Boolean(judge); }
function judgeLabel() { return judge instanceof DemoJudge ? 'デモ判定' : judge.label || 'ローカルLLM判定'; }
let previewFrame = 0;
let previewUpdatedAt = 0;
const drawing = new Drawing($('drawing'), d => {
  $('start').disabled = setupBusy || preparing || !d.hasInk || d.pointer !== null || !judgeReady();
  $('undo').disabled = !d.past.length || d.pointer !== null;
  $('clear').disabled = !d.strokes.length || d.pointer !== null;
  $('canvas-hint').hidden = d.hasInk;
  if (d.pointer === null) {
    cancelAnimationFrame(previewFrame); previewFrame = 0;
    if (d.hasInk) $('preview-face').src = d.image(384);
    else $('preview-face').removeAttribute('src');
    $('preview-face').hidden = !d.hasInk;
    document.querySelector('.preview-empty').hidden = d.hasInk;
    $('preview-caption').textContent = d.hasInk ? ($('preview-face').dataset.rendering === 'flat' ? 'この端末では通常のプレビューを表示します。' : '輪郭を読み取っています…') : '輪郭をぐるっと閉じて描こう。';
  }
  $('start-help').textContent = !judgeReady() ? '採点の準備ができていません。時間をおいて再読み込みしてください。' : d.hasInk ? '準備OK！ その顔で、ひと勝負。' : '顔を描くと、バトルを始められます';
});
// Update during a stroke, while limiting PNG encoding work on phones.
drawing.onRender = d => {
  if (d.pointer === null || previewFrame) return;
  const refresh = timestamp => {
    if (timestamp - previewUpdatedAt < 66) { previewFrame = requestAnimationFrame(refresh); return; }
    previewFrame = 0; previewUpdatedAt = timestamp;
    $('preview-face').src = d.image(256);
    $('preview-face').hidden = false;
    document.querySelector('.preview-empty').hidden = true;
  };
  previewFrame = requestAnimationFrame(refresh);
};
function tool(name) {
  if(drawing.pointer!==null)return;
  drawing.tool = name;
  $('drawing-tool-help').textContent={pen:'自由に描く',eraser:'なぞって消す',bucket:'閉じた部分をタップして塗る',line:'ドラッグで直線',circle:'ドラッグで丸・楕円',picker:'絵の色をタップして取る'}[name];
  for (const id of ['pen', 'eraser', 'bucket', 'line', 'circle', 'picker']) { $(id).classList.toggle('selected', id === name); $(id).setAttribute('aria-pressed', String(id === name)); }
}
$('pen').onclick = () => tool('pen');
for(const name of ['eraser','bucket','line','circle','picker'])$(name).onclick=()=>tool(name);
drawing.onPickColor=color=>{chooseColor(color);tool('pen');};
for (const [color, label] of [['#292d36','すみ色'],['#f96840','オレンジ'],['#427fa8','青'],['#459a7a','緑'],['#af72b1','紫']]) {
  const button = document.createElement('button');
  button.className = 'swatch'; button.style.background = color;
  button.setAttribute('aria-label', label); button.setAttribute('aria-pressed', String(color === drawing.color));
  button.dataset.color = color;
  button.onclick = () => chooseColor(color);
  $('colors').append(button);
}
function chooseColor(color) {
  drawing.color = color;
  if(drawing.tool==='eraser'||drawing.tool==='picker')tool('pen');
  $('custom-color').value=color;
  document.querySelectorAll('.swatch').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.color === color)));
}
$('custom-color').oninput = e => chooseColor(e.target.value);
$('size').oninput = e => { drawing.size = Number(e.target.value); $('size-label').value = e.target.value; };
$('undo').onclick = () => drawing.undo();
$('clear').onclick = () => drawing.clear();
function showScreen(name, record = true) {
  if(record && history.state?.faceScreen !== name) history.pushState({faceScreen:name}, '', location.href);
  for(const screen of ['title','rules','difficulty','draw','battle','result','ranking','ranking-log']) $(screen+'-screen').hidden = screen !== name;
  document.body.classList.toggle('in-battle', name === 'battle');
  document.body.dataset.screen = name;
  window.scrollTo({top:0,behavior:'instant'});
  const heading=$(name+'-screen').querySelector('h1,h2');
  if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true});}
}
function step(name) { showScreen(name); for (const id of ['draw','battle','result']) $('step-' + id).classList.toggle('active', id === name); }
$('show-rules').onclick = () => showScreen('rules');
$('rules-back').onclick = () => showScreen('title');
$('begin-drawing').onclick = () => showScreen('difficulty');
$('difficulty-back').onclick = () => showScreen('rules');
$('confirm-difficulty').onclick = () => {showScreen('draw');drawing.check();};
for(const button of document.querySelectorAll('[data-difficulty]')) button.onclick = () => {
  $('difficulty').value = button.dataset.difficulty;
  for(const choice of document.querySelectorAll('[data-difficulty]'))choice.setAttribute('aria-pressed', String(choice===button));
};
$('draw-back').onclick = () => {if(!preparing&&drawing.pointer===null)showScreen('difficulty');};
$('back-title').onclick = () => {if(!busy&&!preparing)showScreen('title');};
document.querySelector('.brand').onclick = event => {event.preventDefault();if(!busy&&!preparing&&drawing.pointer===null)showScreen('title');};
history.replaceState({faceScreen:'title'}, '', location.href);
showScreen('title', false);
window.addEventListener('popstate', event => {
  if(busy || preparing || drawing.pointer !== null){history.go(1);return;}
  let target = event.state?.faceScreen || 'title';
  if(!['title','rules','difficulty','draw','battle','result','ranking','ranking-log'].includes(target))target='title';
  if(target==='battle' && (!battle || battle.finished))target=battle?.finished?'result':'draw';
  if(target==='result' && !battle?.finished)target='draw';
  showScreen(target, false);
});
function hp(side, value) { $(side + '-hp').replaceChildren(document.createTextNode(`${value} `)); const small = document.createElement('small'); small.textContent = '/ 100'; $(side + '-hp').append(small); $(side + '-bar').value = value; }
async function start(newEnemy = false) {
  if (setupBusy || !drawing.hasInk || drawing.pointer !== null || busy || preparing || !judgeReady()) return;
  preparing=true;
  try {
  if (newEnemy) {
    setupBusy = true; $('start').disabled = true; $('rematch').disabled = true; $('next-enemy').disabled = true;
    try {
      enemy = chooseEnemy($('enemy-select').value, enemy.id);
      $('cpu-face').src = enemy.image;
      await $('cpu-face').decode();
      $('cpu-face').alt = enemy.description;
      $('cpu-name').textContent = enemy.name;
      document.querySelector('label[for="attack"]').textContent = `${enemy.name}の顔を、何かにたとえてみよう。`;
      $('attack').placeholder = enemy.hint;
    } catch {
      $('connection-status').textContent = '敵の画像を読み込めませんでした。もう一度お試しください。';
      $('battle-error').textContent = '敵の画像を読み込めませんでした。';
      return;
    } finally {
      setupBusy = false; $('rematch').disabled = false; $('next-enemy').disabled = false; drawing.check();
    }
  }
  const imageSize = judge.label ? 384 : 640;
  const displayImage = drawing.image();
  const cpuCanvas = document.createElement('canvas'); cpuCanvas.width = cpuCanvas.height = imageSize;
  const ctx = cpuCanvas.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, imageSize, imageSize);
  if (!$('cpu-face').complete || !$('cpu-face').naturalWidth) { $('connection-status').textContent = 'CPUの画像を読み込み中です。少し待って再度お試しください。'; return; }
  ctx.drawImage($('cpu-face'), 0, 0, imageSize, imageSize);
  const selectedDifficulty=newEnemy ? $('difficulty').value : battle?.difficulty || $('difficulty').value;
  const playerImage=drawing.image(imageSize),cpuImage=cpuCanvas.toDataURL('image/png');
  const expectedMode=judge instanceof DemoJudge?'demo':judge.label==='Gemini判定'?'gemini':judge.label==='GPT判定'?'gpt':'local';
  $('start-help').textContent='対戦の準備中…';
  const rankedJudge=await rankings.begin(judge,{playerImage,cpuImage,difficulty:selectedDifficulty,enemy:enemy.id},expectedMode);
  battle = new Battle(rankedJudge, playerImage, cpuImage, selectedDifficulty);
  battle.totalDamage=0;
  $('result-review').open=false;$('result-log').replaceChildren();
  const label = judgeLabel();
  document.querySelector('.battle-top .badge').textContent = label;
  document.querySelector('.battle-note').textContent = judge instanceof DemoJudge ? '✳ デモ判定：画像は解析しません。CPUは定型文です。' : `✳ ${judge.model}：${judge.vision ? '画像対応モデルに顔画像を渡します。' : 'テキスト専用判定。顔画像は解析しません。'} ${judge.label ? judge.notice || '顔画像と発言をOpenAIに送信します（API従量課金）。' : '採点とCPUの返答をローカルで生成します。'}`;
  $('player-face').src = displayImage;
  $('player-bubble').textContent = '';
  $('cpu-bubble').textContent = '';
  $('draw-screen').hidden = true; $('battle-screen').hidden = false;
  $('result').hidden = true; $('attack-form').hidden = false;
  $('turn-title').textContent = 'あなたのツッコミ！'; $('turn-status').textContent = 'あなたの番';
  $('battle-error').textContent = ''; $('judge-time').textContent = ''; $('round').textContent = 'ROUND 1 / 3';
  $('log').replaceChildren(); const p = document.createElement('p'); p.className = 'log-empty'; p.textContent = `バトル開始！ CPUの強さ：${{easy:'やさしい',normal:'ふつう',hard:'ガチ'}[battle.difficulty]}。最初のツッコミをどうぞ。`; $('log').append(p);
  $('attack').value = ''; $('attack').disabled = false;
  hp('player', 100); hp('cpu', 100); step('battle'); updateInput();
  $('battle-screen').scrollIntoView({block: 'start', behavior: 'smooth'}); focusAttack();
  } finally {preparing=false;drawing.check();}
}
$('start').onclick = () => start(true); $('rematch').onclick = () => start();
$('next-enemy').onclick = () => { $('enemy-select').value = 'random'; $('enemy-select').onchange(); start(true); };
$('redraw').onclick = () => { if (busy) return; $('battle-screen').hidden = true; $('draw-screen').hidden = false; step('draw'); $('draw-screen').scrollIntoView({behavior: 'smooth'}); };
function focusAttack() { if(!matchMedia('(pointer:coarse)').matches)$('attack').focus({preventScroll:true}); }
function updateInput() {
  $('counter').textContent = `${Array.from($('attack').value).length} / 120`;
  $('submit').disabled = busy || !battle || battle.finished || !$('attack').value.trim();
  $('submit').classList.toggle('is-waiting', busy);
  $('submit').setAttribute('aria-label', busy ? '攻撃を処理中' : '攻撃する');
}
$('attack').oninput = updateInput;
function log(actor, result, round) {
  $(actor + '-bubble').textContent = result.text;
  $('log').querySelector('.log-empty')?.remove();
  const entry = document.createElement('article'); entry.className = 'log-entry';
  const header = document.createElement('header');
  const name = document.createElement('span'); name.textContent = `ROUND ${round} · ${actor === 'player' ? 'あなた' : `CPU・${enemy.name}`}`;
  const score = document.createElement('b'); score.textContent = `${result.damage} ダメージ`;
  header.append(name, score);
  const quote = document.createElement('blockquote'); quote.textContent = result.text;
  const reason = document.createElement('p'); reason.textContent = `${judgeLabel()}：${result.reason}${actor === 'cpu' && judge instanceof DemoJudge ? '（定型のCPU発言）' : ''}`;
  entry.append(header, quote, reason); $('log').append(entry); $('log').scrollTop = $('log').scrollHeight;
}
async function cutin(actor, text) {
  const overlay = $('attack-cutin');
  $('cutin-face').src = $(actor + '-face').src;
  $('cutin-text').textContent = text;
  overlay.dataset.actor = actor;
  overlay.hidden = false;
  overlay.setAttribute('aria-hidden', 'false');
  document.body.classList.add('showing-cutin');
  sounds.play('cutin');
  try {
    // Keep the line readable before any HP/damage presentation changes.
    await wait(Math.max(2500, Math.min(5000, Array.from(text).length * 65)));
  } finally {
    overlay.hidden = true;
    overlay.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('showing-cutin');
  }
}
async function hit(side, damage, value) {
  const card = $(side + '-card');
  const attacker = $(side === 'cpu' ? 'player-card' : 'cpu-card');
  attacker.classList.add('striking');
  card.dataset.damage = damage;
  sounds.play('hit', damage);
  card.querySelector('.damage').textContent = `−${damage}`;
  card.classList.remove('hit'); void card.offsetWidth; card.classList.add('hit'); hp(side, value);
  await wait(1100); card.classList.remove('hit'); attacker.classList.remove('striking');
}
$('attack-form').onsubmit = async e => {
  e.preventDefault(); if (busy || !battle || battle.finished || !$('attack').value.trim()) return;
  if(matchMedia('(pointer:coarse)').matches)$('attack').blur();
  busy = true; $('attack').disabled = true; updateInput();
  $('battle-error').textContent = ''; $('turn-status').textContent = `${judgeLabel()}中…`; $('attack-panel')?.setAttribute('aria-busy', 'true');
  const started = performance.now();
  document.body.classList.add('is-judging');
  $('judge-time').textContent = '採点中…';
  const waitTimer = setInterval(() => { $('judge-time').textContent = $('turn-status').textContent = `採点中… ${Math.floor((performance.now() - started) / 1000)}秒`; }, 1000);
  // Present the player's own submitted line while the score is being computed.
  // HP and damage remain unchanged until both the score and cut-in are ready.
  const playerCutin = cutin('player', $('attack').value.trim());
  try {
    const turn = await battle.play($('attack').value);
    clearInterval(waitTimer);
    document.body.classList.remove('is-judging');
    document.body.dataset.judgeMs=String(Math.round(performance.now()-started));
    if (!turn) return;
    battle.totalDamage += turn.player.damage;
    $('judge-time').textContent = `今回の判定：${((performance.now() - started) / 1000).toFixed(1)}秒`;
    $('turn-status').textContent = 'あなたの攻撃';
    log('player', turn.player, turn.round);
    await playerCutin;
    await hit('cpu', turn.player.damage, turn.hp.cpu);
    $('turn-status').textContent = 'CPUの番'; $('turn-title').textContent = `${enemy.name}のツッコミ！`;
    log('cpu', turn.cpu, turn.round);
    await cutin('cpu', turn.cpu.text);
    await hit('player', turn.cpu.damage, turn.hp.player);
    if (turn.finished) {
      $('attack-form').hidden = true; $('result').hidden = false; $('turn-title').textContent = '決着！'; $('turn-status').textContent = '対戦終了';
      $('round').textContent = 'FINISH · 3 / 3';
      $('result-title').textContent = {player:'あなたの勝ち！', cpu:`${enemy.name}の勝ち！`, draw:'仲良く、引き分け！'}[turn.winner];
      $('result-detail').textContent = `あなた ${turn.hp.player} HP ／ ${enemy.name} ${turn.hp.cpu} HP`;
      sounds.play({player:'win',cpu:'lose',draw:'draw'}[turn.winner]);
      $('result-log').replaceChildren(...[...$('log').querySelectorAll('.log-entry')].map(entry=>entry.cloneNode(true)));
      rankings.finish(battle.totalDamage);
      step('result');
      if(!matchMedia('(pointer:coarse)').matches)$('rematch').focus({preventScroll:true});
    } else {
      $('round').textContent = `ROUND ${battle.round} / 3`; $('turn-status').textContent = 'あなたの番'; $('turn-title').textContent = 'あなたのツッコミ！'; $('attack').value = '';
    }
  } catch (error) {
    await playerCutin;
    $('battle-error').textContent = `採点に失敗しました。HPは変更されていません。もう一度送信できます。${error.message}`;
    $('turn-status').textContent = '再送信できます';
  } finally {
    clearInterval(waitTimer);
    document.body.classList.remove('is-judging');
    document.body.dataset.turnMs=String(Math.round(performance.now()-started));
    busy = false; $('attack-panel').removeAttribute('aria-busy'); $('attack').disabled = false; updateInput();
    if (!battle.finished) focusAttack();
  }
};

// Provider selection is an operator setting; players only choose difficulty.
async function initializeJudge() {
  $('connection-status').textContent = '準備中…';
  try {
    const response = await fetch('/api/config', {cache:'no-store',signal:AbortSignal.timeout(10000)});
    if(!response.ok)throw new Error('config unavailable');
    const config = await response.json();
    if(!['demo','gemini','gpt','local'].includes(config.mode))throw new Error('invalid mode');
    if(config.mode==='demo')judge=new DemoJudge();
    else if(config.mode==='gemini')judge=await configuredGemini();
    else if(config.mode==='gpt')judge=await configuredGPT();
    else {
      if(typeof config.model!=='string'||!config.model.trim())throw new Error('missing model');
      judge=await connectModel(config.model);
    }
    $('connection-status').textContent='';
    $('provider-notice').textContent = config.mode==='demo' ? 'デモ判定：顔画像は解析しません。' : config.mode==='gemini' ? '最初の攻撃で顔の絵をGoogleのAIに送り、抽出した特徴を3回の採点に使います。特徴の読み取り漏れが採点に影響する場合があります。' : config.mode==='gpt' ? '顔の絵と発言をOpenAIに送って採点します。' : 'このサーバーのAIが採点します。';
  } catch {
    judge=null;
    $('connection-status').textContent='採点の準備ができません。時間をおいて再読み込みしてください。';
    $('provider-notice').textContent='採点の準備ができていません。ゲーム管理者に確認してください。';
  } finally {
    setupBusy=false;
    document.body.dataset.judgeReady=String(Boolean(judge));
    document.body.dataset.judgeLoaded='true';
    drawing.check();
  }
}
initializeJudge();

// Pointer tilt affects presentation only; scoring always uses the original PNGs.
for (const stage of document.querySelectorAll('.face-stage')) {
  stage.addEventListener('pointermove', event => {
    if (event.pointerType !== 'mouse') return;
    const rect = stage.getBoundingClientRect();
    stage.style.setProperty('--tilt-y', `${((event.clientX - rect.left) / rect.width - .5) * 16}deg`);
    stage.style.setProperty('--tilt-x', `${-((event.clientY - rect.top) / rect.height - .5) * 12}deg`);
  });
  stage.addEventListener('pointerleave', () => { stage.style.setProperty('--tilt-x', '0deg'); stage.style.setProperty('--tilt-y', '0deg'); });
}
drawing.check();

for (const id of ['title-face','preview-face','player-face','cpu-face','cutin-face']) {
  const image=$(id);
  image.addEventListener('facegeometry',event=>{
    if(id==='preview-face') $('preview-caption').textContent=event.detail.available===false?'この端末では通常のプレビューを表示します。':event.detail.detected?'描いた輪郭に合わせて立体化！':'閉じた輪郭を描くと、その形で立体化します。';
  });
  const viewer=new FaceMesh(image);
  if(id==='preview-face'&&!viewer.available) $('preview-caption').textContent='この端末では通常のプレビューを表示します。';
}

rankings=setupRankings({showScreen});
