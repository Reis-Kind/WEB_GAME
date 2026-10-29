"""Server-only Gemini Generate Content adapter (Python standard library only)."""
import json
import os
import re
import time
import logging
from gemini_wire import compact_round, expand_round
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GeminiError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def configured():
    return bool(os.environ.get('GEMINI_API_KEY', '').strip())


def generate(model, instructions, content, schema):
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        raise GeminiError('GEMINI_API_KEYが未設定です。READMEのGemini起動手順を確認してサーバーを再起動してください。')
    if not isinstance(model, str) or not re.fullmatch(r'[a-zA-Z0-9._-]+', model):
        raise GeminiError('GEMINI_MODELのモデル名を確認してください。', 400)
    schema, instructions, compact = compact_round(schema, instructions)
    parts = []
    for item in content:
        if item['type'] == 'input_text':
            parts.append({'text': item['text']})
        elif item['type'] == 'input_image':
            image = item['image_url']
            if not image.startswith('data:image/png;base64,'):
                raise GeminiError('PNGの顔画像が必要です。', 400)
            parts.append({'inlineData': {'mimeType': 'image/png', 'data': image.split(',', 1)[1]}})
        else:
            raise GeminiError('入力の形式が不正です。', 400)
    generation = {'responseMimeType': 'application/json', 'responseJsonSchema': schema,
                  'maxOutputTokens': 1000, 'temperature': .3}
    if model.startswith('gemini-2.5-'):
        generation['thinkingConfig'] = {'thinkingBudget': 0}
    elif model.startswith('gemini-3.1-flash-lite'):
        generation['thinkingConfig'] = {'thinkingLevel': 'MINIMAL'}
    payload = {'systemInstruction': {'parts': [{'text': instructions}]},
               'contents': [{'role': 'user', 'parts': parts}], 'generationConfig': generation}
    # Header authentication keeps the API key out of URLs and server access logs.
    request = Request(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                      data=json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    started=time.perf_counter()
    try:
        with urlopen(request, timeout=60) as response:
            result = json.load(response)
    except HTTPError as error:
        logging.getLogger('kao.ai').warning('Gemini HTTP %d after %.2fs',error.code,time.perf_counter()-started)
        messages = {
            400: 'GeminiのAPIキー・モデル名・リクエスト形式を確認してください。',
            401: 'GeminiのAPIキーを確認してください。',
            403: 'Geminiの利用権限・キーの制限・利用地域を確認してください。',
            404: f'Geminiモデル「{model}」がAPIで見つかりません。config.py の GEMINI_MODEL を gemini-3.1-flash-lite にし、サーバーを再起動してください。環境変数GEMINI_MODELを設定している場合はそちらが優先されます。',
            429: 'Geminiの無料枠または利用回数の上限に達した可能性があります。AI Studioで上限を確認し、時間を置いて再送信してください。有料モードには切り替えていません。',
        }
        raise GeminiError(messages.get(error.code, 'Gemini APIでエラーが発生しました。少し待って再送信してください。'),
                          429 if error.code == 429 else 503) from None
    except (URLError, OSError, TimeoutError):
        raise GeminiError('Gemini APIに接続できないか、60秒でタイムアウトしました。再送信できます。') from None
    except (ValueError, TypeError):
        raise GeminiError('Gemini APIの応答形式が正しくありません。再送信してください。') from None
    if not isinstance(result, dict):
        raise GeminiError('Gemini APIの応答形式が正しくありません。')
    feedback = result.get('promptFeedback')
    if isinstance(feedback, dict) and feedback.get('blockReason'):
        raise GeminiError('Geminiがこの発言の判定を返せませんでした。表現を変えて再送信してください。', 422)
    candidates = result.get('candidates')
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        raise GeminiError('Geminiから採点結果を取得できませんでした。再送信してください。')
    candidate = candidates[0]
    if candidate.get('finishReason') != 'STOP':
        raise GeminiError('Geminiの応答が未完了、または判定できない表現でした。短い発言にするなど表現を変えて再送信してください。', 422)
    candidate_content = candidate.get('content')
    if not isinstance(candidate_content, dict) or not isinstance(candidate_content.get('parts'), list):
        raise GeminiError('Geminiの採点形式が正しくありません。')
    output = candidate_content['parts']
    try:
        text = ''.join(part['text'] for part in output if isinstance(part, dict) and 'text' in part and not part.get('thought'))
        value = json.loads(text)
    except (ValueError, TypeError):
        raise GeminiError('Geminiの採点形式が正しくありません。再送信してください。') from None
    if not isinstance(value, dict):
        raise GeminiError('Geminiの採点形式が正しくありません。')
    if compact is not None:
        try:
            value=expand_round(value,compact)
        except (ValueError,TypeError,KeyError):
            raise GeminiError('Geminiの採点形式が正しくありません。再送信してください。') from None
        usage=result.get('usageMetadata',{})
        if not isinstance(usage,dict):usage={}
        images=sum(item.get('type')=='input_image' for item in content)
        tokens=usage.get('candidatesTokenCount')
        if type(tokens) is not int or tokens<0:tokens='unknown'
        logging.getLogger('kao.ai').info('Gemini API %.2fs; images=%d; output_tokens=%s',time.perf_counter()-started,images,tokens)
    return value
