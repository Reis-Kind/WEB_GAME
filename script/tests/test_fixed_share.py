import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from setup_share import validate_ngrok_url
from setup_key import save_settings
from local_settings import load_env
from share import tunnel_command, tunnel_env


class FixedShareTests(unittest.TestCase):
    def test_url_is_normalized(self):
        self.assertEqual(validate_ngrok_url('demo.ngrok-free.app/'), 'https://demo.ngrok-free.app')
        self.assertEqual(validate_ngrok_url('https://demo.ngrok-free.dev'), 'https://demo.ngrok-free.dev')

    def test_only_assigned_https_domain_is_accepted(self):
        for value in ('', 'http://demo.ngrok-free.app', 'https://bad.example', 'https://user:pass@demo.ngrok-free.app', 'demo.ngrok-free.app/path', 'demo.ngrok-free.app?token=x', 'demo.ngrok-free.app:443', 'demo.ngrok-free.app#fragment'):
            with self.assertRaises(ValueError): validate_ngrok_url(value)

    def test_fixed_command_uses_same_url_and_no_token_in_arguments(self):
        with patch.dict(os.environ, {'NGROK_AUTHTOKEN':'mock-token','NGROK_URL':'https://demo.ngrok-free.app'}, clear=True), patch('share.shutil.which', return_value='/tools/ngrok'):
            command = tunnel_command('ngrok', 8010)
            self.assertEqual(command, tunnel_command('ngrok', 8010))
            self.assertIn('https://demo.ngrok-free.app', command)
            self.assertIn('http://127.0.0.1:8010', command)
            self.assertNotIn('mock-token', ' '.join(command))
            self.assertIn('--inspect=false', command)

    def test_missing_token_fails_without_random_url_fallback(self):
        with patch.dict(os.environ, {}, clear=True), patch('share.shutil.which', return_value='/tools/ngrok'):
            with self.assertRaisesRegex(ValueError, 'setup_share.py'): tunnel_command('ngrok', 8000)

    def test_child_environment_does_not_receive_model_keys(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'mock-gemini','OPENAI_API_KEY':'mock-gpt','NGROK_AUTHTOKEN':'mock-tunnel'}, clear=True):
            self.assertEqual(tunnel_env('ngrok'), {'NGROK_AUTHTOKEN':'mock-tunnel'})
            self.assertEqual(tunnel_env('cloudflare'), {})

    def test_configuration_preserves_gemini_key(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / '.env'
            path.write_text('GEMINI_API_KEY=mock-gemini\n')
            save_settings(path, {'SHARE_PROVIDER':'ngrok','NGROK_AUTHTOKEN':'mock-token','NGROK_URL':'https://demo.ngrok-free.app'})
            load_env(path)
            self.assertEqual(os.environ['GEMINI_API_KEY'], 'mock-gemini')
            self.assertEqual(os.environ['SHARE_PROVIDER'], 'ngrok')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_cloudflare_still_supported(self):
        with patch('share.shutil.which', return_value='/tools/cloudflared'):
            self.assertEqual(tunnel_command('cloudflare',8000), ['/tools/cloudflared','tunnel','--url','http://127.0.0.1:8000','--no-autoupdate'])


if __name__ == '__main__': unittest.main()
