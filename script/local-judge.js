async function request(path, body) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), signal: AbortSignal.timeout(130000)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'ローカルLLMに接続できません。');
  return data;
}
export class LocalJudge {
  constructor(model, vision) { this.model = model; this.vision = vision; }
  async evaluate(input) { return request('/api/judge', {...input, action: 'evaluate', model: this.model}); }
  async cpuAttack(input) { return (await request('/api/judge', {...input, action: 'cpu', model: this.model})).text; }
}
export async function connectModel(model) {
  const data = await request('/api/model', {model});
  return new LocalJudge(model, data.vision);
}
