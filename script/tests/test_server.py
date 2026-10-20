import json
import unittest
from unittest.mock import patch
import server

class GatewayTests(unittest.TestCase):
    def body(self, action='evaluate'):
        return {'model':'test', 'action':action, 'text':'眉毛が海苔みたい', 'history':[], 'round':1}

    def test_text_only_does_not_send_image(self):
        def mock(path, data):
            if path == '/api/show': return {'capabilities':['completion']}
            self.assertNotIn('images', data['messages'][1])
            self.assertIn('顔を見た', data['messages'][0]['content'])
            return {'message':{'content':json.dumps({'damage':999, 'reason':'たとえの工夫'})}}
        with patch('server.ollama', side_effect=mock):
            result = server.run_model(self.body())
        self.assertEqual(result['damage'], 30)
        self.assertFalse(result['vision'])

    def test_vision_sends_image(self):
        body = self.body()
        body['targetImage'] = 'data:image/png;base64,' + server.base64.b64encode(b'\x89PNG\r\n\x1a\nmock').decode()
        def mock(path, data):
            if path == '/api/show': return {'capabilities':['completion','vision']}
            self.assertEqual(len(data['messages'][1]['images']), 1)
            return {'message':{'content':'{"damage":20,"reason":"特徴とたとえ"}'}}
        with patch('server.ollama', side_effect=mock):
            self.assertTrue(server.run_model(body)['vision'])

    def test_cpu_is_generated(self):
        with patch('server.ollama', side_effect=[{'capabilities':[]}, {'message':{'content':'{"text":"もしも顔がプリンだったら、会議中もおやつの時間！"}'}}]):
            self.assertIn('もしも', server.run_model(self.body('cpu'))['text'])

    def test_invalid_outputs(self):
        for content in ['not json', '{"damage":"30","reason":"a"}', '{"damage":true,"reason":"a"}', '{"damage":20}']:
            with patch('server.ollama', side_effect=[{'capabilities':[]}, {'message':{'content':content}}]):
                with self.assertRaises(ValueError): server.run_model(self.body())

    def test_config_exposes_only_mode_and_model(self):
        handler = object.__new__(server.Handler)
        handler.path = '/api/config'
        with patch.object(handler, 'send_json') as send:
            handler.do_GET()
        send.assert_called_once_with(200, {'mode': server.JUDGE_MODE, 'model': server.OLLAMA_MODEL})

    def test_configured_model_is_used_when_omitted(self):
        body = self.body()
        del body['model']
        def mock(path, data):
            self.assertEqual(data['model'], 'configured-test-model')
            if path == '/api/show': return {'capabilities': []}
            return {'message': {'content': '{"damage":10,"reason":"test"}'}}
        with patch('server.OLLAMA_MODEL', 'configured-test-model'), patch('server.ollama', side_effect=mock):
            self.assertEqual(server.run_model(body)['damage'], 10)

    def test_explicit_model_overrides_config(self):
        def mock(path, data):
            self.assertEqual(data['model'], 'test')
            if path == '/api/show': return {'capabilities': []}
            return {'message': {'content': '{"damage":10,"reason":"test"}'}}
        with patch('server.ollama', side_effect=mock):
            server.run_model(self.body())

    def test_invalid_input(self):
        for body in [{}, {**self.body(), 'round':4}, {**self.body(), 'text':''}, {**self.body(), 'history':['a']*4}]:
            with self.assertRaises(ValueError): server.validate_payload(body)

if __name__ == '__main__': unittest.main()
