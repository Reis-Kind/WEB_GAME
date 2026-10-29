import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import gemini_gateway
import server

PNG = 'data:image/png;base64,' + server.base64.b64encode(b'\x89PNG\r\n\x1a\nmock').decode()
SCORE = {'feature':8, 'bite':8, 'creativity':4, 'novelty':5, 'evidence':'太い眉', 'reason':'特徴に刺さる'}
RAW = {'player':SCORE, 'cpu':{'text':'その口、プリン専用改札かよ！', 'score':SCORE}}

class GeminiTests(unittest.TestCase):
    def body(self, **values):
        return {'text':'眉毛が海苔の不法占拠かよ', 'round':1, 'playerHistory':[], 'cpuHistory':[], 'playerImage':PNG, 'cpuImage':PNG, **values}

    def completed(self):
        return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(RAW)}]}}]}

    def response(self, value):
        return io.BytesIO(json.dumps(value).encode())

    def test_native_payload_image_header_and_schema(self):
        content = [{'type':'input_text','text':'顔の採点'}, {'type':'input_image','image_url':PNG}]
        with patch.dict(os.environ, {'GEMINI_API_KEY':'mock-only-gemini-key'}), patch('gemini_gateway.urlopen',return_value=self.response(self.completed())) as call:
            result = gemini_gateway.generate('gemini-2.5-flash-lite', 'instructions', content, server.MODEL_SCHEMA)
        self.assertEqual(result,RAW)
        req=call.call_args.args[0]
        self.assertNotIn('mock-only-gemini-key',req.full_url)
        self.assertNotIn('mock-only-gemini-key',req.data.decode())
        self.assertEqual(req.get_header('X-goog-api-key'),'mock-only-gemini-key')
        body=json.loads(req.data)
        self.assertEqual(body['systemInstruction']['parts'][0]['text'],'instructions')
        self.assertEqual(body['contents'][0]['parts'][1]['inlineData']['mimeType'],'image/png')
        self.assertEqual(body['generationConfig']['responseJsonSchema'],server.MODEL_SCHEMA)
        self.assertEqual(body['generationConfig']['thinkingConfig']['thinkingBudget'],0)

    def test_current_model_uses_minimal_thinking_and_reports_404_model(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'mock-key'}), patch('gemini_gateway.urlopen',return_value=self.response(self.completed())) as call:
            gemini_gateway.generate('gemini-3.1-flash-lite', '', [], server.MODEL_SCHEMA)
        req = call.call_args.args[0]
        self.assertIn('/gemini-3.1-flash-lite:generateContent',req.full_url)
        self.assertEqual(json.loads(req.data)['generationConfig']['thinkingConfig'], {'thinkingLevel':'MINIMAL'})
        error=HTTPError('https://example.invalid',404,'error',{},io.BytesIO(b'details'))
        with patch.dict(os.environ, {'GEMINI_API_KEY':'mock-key'}), patch('gemini_gateway.urlopen',side_effect=error):
            with self.assertRaises(gemini_gateway.GeminiError) as caught:
                gemini_gateway.generate('gemini-2.5-flash-lite', '', [], {})
        self.assertIn('gemini-2.5-flash-lite',str(caught.exception))
        self.assertIn('gemini-3.1-flash-lite',str(caught.exception))
        self.assertIn('環境変数',str(caught.exception))

    def test_missing_key_does_not_call_network(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':''}), patch('gemini_gateway.urlopen') as call:
            with self.assertRaises(gemini_gateway.GeminiError): gemini_gateway.generate('model','',[],{})
        call.assert_not_called()

    def test_model_rejected_before_network(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'mock-key'}), patch('gemini_gateway.urlopen') as call:
            with self.assertRaises(gemini_gateway.GeminiError): gemini_gateway.generate('../bad?key=123','',[],{})
        call.assert_not_called()

    def test_quota_errors_do_not_fallback_or_expose_upstream(self):
        for code in [400,401,403,404,429,500]:
            error=HTTPError('https://example.invalid',code,'upstream-secret',{},io.BytesIO(b'secret-body'))
            with patch.dict(os.environ, {'GEMINI_API_KEY':'mock-only-gemini-key'}), patch('gemini_gateway.urlopen',side_effect=error), patch('openai_gateway.generate') as other:
                with self.assertRaises(gemini_gateway.GeminiError) as caught: gemini_gateway.generate('gemini-2.5-flash-lite','',[],{})
                self.assertNotIn('secret',str(caught.exception))
                self.assertNotIn('mock-only-gemini-key',str(caught.exception))
                if code==429:
                    self.assertEqual(caught.exception.status,429)
                    self.assertIn('無料枠',str(caught.exception))
                other.assert_not_called()

    def test_incomplete_blocked_and_malformed_response(self):
        for response in [{}, {'promptFeedback':{'blockReason':'SAFETY'}}, {'candidates':[{'finishReason':'MAX_TOKENS'}]}, {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'bad json'}]}}]}]:
            with patch.dict(os.environ, {'GEMINI_API_KEY':'mock-key'}), patch('gemini_gateway.urlopen',return_value=self.response(response)):
                with self.assertRaises(gemini_gateway.GeminiError): gemini_gateway.generate('gemini-2.5-flash-lite','',[],{})
        with patch.dict(os.environ, {'GEMINI_API_KEY':'mock-key'}), patch('gemini_gateway.urlopen',side_effect=URLError('offline')):
            with self.assertRaises(gemini_gateway.GeminiError): gemini_gateway.generate('gemini-2.5-flash-lite','',[],{})

    def test_shared_round_sends_both_faces_once_and_never_calls_gpt(self):
        with patch('server.gemini_gateway.generate',return_value=RAW) as call, patch('server.openai_gateway.generate') as other:
            result=server.run_gemini_round(self.body(playerHistory=['前の発言'],cpuHistory=['CPUの前の発言']))
        call.assert_called_once()
        other.assert_not_called()
        model, instructions, content, schema=call.call_args.args
        self.assertEqual(model,server.GEMINI_MODEL)
        self.assertEqual(len([p for p in content if p['type']=='input_image']),2)
        self.assertIn('CPUの前の発言',content[0]['text'])
        self.assertEqual(result['player']['mode'],'gemini')
        self.assertEqual(result['player']['damage'],25)
        self.assertEqual(result['cpu']['score']['damage'],25)

    def test_input_and_model_scores_are_validated(self):
        with patch('server.gemini_gateway.generate') as call:
            with self.assertRaises(ValueError): server.run_gemini_round(self.body(cpuImage='bad'))
            call.assert_not_called()
        with patch('server.gemini_gateway.generate',return_value={'player':{**SCORE,'bite':99},'cpu':RAW['cpu']}):
            with self.assertRaises(ValueError): server.run_gemini_round(self.body())

    def test_startup_key_is_set_in_server_process_without_printing_it(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':''}), patch('server.JUDGE_MODE','gemini'), patch('server.sys.stdin.isatty',return_value=True), patch('server.getpass.getpass',return_value='mock-startup-key'), patch('server.save_key') as save, patch('builtins.print') as output:
            server.configure_startup_key()
            self.assertTrue(gemini_gateway.configured())
            save.assert_called_once_with(server.ROOT / '.env', 'mock-startup-key')
            self.assertEqual(os.environ['GEMINI_API_KEY'],'mock-startup-key')
            self.assertNotIn('mock-startup-key',str(output.call_args_list))

    def test_existing_key_is_not_prompted_or_overwritten(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'already-set'}), patch('server.JUDGE_MODE','gemini'), patch('server.getpass.getpass') as prompt:
            server.configure_startup_key()
            prompt.assert_not_called()
            self.assertEqual(os.environ['GEMINI_API_KEY'],'already-set')

    def test_startup_blank_or_noninteractive_does_not_set_key(self):
        for interactive in [True,False]:
            with patch.dict(os.environ, {'GEMINI_API_KEY':''}), patch('server.JUDGE_MODE','gemini'), patch('server.sys.stdin.isatty',return_value=interactive), patch('server.getpass.getpass',return_value='  ') as prompt, patch('builtins.print'):
                server.configure_startup_key()
                self.assertFalse(gemini_gateway.configured())
                if not interactive: prompt.assert_not_called()

    def test_startup_save_failure_keeps_key_for_current_process(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':''}), patch('server.JUDGE_MODE','gemini'), patch('server.sys.stdin.isatty',return_value=True), patch('server.getpass.getpass',return_value='mock-unsaved-key'), patch('server.save_key',side_effect=OSError('denied')), patch('builtins.print') as output:
            server.configure_startup_key()
            self.assertEqual(os.environ['GEMINI_API_KEY'], 'mock-unsaved-key')
            self.assertIn('保存できません', str(output.call_args_list))
            self.assertNotIn('mock-unsaved-key', str(output.call_args_list))

    def test_startup_saved_key_loads_without_second_prompt(self):
        import tempfile
        from pathlib import Path
        from local_settings import load_env
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'GEMINI_API_KEY':''}), patch('server.ROOT', Path(directory)), patch('server.JUDGE_MODE','gemini'), patch('server.sys.stdin.isatty',return_value=True), patch('server.getpass.getpass',return_value='mock-remembered-key') as prompt, patch('builtins.print'):
            server.configure_startup_key()
            os.environ.pop('GEMINI_API_KEY')
            load_env(Path(directory) / '.env')
            server.configure_startup_key()
            self.assertEqual(prompt.call_count, 1)
            self.assertEqual(os.environ['GEMINI_API_KEY'], 'mock-remembered-key')
            self.assertEqual((Path(directory) / '.env').stat().st_mode & 0o777, 0o600)

    def test_status_does_not_publish_key(self):
        handler=object.__new__(server.Handler)
        handler.path='/api/gemini/status'
        with patch.dict(os.environ, {'GEMINI_API_KEY':'mock-secret'}), patch.object(handler,'send_json') as send:
            handler.do_GET()
        send.assert_called_once_with(200,{'configured':True,'model':server.GEMINI_MODEL})

if __name__=='__main__': unittest.main()
