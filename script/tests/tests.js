import {Battle, winner} from '../game.js';
import {demoScore, DemoJudge} from '../judge.js';
import {Drawing} from '../drawing.js';
import {LocalJudge} from '../local-judge.js';
const results = [];
function assert(condition, name) { if (!condition) throw new Error(name); }
async function test(name, fn) { try { await fn(); results.push({name, pass:true}); } catch(e) { results.push({name, pass:false, error:e.message}); } }
await test('3ラウンド・各3攻撃・HP範囲・終了後の攻撃禁止', async () => {
  const game = new Battle(new DemoJudge(), 'player-image', 'cpu-image');
  assert(game.hp.player === 100 && game.hp.cpu === 100, '初期HP');
  for (const line of ['その眉毛、海苔の会議みたい！', '鼻が滑走路のような形！', 'その目、宇宙の信号かよ']) {
    const turn = await game.play(line);
    assert(turn.player.damage >= 0 && turn.player.damage <= 30, 'ダメージ範囲');
  }
  assert(game.finished && game.history.player.length === 3 && game.history.cpu.length === 3, '攻撃回数');
  assert(game.hp.player >= 10 && game.hp.cpu >= 10, 'HP下限');
  assert(await game.play('追加') === null, '終了後');
});
await test('勝ち・負け・同HPなら引き分け', () => { assert(winner(30, 20) === 'player' && winner(20, 30) === 'cpu' && winner(20, 20) === 'draw', '勝敗'); });
await test('同文・句読点違い・よく似た発言を減点', () => {
  const text = 'その眉毛、海苔の会議みたい！';
  assert(demoScore(text).damage > demoScore(text, [text]).damage, '同文');
  assert(demoScore('その眉毛 海苔の会議みたい', [text]).damage === 2, '句読点');
  assert(demoScore('その眉毛、海苔の会議みたいだね！', [text]).damage === 2, '類似');
});
await test('長さと過激さで強くならない', () => {
  assert(demoScore('あ'.repeat(120)).damage === demoScore('あ').damage, '長さ');
  assert(demoScore('死ね、眉毛は海苔みたい').damage === 0, '過激さ');
});
await test('空入力・長すぎる発言の拒否', async () => {
  const b = new Battle(new DemoJudge());
  for (const text of [' ', 'a'.repeat(121)]) { let rejected = false; try { await b.play(text); } catch { rejected = true; } assert(rejected, '入力拒否'); }
  assert(b.hp.cpu === 100 && b.history.player.length === 0, '状態維持');
});
await test('非同期採点中の二重送信を拒否', async () => {
  let resolve;
  const b = new Battle({evaluate: async () => { await new Promise(r => resolve = r); return {damage:20, reason:'test'}; }, cpuAttack: async () => 'CPU'});
  const pending = b.play('test');
  assert(await b.play('二重送信') === null, 'ロック'); resolve();
  await new Promise(r => setTimeout(r, 0)); resolve(); await pending;
  assert(b.history.player.length === 1, '一度のみ');
});
await test('CPU採点失敗ではHPと履歴を更新せず再試行できる', async () => {
  let fail = true;
  const b = new Battle({evaluate: async ({actor}) => { if (actor === 'cpu' && fail) throw new Error('offline'); return {damage:20, reason:'test'}; }, cpuAttack: async () => 'CPU'});
  try { await b.play('test'); } catch {}
  assert(b.hp.player === 100 && b.hp.cpu === 100 && b.round === 1 && !b.busy && b.history.player.length === 0, '失敗時の原子性');
  fail = false; await b.play('test'); assert(b.hp.cpu === 80 && b.hp.player === 80, '再送信');
});
await test('モデルの異常値を拒否しダメージを0〜30に制限', async () => {
  const b = new Battle({evaluate: async ({actor}) => ({damage: actor === 'player' ? 999 : -1, reason:'test'}), cpuAttack: async () => 'CPU'});
  const turn = await b.play('test'); assert(turn.player.damage === 30 && turn.cpu.damage === 0, '制限');
  b.judge.evaluate = async () => ({damage: NaN, reason:'test'});
  let rejected = false; try { await b.play('test'); } catch { rejected = true; } assert(rejected && b.round === 2, 'NaN拒否');
});
await test('描画・消去・消しゴム・元に戻す・空白判定・座標変換', () => {
  const canvas = document.getElementById('canvas');
  const d = new Drawing(canvas);
  assert(!d.hasInk, '初期空白');
  d.remember(); d.strokes.push({tool:'pen', color:'#292d36', size:10, points:[{x:100,y:100},{x:200,y:200}]}); d.render(); d.check(); assert(d.hasInk, '描画');
  assert(d.image().startsWith('data:image/png;base64,'), 'PNG出力');
  const r = canvas.getBoundingClientRect(); const p = d.point({clientX:r.left + 160, clientY:r.top + 160}); assert(p.x === 320 && p.y === 320, '拡縮座標');
  d.clear(); assert(!d.hasInk, '全消去'); d.undo(); assert(d.hasInk, '全消去のundo');
  d.remember(); d.strokes.push({tool:'eraser', color:'#000000', size:40, points:[{x:100,y:100},{x:200,y:200}]}); d.render(); d.check(); assert(!d.hasInk, '消しゴム後空白');
  d.undo(); assert(d.hasInk, '消しゴムundo'); d.undo(); assert(!d.hasInk, 'ストロークundo');
});
await test('LLMプロバイダーが顔画像・履歴をサーバーへ渡す', async () => {
  const original = window.fetch;
  const calls = [];
  window.fetch = async (url, options) => { calls.push(JSON.parse(options.body)); return {ok:true, json:async () => ({damage:20, reason:'test', text:'CPUの返答'})}; };
  try {
    const j = new LocalJudge('test-model', true);
    await j.evaluate({text:'発言', targetImage:'data:image/png;base64,test', history:['前の発言'], round:1});
    const reply = await j.cpuAttack({round:1, history:[], targetImage:'player-image'});
    assert(calls[0].model === 'test-model' && calls[0].targetImage.includes('base64') && calls[0].history.length === 1 && calls[1].action === 'cpu' && reply === 'CPUの返答', '契約');
  } finally { window.fetch = original; }
});
window.testResults = results;
document.getElementById('results').textContent = JSON.stringify(results, null, 2);
