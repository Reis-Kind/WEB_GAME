export class GeminiJudge {
  constructor(model) {
    this.model = model;
    this.vision = true;
    this.label = 'Gemini判定';
    this.notice = '顔画像と発言をGoogleに送信します。無料枠・課金状態はAI Studioで確認してください。';
  }
  async playRound(input) {
    const response = await fetch('/api/gemini/round', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(input), signal: AbortSignal.timeout(70000),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Geminiの判定を取得できません。');
    return result;
  }
}
export async function configuredGemini() {
  const response = await fetch('/api/gemini/status', {cache: 'no-store', signal: AbortSignal.timeout(10000)});
  const status = await response.json();
  if (!response.ok) throw new Error('Geminiの設定を確認できません。');
  if (!status.configured) throw new Error('GEMINI_API_KEYが未設定です。READMEのGemini起動手順を確認してください。');
  return new GeminiJudge(status.model);
}
