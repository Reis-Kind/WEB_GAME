"""Sharing settings stored separately from the face game."""
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
SHARING_KEYS = {'NGROK_URL', 'NGROK_AUTHTOKEN', 'SHARE_PROVIDER'}


def read_settings(path):
    path = Path(path)
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, sep, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if sep and key in SHARING_KEYS:
            if value.startswith(('"', "'")):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError('共有設定の引用符を確認してください。')
                value = value[1:-1]
            result[key] = value
    return result


def validate_url(value):
    value = value.strip()
    if '://' not in value:
        value = 'https://' + value
    parsed = urlsplit(value)
    host = parsed.netloc.lower()
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host)
            or not any(host.endswith('.' + suffix) for suffix in ('ngrok-free.app', 'ngrok-free.dev', 'ngrok.app', 'ngrok.io'))
            or '..' in host):
        raise ValueError('ngrokのDomains画面にあるクッション専用のHTTPSドメインを入力してください。')
    return 'https://' + host


def ensure_separate(value):
    # Kept as a compatibility alias; reusing the existing domain is authorized.
    return validate_url(value)
