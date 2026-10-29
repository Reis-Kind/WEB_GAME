"""Configure an account-assigned, free ngrok URL once."""
import getpass
from pathlib import Path
import re
from urllib.parse import urlsplit
from setup_key import save_settings


def validate_ngrok_url(value):
    value = value.strip()
    if '://' not in value:
        value = 'https://' + value
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.ngrok-free\.(?:app|dev)', parsed.netloc)):
        raise ValueError('ngrokのDomains画面にある無料の割り当てURLを入力してください。')
    return 'https://' + parsed.netloc


def main():
    print('初回だけngrokの無料アカウントが必要です。https://dashboard.ngrok.com/signup')
    print('Authtoken: https://dashboard.ngrok.com/get-started/your-authtoken')
    token = getpass.getpass('ngrok Authtoken（Geminiキーとは別・入力は非表示）: ').strip()
    if not token:
        print('保存せず終了しました。')
        return
    print('固定URL: https://dashboard.ngrok.com/domains に表示される割り当てURLをコピーしてください。')
    try:
        url = validate_ngrok_url(input('固定URL: '))
        save_settings(Path(__file__).resolve().parent / '.env', {
            'NGROK_AUTHTOKEN': token, 'NGROK_URL': url, 'SHARE_PROVIDER': 'ngrok'})
    except (ValueError, OSError):
        print('保存できませんでした。無料の割り当てURLと書き込み権限を確認してください。')
        raise SystemExit(1)
    print('固定URLの設定を保存しました。次回から uv run share.py で同じURLを使います。')


if __name__ == '__main__':
    main()
