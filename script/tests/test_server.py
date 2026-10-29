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
            return {'message':{'content':json.dumps({'feature':10, 'bite':10, 'creativity':5, 'novelty':5, 'evidence':'偽の特徴', 'reason':'たとえの工夫'})}}
        with patch('server.ollama', side_effect=mock):
            result = server.run_model(self.body())
        self.assertEqual(result['damage'], 18)
        self.assertEqual(result['breakdown']['feature'], 0)
        self.assertNotIn('偽の特徴', result['reason'])
        self.assertFalse(result['vision'])

    def test_vision_sends_image(self):
        body = self.body()
        body['targetImage'] = 'data:image/png;base64,' + server.base64.b64encode(b'\x89PNG\r\n\x1a\nmock').decode()
        def mock(path, data):
            if path == '/api/show': return {'capabilities':['completion','vision']}
            self.assertEqual(len(data['messages'][1]['images']), 1)
            return {'message':{'content':'{"feature":8,"bite":9,"creativity":4,"novelty":5,"evidence":"太い眉毛","reason":"特徴とたとえ"}'}}
        with patch('server.ollama', side_effect=mock):
            self.assertTrue(server.run_model(body)['vision'])

    def test_cpu_is_generated(self):
        with patch('server.ollama', side_effect=[{'capabilities':[]}, {'message':{'content':'{"text":"もしも顔がプリンだったら、会議中もおやつの時間！"}'}}]):
            self.assertIn('もしも', server.run_model(self.body('cpu'))['text'])

    def test_invalid_outputs(self):
        for content in ['not json', '{"damage":"30","reason":"a"}', '{"damage":true,"reason":"a"}', '{"damage":20}']:
            with patch('server.ollama', side_effect=[{'capabilities':[]}, {'message':{'content':content}}]):
                with self.assertRaises(ValueError): server.run_model(self.body())

    def scores(self, **values):
        return {'feature': 9, 'bite': 9, 'creativity': 4, 'novelty': 5,
                'evidence': '眉が太く横長', 'reason': '太い眉への皮肉が鋭い', **values}

    def test_simple_matched_teasing_is_rewarded(self):
        matched = server.score_result(self.scores(), True, '新しい発言', [])
        mild = server.score_result(self.scores(bite=3), True, '新しい発言', [])
        unrelated = server.score_result(self.scores(feature=2), True, '新しい発言', [])
        self.assertEqual(matched['damage'], 27)
        self.assertEqual(mild['damage'], 27)
        self.assertLessEqual(unrelated['damage'], 18)
        self.assertIn('眉が太く横長', matched['reason'])
        self.assertIn('刺さり 9/10', matched['reason'])

    def test_short_teasing_bonus_preserves_repeat_and_observation_limits(self):
        simple = self.scores(feature=8, bite=4, creativity=0, novelty=5)
        self.assertEqual(server.score_result(simple, True, '眉毛ふとっ', [])['damage'], 23)
        self.assertEqual(server.score_result(simple, True, '眉毛ふとっ', ['眉毛ふとっ'])['damage'], 2)
        self.assertLessEqual(server.score_result(self.scores(feature=8, bite=0), True, '眉毛が太いですね', [])['damage'], 18)
        self.assertLessEqual(server.score_result(self.scores(feature=0, bite=1), True, 'バカ', [])['damage'], 18)
        self.assertLessEqual(server.score_result(self.scores(feature=8, bite=4, novelty=1), True, '眉毛ふとっ', ['眉毛太い'])['damage'], 8)

    def test_duplicate_caps_apply_even_if_model_gives_high_scores(self):
        repeated = server.score_result(self.scores(), True, 'その眉毛、海苔かよ！', ['その眉毛 海苔かよ'])
        similar = server.score_result(self.scores(novelty=1), True, '少し言い換え', ['前の発言'])
        self.assertEqual(repeated['damage'], 2)
        self.assertEqual(similar['damage'], 8)

    def test_component_validation_and_maximum(self):
        self.assertEqual(server.score_result(self.scores(feature=10, bite=10, creativity=5), True, '発言', [])['damage'], 30)
        for values in [dict(bite=11), dict(feature=-1), dict(bite=True), dict(bite=float('nan')), dict(bite='10'), dict(evidence='')]:
            with self.assertRaises(ValueError):
                server.score_result(self.scores(**values), True, '発言', [])
        for value in [[], None, {'damage': 30, 'reason': '旧形式'}]:
            with self.assertRaises(ValueError): server.score_result(value, True, '発言', [])

    def test_config_exposes_only_mode_and_model(self):
        handler = object.__new__(server.Handler)
        handler.path = '/api/config'
        with patch.object(handler, 'send_json') as send:
            handler.do_GET()
        send.assert_called_once_with(200, {'mode': server.JUDGE_MODE, 'model': server.OLLAMA_MODEL, 'openai_model': server.OPENAI_MODEL, 'gemini_model': server.GEMINI_MODEL})

    def test_configured_model_is_used_when_omitted(self):
        body = self.body()
        del body['model']
        def mock(path, data):
            self.assertEqual(data['model'], 'configured-test-model')
            if path == '/api/show': return {'capabilities': []}
            return {'message': {'content': '{"feature":0,"bite":5,"creativity":0,"novelty":5,"evidence":"","reason":"test"}'}}
        with patch('server.OLLAMA_MODEL', 'configured-test-model'), patch('server.ollama', side_effect=mock):
            self.assertEqual(server.run_model(body)['damage'], 10)

    def test_explicit_model_overrides_config(self):
        def mock(path, data):
            self.assertEqual(data['model'], 'test')
            if path == '/api/show': return {'capabilities': []}
            return {'message': {'content': '{"feature":0,"bite":5,"creativity":0,"novelty":5,"evidence":"","reason":"test"}'}}
        with patch('server.ollama', side_effect=mock):
            server.run_model(self.body())

    def test_invalid_input(self):
        for body in [{}, {**self.body(), 'round':4}, {**self.body(), 'text':''}, {**self.body(), 'history':['a']*4}]:
            with self.assertRaises(ValueError): server.validate_payload(body)

if __name__ == '__main__': unittest.main()
