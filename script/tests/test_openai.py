import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import openai_gateway
import server

PNG = 'data:image/png;base64,' + server.base64.b64encode(b'\x89PNG\r\n\x1a\nmock').decode()
SCORE = {'feature': 8, 'bite': 8, 'creativity': 4, 'novelty': 5, 'evidence': '太い眉', 'reason': '特徴をえぐる皮肉'}
RAW = {'player': SCORE, 'cpu': {'text': 'その口、プリン専用改札かよ！', 'score': SCORE}}

class OpenAITests(unittest.TestCase):
    def response(self, value):
        return io.BytesIO(json.dumps(value).encode())

    def completed(self, content=None):
        return {'status':'completed', 'output': [{'type':'message', 'content': content if content is not None else [{'type':'output_text', 'text':json.dumps(RAW)}]}]}

    def body(self, **values):
        return {'text':'眉毛が海苔の不法占拠かよ', 'round':1, 'playerHistory':[], 'cpuHistory':[], 'playerImage':PNG, 'cpuImage':PNG, **values}

    def test_responses_payload_and_parsing(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':'mock-only-key'}), patch('openai_gateway.urlopen', return_value=self.response(self.completed())) as call:
            result = openai_gateway.generate('gpt-5.4-mini', 'instructions', [{'type':'input_image','image_url':PNG}], {'type':'object'})
        self.assertEqual(result, RAW)
        req = call.call_args.args[0]
        body = json.loads(req.data)
        self.assertEqual(req.full_url, 'https://api.openai.com/v1/responses')
        self.assertEqual(req.get_header('Authorization'), 'Bearer mock-only-key')
        self.assertFalse(body['store'])
        self.assertTrue(body['text']['format']['strict'])
        self.assertEqual(body['reasoning'], {'effort':'none'})
        self.assertNotIn('mock-only-key', req.data.decode())

    def test_missing_key_never_calls_api(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':''}), patch('openai_gateway.urlopen') as call:
            with self.assertRaises(openai_gateway.OpenAIError): openai_gateway.generate('model','',[],{})
        call.assert_not_called()

    def test_upstream_errors_do_not_expose_body_or_key(self):
        for code in [401,403,429,500]:
            error = HTTPError('https://api.openai.com/v1/responses', code, 'error', {}, io.BytesIO(b'secret-upstream-body'))
            with patch.dict(os.environ, {'OPENAI_API_KEY':'mock-only-key'}), patch('openai_gateway.urlopen', side_effect=error):
                with self.assertRaises(openai_gateway.OpenAIError) as caught: openai_gateway.generate('model','',[],{})
                self.assertNotIn('secret', str(caught.exception))
                self.assertNotIn('mock-only-key', str(caught.exception))

    def test_network_refusal_and_incomplete(self):
        values = [{'status':'incomplete'}, self.completed([{'type':'refusal','refusal':'no'}]), self.completed([{'type':'output_text','text':'not json'}])]
        for value in values:
            with patch.dict(os.environ, {'OPENAI_API_KEY':'mock-only-key'}), patch('openai_gateway.urlopen', return_value=self.response(value)):
                with self.assertRaises(openai_gateway.OpenAIError): openai_gateway.generate('model','',[],{})
        with patch.dict(os.environ, {'OPENAI_API_KEY':'mock-only-key'}), patch('openai_gateway.urlopen', side_effect=URLError('offline')):
            with self.assertRaises(openai_gateway.OpenAIError): openai_gateway.generate('model','',[],{})

    def test_full_round_uses_one_call_with_both_images_and_histories(self):
        with patch('server.openai_gateway.generate', return_value=RAW) as call:
            result = server.run_gpt_round(self.body(playerHistory=['前の発言'], cpuHistory=['CPUの前の発言']))
        call.assert_called_once()
        model, instructions, content, schema = call.call_args.args
        self.assertEqual(len([p for p in content if p['type']=='input_image']),2)
        self.assertIn('CPUの前の発言', content[0]['text'])
        self.assertIn('前の発言', content[0]['text'])
        self.assertEqual(result['player']['damage'],25)
        self.assertEqual(result['cpu']['score']['damage'],25)
        self.assertEqual(result['player']['mode'],'gpt')

    def test_invalid_input_rejected_before_api(self):
        for values in [dict(playerImage='bad'),dict(cpuImage='bad'),dict(round=4),dict(playerHistory=['a']*4),dict(text='a'*121)]:
            with patch('server.openai_gateway.generate') as call:
                with self.assertRaises(ValueError): server.run_gpt_round(self.body(**values))
                call.assert_not_called()

    def test_invalid_cpu_and_scores_rejected(self):
        for raw in [{'player':SCORE,'cpu':{'text':'a'*121,'score':SCORE}}, {'player':SCORE,'cpu':{'text':'CPU','score':{**SCORE,'bite':99}}}]:
            with patch('server.openai_gateway.generate',return_value=raw):
                with self.assertRaises(ValueError): server.run_gpt_round(self.body())

    def test_status_returns_only_configured_flag_and_model(self):
        handler = object.__new__(server.Handler)
        handler.path = '/api/gpt/status'
        with patch.dict(os.environ, {'OPENAI_API_KEY':'mock-only-key'}), patch.object(handler,'send_json') as send:
            handler.do_GET()
        send.assert_called_once_with(200, {'configured':True,'model':server.OPENAI_MODEL})

if __name__ == '__main__': unittest.main()
