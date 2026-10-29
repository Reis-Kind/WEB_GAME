"""Read supported local settings as data, without shell evaluation."""
from pathlib import Path
import os

ALLOWED = {'JUDGE_MODE', 'TURSO_DATABASE_URL', 'TURSO_AUTH_TOKEN', 'GEMINI_API_KEY', 'OPENAI_API_KEY', 'GEMINI_MODEL', 'OPENAI_MODEL', 'OLLAMA_MODEL', 'OLLAMA_URL', 'SHARE_PROVIDER', 'NGROK_AUTHTOKEN', 'NGROK_URL'}


def load_env(path):
    path = Path(path)
    if not path.exists():
        return
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        name, separator, value = line.partition('=')
        name = name.strip()
        if not separator or name not in ALLOWED:
            continue
        value = value.strip()
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'.env の{number}行目の引用符を確認してください。')
            value = value[1:-1]
        if value and not os.environ.get(name, '').strip():
            os.environ[name] = value
