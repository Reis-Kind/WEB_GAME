import {Drawing} from './drawing.js';
import {Battle} from './game.js';
import {DemoJudge} from './judge.js';
import {connectModel} from './local-judge.js';
const $ = id => document.getElementById(id);
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
let battle, busy = false;
let setupBusy = true;
let judge = new DemoJudge();
let connectedJudge = null;
const drawing = new Drawing($('drawing'), d => {
  $('start').disabled = setupBusy || !d.hasInk || d.pointer !== null || ($('judge-mode').value === 'local' && !connectedJudge);
  $('undo').disabled = !d.past.length || d.pointer !== null;
  $('clear').disabled = !d.strokes.length || d.pointer !== null;
  $('canvas-hint').hidden = d.hasInk;
  $('start-help').textContent = d.hasInk ? '準備OK！ その顔で、ひと勝負。' : '顔を描くと、バトルを始められます';
});
function tool(name) {
  drawing.tool = name;
  for (const id of ['pen', 'eraser']) { $(id).classList.toggle('selected', id === name); $(id).setAttribute('aria-pressed', String(id === name)); }
}
$('pen').onclick = () => tool('pen');
$('eraser').onclick = () => tool('eraser');
for (const [color, label] of [['#292d36','すみ色'],['#f96840','オレンジ'],['#427fa8','青'],['#459a7a','緑'],['#af72b1','紫']]) {
  const button = document.createElement('button');
  button.className = 'swatch'; button.style.background = color;
  button.setAttribute('aria-label', label); button.setAttribute('aria-pressed', String(color === drawing.color));
  button.dataset.color = color;
  button.onclick = () => chooseColor(color);
  $('colors').append(button);
}
function chooseColor(color) {
  drawing.color = color; tool('pen');
  document.querySelectorAll('.swatch').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.color === color)));
}
$('custom-color').oninput = e => chooseColor(e.target.value);
$('size').oninput = e => { drawing.size = Number(e.target.value); $('size-label').value = e.target.value; };
$('undo').onclick = () => drawing.undo();
$('clear').onclick = () => drawing.clear();
function step(name) { for (const id of ['draw','battle','result']) $('step-' + id).classList.toggle('active', id === name); }
function hp(side, value) { $(side + '-hp').replaceChildren(document.createTextNode(`${value} `)); const small = document.createElement('small'); small.textContent = '/ 100'; $(side + '-hp').append(small); $(side + '-bar').value = value; }
function start() {
  if (setupBusy || !drawing.hasInk || drawing.pointer !== null || busy || ($('judge-mode').value === 'local' && !connectedJudge)) return;
  const cpuCanvas = document.createElement('canvas'); cpuCanvas.width = cpuCanvas.height = 640;
  const ctx = cpuCanvas.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 640, 640);
  if (!$('cpu-face').complete || !$('cpu-face').naturalWidth) { $('connection-status').textContent = 'CPUの画像を読み込み中です。少し待って再度お試しください。'; return; }
  ctx.drawImage($('cpu-face'), 0, 0, 640, 640);
  battle = new Battle(judge, drawing.image(), cpuCanvas.toDataURL('image/png'));
  const label = judge instanceof DemoJudge ? 'デモ判定' : 'ローカルLLM判定';
  document.querySelector('.battle-top .badge').textContent = label;
  document.querySelector('.battle-note').textContent = judge instanceof DemoJudge ? '✳ デモ判定：画像は解析しません。CPUは定型文です。' : `✳ ${judge.model}：${judge.vision ? '画像対応モデルに顔画像を渡します。' : 'テキスト専用判定。顔画像は解析しません。'} 採点とCPUの返答をローカルで生成します。`;
  $('player-face').src = battle.images.player;
  $('draw-screen').hidden = true; $('battle-screen').hidden = false;
  $('result').hidden = true; $('attack-form').hidden = false;
  $('turn-title').textContent = 'あなたのツッコミ！'; $('turn-status').textContent = 'あなたの番';
  $('battle-error').textContent = ''; $('round').textContent = 'ROUND 1 / 3';
  $('log').replaceChildren(); const p = document.createElement('p'); p.className = 'log-empty'; p.textContent = 'バトル開始！ 最初のツッコミをどうぞ。'; $('log').append(p);
  $('attack').value = ''; $('attack').disabled = false;
  hp('player', 100); hp('cpu', 100); step('battle'); updateInput();
  $('battle-screen').scrollIntoView({block: 'start', behavior: 'smooth'}); $('attack').focus({preventScroll: true});
}
$('start').onclick = start; $('rematch').onclick = start;
$('redraw').onclick = () => { if (busy) return; $('battle-screen').hidden = true; $('draw-screen').hidden = false; step('draw'); $('draw-screen').scrollIntoView({behavior: 'smooth'}); };
function updateInput() {
  $('counter').textContent = `${Array.from($('attack').value).length} / 120`;
  $('submit').disabled = busy || !battle || battle.finished || !$('attack').value.trim();
}
$('attack').oninput = updateInput;
function log(actor, result, round) {
  $('log').querySelector('.log-empty')?.remove();
  const entry = document.createElement('article'); entry.className = 'log-entry';
  const header = document.createElement('header');
  const name = document.createElement('span'); name.textContent = `ROUND ${round} · ${actor === 'player' ? 'あなた' : 'CPU・まゆげ部長'}`;
  const score = document.createElement('b'); score.textContent = `${result.damage} ダメージ`;
  header.append(name, score);
  const quote = document.createElement('blockquote'); quote.textContent = result.text;
  const reason = document.createElement('p'); reason.textContent = `${judge instanceof DemoJudge ? 'デモ判定' : 'ローカルLLM判定'}：${result.reason}${actor === 'cpu' && judge instanceof DemoJudge ? '（定型のCPU発言）' : ''}`;
  entry.append(header, quote, reason); $('log').append(entry); $('log').scrollTop = $('log').scrollHeight;
}
async function hit(side, damage, value) {
  const card = $(side + '-card'); card.querySelector('.damage').textContent = `−${damage}`;
  card.classList.remove('hit'); void card.offsetWidth; card.classList.add('hit'); hp(side, value);
  await wait(1050); card.classList.remove('hit');
}
$('attack-form').onsubmit = async e => {
  e.preventDefault(); if (busy || !battle || battle.finished || !$('attack').value.trim()) return;
  busy = true; $('attack').disabled = true; updateInput();
  $('battle-error').textContent = ''; $('turn-status').textContent = judge instanceof DemoJudge ? 'デモ採点中…' : 'ローカルLLM採点中…'; $('attack-panel')?.setAttribute('aria-busy', 'true');
  try {
    const turn = await battle.play($('attack').value);
    if (!turn) return;
    await wait(400); log('player', turn.player, turn.round);
    await hit('cpu', turn.player.damage, turn.hp.cpu);
    $('turn-status').textContent = 'CPUの番'; $('turn-title').textContent = 'まゆげ部長のツッコミ！';
    await wait(500); log('cpu', turn.cpu, turn.round);
    await hit('player', turn.cpu.damage, turn.hp.player);
    if (turn.finished) {
      $('attack-form').hidden = true; $('result').hidden = false; $('turn-title').textContent = '決着！'; $('turn-status').textContent = '対戦終了';
      $('round').textContent = 'FINISH · 3 / 3'; step('result');
      $('result-title').textContent = {player:'あなたの勝ち！', cpu:'まゆげ部長の勝ち！', draw:'仲良く、引き分け！'}[turn.winner];
      $('result-detail').textContent = `あなた ${turn.hp.player} HP ／ CPU ${turn.hp.cpu} HP。3回ずつのツッコミ、おつかれさま！`;
      $('rematch').focus({preventScroll: true});
    } else {
      $('round').textContent = `ROUND ${battle.round} / 3`; $('turn-status').textContent = 'あなたの番'; $('turn-title').textContent = 'あなたのツッコミ！'; $('attack').value = '';
    }
  } catch (error) {
    $('battle-error').textContent = `採点に失敗しました。HPは変更されていません。もう一度送信できます。${error.message}`;
    $('turn-status').textContent = '再送信できます';
  } finally {
    busy = false; $('attack-panel').removeAttribute('aria-busy'); $('attack').disabled = false; updateInput();
    if (!battle.finished) $('attack').focus({preventScroll: true});
  }
};

$('judge-mode').onchange = () => {
  const local = $('judge-mode').value === 'local';
  $('local-settings').hidden = !local; $('demo-note').hidden = local;
  judge = local ? connectedJudge : new DemoJudge();
  $('connection-status').textContent = local ? connectedJudge ? modelStatus(connectedJudge) : 'Ollamaを起動して、モデルを取得・接続してください。' : 'デモ判定：画像は解析しません。';
  document.querySelector('.mode').textContent = local ? '● LOCAL LLM' : '● CPU DEMO';
  drawing.check();
};
function modelStatus(j) { return `${j.model} 接続済み。${j.vision ? '画像対応：顔画像も渡します。' : 'テキスト専用：画像は解析しません。'}`; }
$('load-models').onclick = async () => {
  $('load-models').disabled = true; connectedJudge = null; drawing.check(); $('connection-status').textContent = 'Ollamaに接続中…';
  try {
    const res = await fetch('/api/models', {signal: AbortSignal.timeout(10000)});
    const data = await res.json(); if (!res.ok) throw new Error(data.error);
    $('model-select').replaceChildren();
    for (const model of data.models) { const option = document.createElement('option'); option.value = option.textContent = model; $('model-select').append(option); }
    $('connect-model').disabled = !data.models.length;
    $('connection-status').textContent = data.models.length ? 'モデルを選んで接続してください。' : 'モデルがありません。Ollamaでモデルを追加してください。';
  } catch (e) { $('connection-status').textContent = `${e.message} READMEの起動手順を確認してください。`; }
  finally { $('load-models').disabled = false; }
};
$('model-select').onchange = () => { connectedJudge = null; drawing.check(); };
$('connect-model').onclick = async () => {
  $('connect-model').disabled = true; connectedJudge = null; drawing.check(); $('connection-status').textContent = 'モデルを確認中…';
  const selected = $('model-select').value;
  try {
    const result = await connectModel(selected);
    if ($('model-select').value !== selected) return;
    connectedJudge = result;
    if ($('judge-mode').value === 'local') { judge = result; $('connection-status').textContent = modelStatus(result); }
  } catch (e) { $('connection-status').textContent = e.message; }
  finally { $('connect-model').disabled = !$('model-select').value; drawing.check(); }
};

// Apply server configuration and connect to the configured local model on startup.
async function initializeJudge() {
  const controls = ['judge-mode', 'load-models', 'model-select', 'connect-model'];
  for (const id of controls) $(id).disabled = true;
  $('connection-status').textContent = '判定設定を読み込み中…';
  try {
    const response = await fetch('/api/config', {cache: 'no-store', signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error('設定を取得できません。python3 server.py で起動してください。');
    const config = await response.json();
    if (!['local', 'demo'].includes(config.mode) || typeof config.model !== 'string' || !config.model.trim()) throw new Error('判定設定の形式が正しくありません。');
    $('judge-mode').value = config.mode;
    $('judge-mode').onchange();
    if (config.mode === 'local') {
      const option = document.createElement('option');
      option.value = option.textContent = config.model;
      $('model-select').replaceChildren(option);
      await $('connect-model').onclick();
      if (!connectedJudge) $('connection-status').textContent += ' config.py のモデル名と、ollama list を確認してください。デモ判定にも切り替えられます。';
    }
  } catch (error) {
    $('judge-mode').value = 'demo';
    $('judge-mode').onchange();
    $('connection-status').textContent = `設定の読み込みに失敗したためデモ判定です。${error.message}`;
  } finally {
    setupBusy = false;
    for (const id of ['judge-mode', 'load-models', 'model-select']) $(id).disabled = false;
    $('connect-model').disabled = !$('model-select').value;
    drawing.check();
  }
}
initializeJudge();
