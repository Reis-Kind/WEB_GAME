"""Internet sharing with Cloudflare Quick Tunnel or a fixed ngrok URL."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import threading
from http.server import ThreadingHTTPServer
import server
from setup_share import validate_ngrok_url


def tunnel_command(provider, port):
    name = {'cloudflare': 'cloudflared', 'ngrok': 'ngrok'}.get(provider)
    if not name:
        raise ValueError('共有方法は cloudflare または ngrok を指定してください。')
    binary = shutil.which(name)
    local = Path(__file__).resolve().parent / '.tools' / name
    if not binary and local.is_file():
        binary = str(local)
    if not binary:
        raise ValueError(f'{name} がありません。READMEの共有手順を確認してください。')
    upstream = f'http://127.0.0.1:{port}'
    if provider == 'ngrok':
        if not os.environ.get('NGROK_AUTHTOKEN', '').strip():
            raise ValueError('固定URLの初回設定が必要です。uv run setup_share.py を実行してください。')
        url = validate_ngrok_url(os.environ.get('NGROK_URL', ''))
        return [binary, 'http', upstream, '--url', url, '--inspect=false', '--log=stdout']
    return [binary, 'tunnel', '--url', upstream, '--no-autoupdate']


def tunnel_env(provider):
    hidden = {'GEMINI_API_KEY', 'OPENAI_API_KEY', 'GAME_SHARE_PASSWORD'}
    if provider != 'ngrok':
        hidden.add('NGROK_AUTHTOKEN')
    return {k: v for k, v in os.environ.items() if k not in hidden}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--provider', choices=('cloudflare', 'ngrok'), default=os.environ.get('SHARE_PROVIDER', 'cloudflare'))
    args = parser.parse_args()
    try:
        command = tunnel_command(args.provider, args.port)
    except ValueError as error:
        parser.error(str(error))
    try:
        httpd = ThreadingHTTPServer(('127.0.0.1', args.port), server.Handler)
    except OSError:
        parser.error('ポートを使用中です。起動中のserver.pyをCtrl+Cで止めるか --port 8001 を指定してください。')
    httpd.public_share = True
    tunnel = None
    try:
        server.configure_startup_key()
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
