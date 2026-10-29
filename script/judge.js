/** Demo only: images are deliberately not inspected. Replace this provider with
 * a same-origin server API when adding AI. Never put a secret in browser code. */
export const normalize = text => text.normalize('NFKC').toLowerCase().replace(/[\s\p{P}\p{S}]/gu, '');
function similar(a, b) {
  if (a === b) return true;
  if (!a || !b) return false;
  const pairs = s => new Set(Array.from(s).slice(1).map((c, i) => Array.from(s)[i] + c));
  const x = pairs(a), y = pairs(b);
  if (!x.size || !y.size) return false;
  return 2 * [...x].filter(p => y.has(p)).length / (x.size + y.size) >= .72;
}
export function demoScore(text, history = []) {
  const normalized = normalize(text);
  if (!normalized) return {damage: 0, reason: '言葉が見つかりませんでした。たとえを入れてみよう。', mode: 'demo'};
  if (history.some(past => similar(normalized, normalize(past)))) {
    return {damage: 2, reason: '前の発言と同じ、またはよく似た表現なので減点。別のたとえに挑戦！ 画像は未解析です。', mode: 'demo'};
  }
  // No reward for length or intensity. These are textual cues, not vision results.
  const comparison = /みたい|まるで|ような|ように|そっくり|たとえ|かよ|並み|すぎ|まんま/.test(text);
  const feature = /目|眼|眉|まゆ|鼻|口|くち|耳|髪|かみ|輪郭|ほっぺ|顔|かお|あご|おでこ/.test(text);
  const playful = /海苔|のり|会議|渋滞|信号|滑走路|アンテナ|おにぎり|パン|電車|月|山|毛虫|カーテン|バナナ|定規|Wi-Fi|wifi|プリン|宇宙|寝ぐせ|看板/.test(text);
  const damage = Math.min(30, 6 + (comparison ? 5 : 0) + (feature ? 12 : 0) + (playful ? 7 : 0));
  const reason = `${comparison ? 'たとえの言い回し' : '新しい一言'}${feature ? '・顔の部位を表す言葉' : ''}${playful ? '・遊びのある単語' : ''}を仮採点。画像との一致や本当の面白さは判定していません。`;
  return {damage, reason, mode: 'demo'};
}
export const CPU_LINES = [
  'その顔、月曜の会議で三時間説教されたおにぎりかよ！具までやる気なくしてんぞ！',
  'その目、圏外のアンテナみたいだな！宇宙にまで既読スルーされてんのかよ！',
  'その口、プリン専用の改札かよ！悪口だけ特急で通過させんな！'
];
export class DemoJudge {
  async evaluate({text, history}) { return demoScore(text, history); }
  async cpuAttack({round}) { return CPU_LINES[round - 1]; }
}
// Future provider contract:
// evaluate({text, history, targetImage, round, actor}) -> {damage: 0..30, reason}
// cpuAttack({round, targetImage, history}) -> string
// A server provider should POST to your backend; only the backend holds the API key.
