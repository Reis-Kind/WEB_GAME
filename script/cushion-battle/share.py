"""Internet sharing with Cloudflare Quick Tunnel or a fixed ngrok URL."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import threading
from http.server import ThreadingHTTPServer
import sys
from functools import partial
import server

PARENT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PARENT))
from share_settings import ROOT, read_settings, ensure_separate

validate_ngrok_url = ensure_separate


def tunnel_command(provider, port):
    name = {'cloudflare': 'cloudflared', 'ngrok': 'ngrok'}.get(provider)
    if not name:
        raise ValueError('共有方法は cloudflare または ngrok を指定してください。')
    binary = shutil.which(name)
    local = PARENT / '.tools' / name
    if not binary and local.is_file():
        binary = str(local)
    if not binary:
        raise ValueError(f'{name} がありません。READMEの共有手順を確認してください。')
    upstream = f'http://127.0.0.1:{port}'
    if provider == 'ngrok':
        if not os.environ.get('NGROK_AUTHTOKEN', '').strip():
            raise ValueError('固定URLの初回設定が必要です。python3 cushion-battle/setup_share.py（scriptフォルダで実行） を実行してください。')
        url = validate_ngrok_url(os.environ.get('NGROK_URL', ''))
        return [binary, 'http', upstream, '--url', url, '--inspect=false', '--log=stdout']
    return [binary, 'tunnel', '--url', upstream, '--no-autoupdate']


def tunnel_env(provider):
    hidden = {'GEMINI_API_KEY', 'OPENAI_API_KEY', 'GAME_SHARE_PASSWORD', 'TURSO_AUTH_TOKEN'}
    if provider != 'ngrok':
        hidden.add('NGROK_AUTHTOKEN')
    return {k: v for k, v in os.environ.items() if k not in hidden}


def main():
    try:
        settings = read_settings(ROOT / '.env')
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
    # Dedicated file values take precedence over a shell configured for the face game.
    for name in ('NGROK_URL', 'NGROK_AUTHTOKEN'):
        os.environ.pop(name, None)
        if settings.get(name):
            os.environ[name] = settings[name]
    parser = argparse.ArgumentParser(description='クッション・アリーナのスマホ共有')
    parser.add_argument('--port', type=int, default=8001)
    parser.add_argument('--provider', choices=('cloudflare', 'ngrok'), default=settings.get('SHARE_PROVIDER', 'ngrok'))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port は1〜65535で指定してください')
    try:
        command = tunnel_command(args.provider, args.port)
    except ValueError as error:
        parser.error(str(error))
    try:
        httpd = ThreadingHTTPServer(('127.0.0.1', args.port), partial(server.Handler, directory=str(server.ROOT)))
    except OSError:
        parser.error('ポートを使用中です。起動中のクッションサーバーをCtrl+Cで止めるか --port 8002 を指定してください。')
    httpd.public_share = True
    tunnel = None
    try:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        if args.provider == 'ngrok':
            print(f'固定URL（トンネル接続後に有効）: {validate_ngrok_url(os.environ["NGROK_URL"])}', flush=True)
        else:
            print('cloudflaredのログに表示される実際の https://英単語.trycloudflare.com を開いてください。', flush=True)
        print('ログイン不要です。終了はCtrl+C。', flush=True)
        # The tunnel needs no model API keys.
        env = tunnel_env(args.provider)
        tunnel = subprocess.Popen(command, env=env)
        code = tunnel.wait()
        if code:
            print('共有サービスに接続できませんでした。上のログとREADMEを確認してください。', flush=True)
            raise SystemExit(code)
    except KeyboardInterrupt:
        pass
    finally:
        if tunnel and tunnel.poll() is None:
            tunnel.terminate()
            try:
                tunnel.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tunnel.kill()
                tunnel.wait()
        httpd.shutdown()
        httpd.server_close()


if __name__ == '__main__':
    main()
