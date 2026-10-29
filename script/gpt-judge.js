export class GPTJudge {
  constructor(model) { this.model = model; this.vision = true; this.label = 'GPT判定'; }
  async playRound(input) {
    const response = await fetch('/api/gpt/round', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(input), signal: AbortSignal.timeout(70000),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'GPTの判定を取得できません。');
    return result;
  }
}
export async function configuredGPT() {
  const response = await fetch('/api/gpt/status', {cache: 'no-store', signal: AbortSignal.timeout(10000)});
  const status = await response.json();
  if (!response.ok) throw new Error('GPTの設定を確認できません。');
  if (!status.configured) throw new Error('OPENAI_API_KEYが未設定です。READMEのGPT起動手順を確認してください。');
  return new GPTJudge(status.model);
}
