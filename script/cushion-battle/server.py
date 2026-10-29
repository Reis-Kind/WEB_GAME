"""Standalone local launcher for Cushion Arena (Python standard library only)."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path not in ('/', '/index.html', '/style.css', '/game.js', '/physics.js', '/abilities.js', '/items.js', '/sound.js', '/combat.js'):
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self):
        if urlsplit(self.path).path not in ('/', '/index.html', '/style.css', '/game.js', '/physics.js', '/abilities.js', '/items.js', '/sound.js', '/combat.js'):
            self.send_error(404)
            return
        super().do_HEAD()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description='らくがきクッション・アリーナ専用サーバー')
    parser.add_argument('--port', type=int, default=8001)
    parser.add_argument('--lan', action='store_true', help='同じWi-Fiのスマホから接続を許可')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port は1〜65535で指定してください')
    handler = partial(Handler, directory=str(ROOT))
    try:
        server = ThreadingHTTPServer(('0.0.0.0' if args.lan else '127.0.0.1', args.port), handler)
    except OSError as exc:
        parser.exit(1, f'起動できません: {exc}\n別の --port を指定してください。\n')
    print(f'クッション・アリーナ: http://127.0.0.1:{args.port}', flush=True)
    if args.lan:
        print(f'スマホでは http://PCのLAN内IP:{args.port}/ を開いてください。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
