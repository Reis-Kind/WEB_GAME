"""Save the Gemini key locally once; subsequent starts read .env automatically."""
import getpass
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parent


def save_settings(path, values):
    from local_settings import ALLOWED
    clean = {}
    for name, value in values.items():
        value = value.strip()
        if name not in ALLOWED or not value or any(c in value for c in ('\r', '\n', '\0', '"', "'")):
            raise ValueError('設定名・空の値・改行・引用符を確認してください。')
        clean[name] = value
    path = Path(path)
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    for name in clean:
        lines = [line for line in lines if not re.match(r'^\s*(?:export\s+)?' + re.escape(name) + r'\s*=', line)]
    lines.extend(name + '=' + value for name, value in clean.items())
    # A private temporary file + replace avoids a partially written or world-readable key.
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix='.key-', delete=False) as output:
            name = output.name
            os.chmod(name, 0o600)
            output.write('\n'.join(lines) + '\n')
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def save_key(path, key):
    save_settings(path, {'GEMINI_API_KEY': key})


def main():
    key = getpass.getpass('Gemini API key（入力は非表示）: ')
    if not key.strip():
        print('保存せず終了しました。')
        return
    try:
        save_key(ROOT / '.env', key)
    except (OSError, ValueError):
        print('保存できませんでした。キーの形式とフォルダの書き込み権限を確認してください。')
        raise SystemExit(1)
    print('.env に保存しました。次回からAPIキーの入力は不要です。')
    print('uv run share.py または python3 share.py で起動してください。')


if __name__ == '__main__':
    main()
