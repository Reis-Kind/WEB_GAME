export const INITIAL_HP = 100;
export const MAX_ROUNDS = 3;
export function winner(playerHP, cpuHP) {
  return playerHP === cpuHP ? 'draw' : playerHP > cpuHP ? 'player' : 'cpu';
}
function validResult(result) {
  if (!result || !Number.isFinite(result.damage) || typeof result.reason !== 'string') throw new Error('採点結果の形式が正しくありません。');
  return {...result, damage: Math.max(0, Math.min(30, Math.round(result.damage)))};
}
export const DIFFICULTIES = {easy: {label: 'やさしい', scale: 0.6}, normal: {label: 'ふつう', scale: 0.8}, hard: {label: 'ガチ', scale: 1}};
export class Battle {
  constructor(judge, playerImage, cpuImage, difficulty = 'hard') {
    if (!Object.hasOwn(DIFFICULTIES, difficulty)) throw new Error('難易度が不正です。');
    this.difficulty = difficulty;
    this.judge = judge;
    this.images = {player: playerImage, cpu: cpuImage};
    this.hp = {player: INITIAL_HP, cpu: INITIAL_HP};
    this.history = {player: [], cpu: []};
    this.round = 1;
    this.busy = false;
    this.finished = false;
  }
  async play(text) {
    if (this.busy || this.finished) return null;
    if (typeof text !== 'string' || !text.trim() || Array.from(text).length > 120) throw new Error('1〜120文字で入力してください。');
    this.busy = true;
    try {
      const attack = text.trim();
      let playerResult, cpuResult, reply;
      if (typeof this.judge.playRound === 'function') {
        const result = await this.judge.playRound({text: attack, round: this.round,
          playerHistory: [...this.history.player], cpuHistory: [...this.history.cpu],
          playerImage: this.images.player, cpuImage: this.images.cpu});
        playerResult = validResult(result?.player);
        reply = result?.cpu?.text;
        cpuResult = validResult(result?.cpu?.score);
      } else {
        playerResult = validResult(await this.judge.evaluate({text: attack, history: [...this.history.player], targetImage: this.images.cpu, round: this.round, actor: 'player'}));
        reply = await this.judge.cpuAttack({round: this.round, targetImage: this.images.player, history: [...this.history.cpu]});
        cpuResult = validResult(await this.judge.evaluate({text: reply, history: [...this.history.cpu], targetImage: this.images.player, round: this.round, actor: 'cpu'}));
      }
      if (typeof reply !== 'string' || !reply.trim() || Array.from(reply).length > 120) throw new Error('CPUの発言を取得できませんでした。');
      const rawDamage = cpuResult.damage;
      cpuResult = {...cpuResult, damage: Math.round(rawDamage * DIFFICULTIES[this.difficulty].scale)};
      if (this.difficulty !== 'hard') cpuResult.reason += `（${DIFFICULTIES[this.difficulty].label}補正：${rawDamage}→${cpuResult.damage}ダメージ）`;
      // Commit only after both evaluations succeed: a retry never causes a double hit.
      const turn = {round: this.round, player: {...playerResult, text: attack}, cpu: {...cpuResult, text: reply}};
      this.hp.cpu = Math.max(0, this.hp.cpu - playerResult.damage);
      this.hp.player = Math.max(0, this.hp.player - cpuResult.damage);
      this.history.player.push(attack);
      this.history.cpu.push(reply);
      this.finished = this.round === MAX_ROUNDS;
      if (!this.finished) this.round++;
      return {...turn, hp: {...this.hp}, finished: this.finished, winner: this.finished ? winner(this.hp.player, this.hp.cpu) : null};
    } finally { this.busy = false; }
  }
}
