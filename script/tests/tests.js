import {Battle, winner} from '../game.js';
import {demoScore, DemoJudge} from '../judge.js';
import {Drawing} from '../drawing.js';
import {LocalJudge} from '../local-judge.js';
import {GPTJudge} from '../gpt-judge.js';
import {GeminiJudge} from '../gemini-judge.js';
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
  for (const [difficulty, expected] of [['easy',18], ['normal',24], ['hard',30]]) {
    const judge = {playRound: async () => ({player:{damage:30,reason:'player'}, cpu:{text:'CPU',score:{damage:30,reason:'cpu'}}})};
    const b = new Battle(judge, 'player', 'cpu', difficulty);
    const turn = await b.play('test');
    assert(turn.cpu.damage === expected && turn.hp.player === 100-expected, difficulty + ' CPU補正');
    assert(turn.player.damage === 30 && turn.hp.cpu === 70, 'プレイヤー採点維持');
    if (difficulty !== 'hard') assert(turn.cpu.reason.includes('補正'), '補正の明示');
  }

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
  const plain = demoScore('その眉毛、海苔みたい');
  const harsh = demoScore('その眉毛、海苔みたいでキモいバカ顔だな');
  assert(harsh.damage === plain.damage && harsh.damage > 0, '毒舌だけで加点も0点化もしない');
  assert(demoScore('バカ').damage === demoScore('あ').damage, '悪口単体は高得点にしない');
  assert(demoScore('眉毛、海苔').damage === 25, '短いたとえにもダメージ');
  assert(demoScore('眉毛ふとっ').damage === 18, '簡単なツッコミ');
  assert(demoScore('眉毛、海苔', ['眉毛、海苔']).damage === 2, '短文連打は減点');
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
await test('バケツの境界・同色・undo・消去・白紙判定', () => {
  const canvas=document.createElement('canvas');canvas.width=canvas.height=640;
  const d=new Drawing(canvas),pixel=(x,y)=>Array.from(d.ctx.getImageData(x,y,1,1).data);
  d.strokes.push({tool:'circle',color:'#292d36',size:8,points:[{x:100,y:100},{x:300,y:300}]});d.render();d.check();
  d.color='#f96840';d.fill({x:200,y:200});
  assert([249,104,64,255].every((v,i)=>Math.abs(pixel(200,200)[i]-v)<=2),'閉じた丸の内側を塗る');
  assert(pixel(20,20)[3]===0,'外へ漏れない');
  const history=d.past.length;d.fill({x:200,y:200});assert(d.past.length===history,'同色は履歴を増やさない');
  d.undo();assert(pixel(200,200)[3]===0&&pixel(200,100)[3]>0,'塗りだけundo');
  d.fill({x:200,y:200});d.clear();assert(!d.hasInk,'全消去');d.undo();assert(pixel(200,200)[0]===249,'全消去undoで塗りも復元');
  d.strokes.push({tool:'eraser',color:'#000000',size:30,points:[{x:200,y:200}]});d.render();assert(pixel(200,200)[3]===0,'塗った後に消せる');
  d.strokes=[];d.render();d.color='#ffffff';d.fill({x:10,y:10});assert(!d.hasInk,'白で全面塗りは白紙');
  d.color='#427fa8';d.fill({x:10,y:10});assert([66,127,168,255].every((value,index)=>Math.abs(pixel(639,639)[index]-value)<=2)&&d.hasInk,'全面塗り '+pixel(639,639).join(',')+' '+d.hasInk);
});
await test('直線と丸は終点更新でプレビューする', () => {
  const canvas=document.createElement('canvas');canvas.width=canvas.height=640;
  const d=new Drawing(canvas);d.point=e=>({x:e.clientX,y:e.clientY});
  d.pointer=7;d.strokes=[{tool:'line',color:'#000000',size:8,points:[{x:10,y:10}]}];
  for(const coordinate of [50,100,200])d.move({pointerId:7,clientX:coordinate,clientY:coordinate,preventDefault(){}});
  assert(d.strokes[0].points.length===2&&d.ctx.getImageData(100,100,1,1).data[3]>0,'直線');
  d.strokes=[{tool:'circle',color:'#000000',size:8,points:[{x:100,y:100}]}];
  d.move({pointerId:7,clientX:300,clientY:300,preventDefault(){}});
  assert(d.ctx.getImageData(200,100,1,1).data[3]>0&&d.ctx.getImageData(200,200,1,1).data[3]===0,'丸は輪郭のみ');
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
await test('GPTの1回通信で両攻撃を処理し3ラウンドで終了', async () => {
  const original = window.fetch;
  const calls = [];
  window.fetch = async (url, options) => {
    calls.push({url, body: JSON.parse(options.body)});
    await new Promise(r => setTimeout(r, 0));
    return {ok:true, json:async () => ({player:{damage:25, reason:'顔に的中'}, cpu:{text:'CPUの毒舌', score:{damage:18, reason:'刺さる'}}})};
  };
  try {
    const b = new Battle(new GPTJudge('test-model'), 'player-png', 'cpu-png');
    const first = b.play('最初の発言');
    assert(await b.play('二重送信') === null, '二重送信ロック');
    await first;
    assert(b.hp.cpu === 75 && b.hp.player === 82, 'HPの攻撃対象');
    await b.play('次の発言'); await b.play('最後の発言');
    assert(calls.length === 3 && b.finished && b.history.cpu.length === 3, '1ラウンド1通信');
    assert(calls[0].url === '/api/gpt/round' && calls[0].body.playerImage === 'player-png' && calls[0].body.cpuImage === 'cpu-png', '顔の対象');
    assert(calls[1].body.playerHistory[0] === '最初の発言' && calls[1].body.cpuHistory[0] === 'CPUの毒舌', '履歴の分離');
  } finally { window.fetch = original; }
});
await test('GPTの失敗・不正応答でもHP維持と再送信ができる', async () => {
  let failure = true;
  const b = new Battle({playRound: async () => {
    if (failure) return {player:{damage:30, reason:'test'}, cpu:{text:'CPU', score:{damage:NaN, reason:'invalid'}}};
    return {player:{damage:20, reason:'test'}, cpu:{text:'CPU', score:{damage:10, reason:'test'}}};
  }});
  try { await b.play('発言'); } catch {}
  assert(b.hp.cpu === 100 && b.hp.player === 100 && b.round === 1 && !b.busy && b.history.player.length === 0, '全体成功時だけ確定');
  failure = false; await b.play('発言');
  assert(b.hp.cpu === 80 && b.hp.player === 90 && b.round === 2, '再送信');
});
await test('Geminiの1回通信で両画像・履歴を渡しAPIエラーを通知', async () => {
  const original = window.fetch;
  const calls = [];
  let fail = false;
  window.fetch = async (url, options) => {
    calls.push({url, body: JSON.parse(options.body)});
    return {ok:!fail, json:async () => fail ? {error:'無料枠の上限'} : {player:{damage:25, reason:'的中'}, cpu:{text:'CPUの毒舌', score:{damage:20, reason:'的中'}}}};
  };
  try {
    const b = new Battle(new GeminiJudge('gemini-test'), 'player-png', 'cpu-png');
    await b.play('眉毛が海苔の不法占拠かよ');
    assert(calls.length === 1 && calls[0].url === '/api/gemini/round', '1ラウンド1通信');
    assert(calls[0].body.cpuImage === 'cpu-png' && calls[0].body.playerImage === 'player-png', '両画像');
    fail = true;
    let rejected = false;
    try { await b.play('次の発言'); } catch(e) { rejected = e.message.includes('無料枠'); }
    assert(rejected && b.hp.cpu === 75 && b.hp.player === 80 && b.round === 2 && !b.busy, '上限時のHP維持とロック解除');
    assert(calls[1].body.playerHistory.length === 1 && calls[1].body.cpuHistory.length === 1, '履歴');
  } finally { window.fetch = original; }
});
window.testResults = results;
document.getElementById('results').textContent = JSON.stringify(results, null, 2);
