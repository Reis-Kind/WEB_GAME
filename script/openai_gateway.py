"""Server-only OpenAI Responses API adapter. Never expose the key to the browser."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenAIError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def configured():
    return bool(os.environ.get('OPENAI_API_KEY', '').strip())


def generate(model, instructions, content, schema):
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not key:
        raise OpenAIError('OPENAI_API_KEYが未設定です。サーバーを起動するターミナルで設定して再起動してください。', 503)
    payload = {
        'model': model, 'instructions': instructions,
        'input': [{'role': 'user', 'content': content}],
        'text': {'format': {'type': 'json_schema', 'name': 'face_battle_round', 'strict': True, 'schema': schema}},
        'max_output_tokens': 1200, 'store': False,
    }
    if model.startswith('gpt-5.4'):
        payload['reasoning'] = {'effort': 'none'}
    request = Request('https://api.openai.com/v1/responses', data=json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    try:
        with urlopen(request, timeout=60) as response:
            result = json.load(response)
    except HTTPError as error:
        # Do not relay upstream response bodies, request headers, or credentials.
        messages = {401: 'OpenAI APIキーを確認してください。', 403: 'OpenAI APIへのアクセスが許可されていません。',
                    429: 'OpenAI APIの利用上限・残高または混雑を確認し、少し待って再送信してください。',
                    400: 'OpenAI APIのモデル設定またはリクエスト形式を確認してください。',
                    404: '指定のOpenAIモデルを利用できません。OPENAI_MODELを確認してください。'}
        raise OpenAIError(messages.get(error.code, 'OpenAI APIでエラーが発生しました。再送信してください。'), 503) from None
    except (URLError, OSError, TimeoutError):
        raise OpenAIError('OpenAI APIに接続できないか、60秒でタイムアウトしました。再送信できます。') from None
    if not isinstance(result, dict) or result.get('status') != 'completed':
        raise OpenAIError('GPTの応答が完了しませんでした。再送信してください。')
    texts = []
    for item in result.get('output', []):
        if item.get('type') != 'message':
            continue
        for part in item.get('content', []):
            if part.get('type') == 'refusal':
                raise OpenAIError('GPTがこの発言の判定を返せませんでした。表現を変えて再送信してください。', 422)
            if part.get('type') == 'output_text':
                texts.append(part.get('text', ''))
    try:
        value = json.loads(''.join(texts))
    except (ValueError, TypeError):
        raise OpenAIError('GPTの応答形式が正しくありません。再送信してください。') from None
    if not isinstance(value, dict):
        raise OpenAIError('GPTの応答形式が正しくありません。')
    return value
