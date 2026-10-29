"""Small sqlite-compatible subset for rankings, using Turso's HTTPS SQL API.

Writes are buffered and committed in one conditional batch (no network gaps
inside Turso's five-second transaction window). Never log credentials.
"""
import json
import sqlite3
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class Cursor:
    def __init__(self, connection, index):
        self.connection, self.index = connection, index
        self.rows = None

    def fetchall(self):
        if self.rows is None:
            self.rows = self.connection.flush()[self.index]
        rows, self.rows = self.rows, []
        return rows

    def fetchone(self):
        rows = self.fetchall()
        self.rows = rows[1:]
        return rows[0] if rows else None


def value(item):
    kind = item['type']
    if kind == 'null':
        return None
    if kind == 'integer':
        return int(item['value'])
    if kind == 'float':
        return float(item['value'])
    if kind == 'text':
        return item['value']
    raise ValueError('Unsupported database value')


def argument(item):
    if item is None:
        return {'type': 'null'}
    if isinstance(item, int):
        return {'type': 'integer', 'value': str(item)}
    if isinstance(item, str):
        return {'type': 'text', 'value': item}
    raise ValueError('Unsupported query parameter')


class Connection:
    def __init__(self, url, token):
        url = url.replace('libsql://', 'https://', 1).replace('turso://', 'https://', 1)
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or
                parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
            raise ValueError('TURSO_DATABASE_URLにはHTTPSまたはlibsqlのデータベースURLを設定してください。')
        if not token.strip():
            raise ValueError('TURSO_AUTH_TOKENが未設定です。')
        self.endpoint = url.rstrip('/') + '/v2/pipeline'
        self.token = token
        self.pending = []

    def request(self, requests):
        payload = {'requests': requests}
        request = Request(self.endpoint, data=json.dumps(payload).encode(), headers={
            'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=15) as response:
                body = json.load(response)
            # Keep the original trusted endpoint; do not forward the token to a response URL.
            results = body['results']
            if len(results) != len(requests) or any(r['type'] != 'ok' for r in results):
                raise ValueError('Database operation failed')
            return results
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise sqlite3.OperationalError('ランキング用データベースに接続できません。') from error

    def execute(self, sql, params=()):
        index = len(self.pending)
        self.pending.append({'sql': sql, 'args': [argument(p) for p in params], 'want_rows': True})
        return Cursor(self, index)

    def flush(self):
        if not self.pending:
            return []
        statements, self.pending = self.pending, []
        steps = [{'stmt': {'sql': 'BEGIN'}}]
        for statement in [*statements, {'sql': 'COMMIT'}]:
            steps.append({'condition': {'type': 'ok', 'step': len(steps)-1}, 'stmt': statement})
        # Closing the stream rolls back a failed transaction. COMMIT only runs
        # if every previous step succeeded; registration is all-or-nothing.
        response = self.request([{'type': 'batch', 'batch': {'steps': steps}}, {'type': 'close'}])[0]
        try:
            result = response['response']['result']
            if any(result['step_errors']) or any(r is None for r in result['step_results']):
                raise ValueError('Database batch failed')
            return [[tuple(value(v) for v in row) for row in r['rows']]
                    for r in result['step_results'][1:-1]]
        except (KeyError, TypeError, ValueError) as error:
            raise sqlite3.OperationalError('ランキング用データベースの処理に失敗しました。') from error

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        if kind is None:
            self.flush()
        else:
            self.pending.clear()

    def close(self):
        self.pending.clear()
