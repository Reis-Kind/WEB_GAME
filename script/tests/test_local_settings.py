import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from local_settings import load_env
from setup_key import save_key


class LocalSettingsTests(unittest.TestCase):
    def test_save_reload_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / '.env'
            save_key(path, 'mock-key-only')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            load_env(path)
            self.assertEqual(os.environ['GEMINI_API_KEY'], 'mock-key-only')
            self.assertFalse(list(Path(directory).glob('.key-*')))

    def test_update_preserves_other_settings_and_removes_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('# Keep comment\nGEMINI_MODEL=test-model\nGEMINI_API_KEY=old\nexport GEMINI_API_KEY=old2\n')
            save_key(path, 'replacement-mock')
            content = path.read_text()
            self.assertIn('# Keep comment', content)
            self.assertIn('GEMINI_MODEL=test-model', content)
            self.assertEqual(content.count('GEMINI_API_KEY='), 1)

    def test_environment_wins_and_only_supported_names_load(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'GEMINI_API_KEY':'from-terminal'}, clear=True):
            path = Path(directory) / '.env'
            path.write_text('GEMINI_API_KEY=from-file\nexport OPENAI_API_KEY="mock-gpt"\nHOME=wrong\nGEMINI_MODEL=literal$(not-a-command)\n')
            load_env(path)
            self.assertEqual(os.environ['GEMINI_API_KEY'], 'from-terminal')
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'mock-gpt')
            self.assertNotIn('HOME', os.environ)
            self.assertEqual(os.environ['GEMINI_MODEL'], 'literal$(not-a-command)')

    def test_invalid_save_keeps_original_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('GEMINI_API_KEY=original\n')
            for key in ('', '  ', 'bad\nKEY=value', 'bad"key'):
                with self.assertRaises(ValueError): save_key(path, key)
                self.assertEqual(path.read_text(), 'GEMINI_API_KEY=original\n')

    def test_missing_file_and_bad_quotes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            load_env(path)
            path.write_text('GEMINI_API_KEY="mock-missing-quote\n')
            with self.assertRaisesRegex(ValueError, '1行目'):
                load_env(path)


if __name__ == '__main__': unittest.main()
