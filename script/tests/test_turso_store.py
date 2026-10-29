"""Exercise the real ranking SQL through a local implementation of Turso's wire format."""
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rankings
from turso_store import Connection


class WireDatabase:
    def __init__(self, path):
        self.path = path
        self.connections = {}
        self.requests = []
        self.fail_sql = None

    def __call__(self, request, timeout):
        self.assertions(request, timeout)
        payload = json.loads(request.data)
        baton = payload.get('baton')
        if baton is None:
            baton = str(len(self.requests))
            self.connections[baton] = sqlite3.connect(self.path, isolation_level=None)
        db = self.connections[baton]
        results = []
        for operation in payload['requests']:
            if operation['type'] == 'close':
                db.close()
                del self.connections[baton]
                baton = None
                results.append({'type': 'ok', 'response': {'type': 'close'}})
                continue
            step_results, step_errors = [], []
            for step in operation['batch']['steps']:
                condition = step.get('condition')
                if condition and step_results[condition['step']] is None:
                    step_results.append(None); step_errors.append(None)
                    continue
                stmt = step['stmt']
                self.requests.append(stmt)
                args = [int(a['value']) if a['type'] == 'integer' else a.get('value') for a in stmt.get('args', [])]
                try:
                    if self.fail_sql and self.fail_sql in stmt['sql']:
                        raise sqlite3.OperationalError('simulated failure')
                    cursor = db.execute(stmt['sql'], args)
                    rows = [[{'type': 'null'} if v is None else
                             {'type': 'integer' if isinstance(v, int) else 'text', 'value': str(v)}
                             for v in row] for row in cursor.fetchall()]
                    step_results.append({'rows': rows}); step_errors.append(None)
                except sqlite3.Error:
                    step_results.append(None); step_errors.append({'message': 'not exposed'})
            results.append({'type': 'ok', 'response': {'result': {
                'step_results': step_results, 'step_errors': step_errors}}})
        return io.BytesIO(json.dumps({'baton': baton, 'base_url': None, 'results': results}).encode())

    def assertions(self, request, timeout):
        assert request.full_url == 'https://example.turso.io/v2/pipeline'
        assert request.headers['Authorization'] == 'Bearer mock-token'
        assert timeout == 15


class TursoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.wire = WireDatabase(str(Path(self.temp.name) / 'remote.sqlite3'))
        self.patcher = patch('turso_store.urlopen', side_effect=self.wire)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def store(self):
        return rankings.Rankings('/not-used/local.sqlite3', None, lambda image: None,
            remote_url='libsql://example.turso.io', remote_token='mock-token')

    def test_ranking_log_face_survive_new_store_and_parameters_stay_bound(self):
        store = self.store()
        name = "日本語'); DROP TABLE cpu_scores;--"
        with store.db() as db:
            db.execute('INSERT INTO cpu_scores(game,name,mode,difficulty,enemy,damage) VALUES(?,?,?,?,?,?)',
                       ('a' * 32, name, 'demo', 'easy', 'mame', 73))
            db.execute('INSERT INTO cpu_logs VALUES(?,?)', ('a' * 32, '[]'))
            db.execute('INSERT INTO cpu_faces VALUES(?,?)', ('a' * 32, 'data:image/png;base64,aGVsbG8='))
        restarted = self.store()
        entry = restarted.leaderboard('demo', 'easy')['entries'][0]
        self.assertEqual((entry['damage'], entry['name'], entry['hasFace']), (73, name, True))
        self.assertEqual(restarted.detail('a' * 32)['turns'], [])
        self.assertEqual(restarted.face('a' * 32), b'hello')
        self.assertFalse(self.wire.connections)
        self.assertTrue(all(name not in stmt['sql'] for stmt in self.wire.requests))

    def test_partial_registration_is_rolled_back(self):
        store = self.store()
        self.wire.fail_sql = 'INSERT INTO cpu_logs'
        with self.assertRaises(sqlite3.OperationalError):
            with store.db() as db:
                db.execute('INSERT INTO cpu_scores(game,name,mode,difficulty,enemy,damage) VALUES(?,?,?,?,?,?)',
                           ('b' * 32, 'test', 'demo', 'easy', 'mame', 73))
                db.execute('INSERT INTO cpu_logs VALUES(?,?)', ('b' * 32, '[]'))
        self.wire.fail_sql = None
        self.assertEqual(store.leaderboard('demo', 'easy')['entries'], [])
        self.assertFalse(self.wire.connections)

    def test_network_error_is_database_error_without_secret(self):
        with patch('turso_store.urlopen', side_effect=OSError('private details')):
            with self.assertRaises(sqlite3.OperationalError) as result:
                Connection('https://example.turso.io', 'mock-token').execute('SELECT 1').fetchone()
        self.assertNotIn('private', str(result.exception))
        self.assertNotIn('mock-token', str(result.exception))

    def test_invalid_configuration_fails_without_local_fallback(self):
        with self.assertRaises(ValueError):
            rankings.Rankings('/tmp/unused', None, None, remote_url='libsql://example.turso.io')
        for url in ['http://example.turso.io', 'https://user:password@example.turso.io', 'https://example.turso.io/?token=secret']:
            with self.assertRaises(ValueError):
                Connection(url, 'mock-token')


if __name__ == '__main__':
    unittest.main()
