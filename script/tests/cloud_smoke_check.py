"""Local HTTP smoke test of cloud HTTPS origins + remote DB. No external API calls."""
import json
import tempfile
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import server
import rankings
from test_turso_store import WireDatabase


def main():
    with tempfile.TemporaryDirectory() as directory:
        wire = WireDatabase(str(Path(directory) / 'remote.sqlite3'))
        def store():
            return rankings.Rankings(Path(directory) / 'must-not-create.sqlite3', server.run_ranked_round,
                server.png_image, remote_url='libsql://example.turso.io', remote_token='mock-token')
        class QuietHandler(server.Handler):
            def log_message(self, *args):
                pass
        http = server.ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        http.public_share = True
        base = 'http://127.0.0.1:' + str(http.server_port)
        def request(path, data=None, origin='https://public.example'):
            headers = {'Host': 'public.example', 'Origin': origin, 'Content-Type': 'application/json'}
            req = Request(base + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
            with urlopen(req, timeout=10) as response:
                return response.read()
        with patch('turso_store.urlopen', side_effect=wire), patch.object(server, 'JUDGE_MODE', 'demo'), patch.object(server, 'ranking_store', store()):
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                assert json.loads(request('/healthz')) == {'ok': True}
                assert b'<html' in request('/')
                for path in ['/.env', '/turso_store.py', '/render.yaml', '/.data/rankings.sqlite3']:
                    try:
                        request(path)
                        raise AssertionError('private path served: ' + path)
                    except HTTPError as error:
                        assert error.code == 404
                image = 'data:image/png;base64,iVBORw0KGgo='
                body = {'playerImage': image, 'cpuImage': image, 'difficulty': 'easy', 'enemy': 'mame'}
                try:
                    request('/api/ranking/start', body, 'https://different.example')
                    raise AssertionError('foreign origin accepted')
                except HTTPError as error:
                    assert error.code == 403
                session = json.loads(request('/api/ranking/start', body))
                for number, text in enumerate(['眉毛、海苔', '鼻みたい', '口、パン'], 1):
                    result = json.loads(request('/api/ranking/round', {**session, 'round': number, 'text': text}))
                    assert 0 <= result['player']['damage'] <= 30
                data = {**session, 'name': 'クラウド確認'}
                assert json.loads(request('/api/ranking/register', data))['damage'] == 73
                assert json.loads(request('/api/ranking/register', data))['registered']
                # New process/store: registered results survive, active sessions do not.
                server.ranking_store = store()
                entries = json.loads(request('/api/leaderboard?difficulty=easy'))['entries']
                assert len(entries) == 1 and entries[0]['damage'] == 73
                game_id = entries[0]['id']
                log = json.loads(request('/api/ranking/log?id=' + game_id))
                assert len(log['turns']) == 3
                assert request('/api/ranking/face?id=' + game_id).startswith(b'\x89PNG')
                assert not (Path(directory) / 'must-not-create.sqlite3').exists()
                assert not wire.connections
                print('PASS: cloud HTTP/HTTPS origin; private files 404; 3 demo rounds; atomic registration/retry; score/log/face survive store restart; no local DB fallback; no external API calls')
            finally:
                http.shutdown()
                http.server_close()
                thread.join()


if __name__ == '__main__':
    main()
