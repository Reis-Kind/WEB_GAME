"""CPU damage leaderboards. Clients never supply a score to register."""
from contextlib import contextmanager
from pathlib import Path
import re
import json
import base64
import math
import secrets
import sqlite3
import threading
import time
import unicodedata
from turso_store import Connection as TursoConnection

CPU_LINES = [
    'その顔、月曜の会議で三時間説教されたおにぎりかよ！具までやる気なくしてんぞ！',
    'その目、圏外のアンテナみたいだな！宇宙にまで既読スルーされてんのかよ！',
    'その口、プリン専用の改札かよ！悪口だけ特急で通過させんな！',
]
DIFFICULTIES = ('easy', 'normal', 'hard')


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).lower()
                   if not c.isspace() and unicodedata.category(c)[0] not in ('P', 'S'))


def demo_score(text, history):
    word = normalized(text)
    damage = min(30, 6 + 5 * bool(re.search('みたい|まるで|ような|ように|そっくり|たとえ|かよ|並み|すぎ|まんま', text))
                 + 12 * bool(re.search('目|眼|眉|まゆ|鼻|口|くち|耳|髪|かみ|輪郭|ほっぺ|顔|かお|あご|おでこ', text))
                 + 7 * bool(re.search('海苔|のり|会議|渋滞|信号|滑走路|アンテナ|おにぎり|パン|電車|月|山|毛虫|カーテン|バナナ|定規|Wi-Fi|wifi|プリン|宇宙|寝ぐせ|看板', text)))
    def similar(a, b):
        if a == b: return True
        x, y = set(zip(a, a[1:])), set(zip(b, b[1:]))
        return bool(x and y) and 2 * len(x & y) / (len(x) + len(y)) >= .72
    if not word:
        damage = 0
    elif any(similar(word, normalized(past)) for past in history):
        damage = 2
    return {'damage': damage, 'reason': 'デモ判定：単語と重複による仮採点です。画像との一致や本当の面白さは判定していません。', 'mode': 'demo'}


class RankingError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Rankings:
    def __init__(self, database, judge, image_check, clock=time.monotonic, remote_url=None, remote_token=None):
        self.database = Path(database)
        self.remote_url = remote_url
        self.remote_token = remote_token
        if bool(remote_url) != bool(remote_token):
            raise ValueError("TURSO_DATABASE_URLとTURSO_AUTH_TOKENは両方設定してください。")
        self.judge = judge
        self.image_check = image_check
        self.clock = clock
        self.lock = threading.RLock()
        self.workers = threading.BoundedSemaphore(2)
        self.games = {}

    @contextmanager
    def db(self):
        if self.remote_url:
            db = TursoConnection(self.remote_url, self.remote_token)
        else:
            self.database.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.database, timeout=10)
        try:
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS cpu_scores (game TEXT PRIMARY KEY, name TEXT NOT NULL, mode TEXT NOT NULL, difficulty TEXT NOT NULL, enemy TEXT NOT NULL, damage INTEGER NOT NULL CHECK(damage BETWEEN 0 AND 90), created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
                db.execute('CREATE TABLE IF NOT EXISTS cpu_logs (game TEXT PRIMARY KEY, payload TEXT NOT NULL)')
                db.execute('CREATE TABLE IF NOT EXISTS cpu_faces (game TEXT PRIMARY KEY, png TEXT NOT NULL)')
                yield db
        finally:
            db.close()

    def leaderboard(self, mode, difficulty):
        if difficulty not in DIFFICULTIES:
            raise RankingError('難易度が不正です。')
        with self.db() as db:
            rows = db.execute('SELECT name, damage, enemy, game, EXISTS(SELECT 1 FROM cpu_logs WHERE cpu_logs.game=cpu_scores.game), EXISTS(SELECT 1 FROM cpu_faces WHERE cpu_faces.game=cpu_scores.game) FROM cpu_scores WHERE mode=? AND difficulty=? ORDER BY damage DESC, created ASC, game ASC LIMIT 20', (mode, difficulty)).fetchall()
        entries, previous, rank = [], None, 0
        for i, (name, damage, enemy, game_id, has_log, has_face) in enumerate(rows, 1):
            if damage != previous: rank = i
            entries.append({'rank': rank, 'name': name, 'damage': damage, 'enemy': enemy, 'id': game_id, 'hasLog': bool(has_log), 'hasFace': bool(has_face)})
            previous = damage
        return {'mode': mode, 'difficulty': difficulty, 'entries': entries}

    def detail(self, game_id):
        if not isinstance(game_id, str) or not re.fullmatch(r'[0-9a-f]{32}', game_id):
            raise RankingError('対戦記録が見つかりません。', 404)
        with self.db() as db:
            row = db.execute('SELECT s.name,s.damage,s.enemy,s.mode,s.difficulty,s.created,l.payload,EXISTS(SELECT 1 FROM cpu_faces WHERE cpu_faces.game=s.game) FROM cpu_scores s LEFT JOIN cpu_logs l ON l.game=s.game WHERE s.game=?', (game_id,)).fetchone()
        if row is None:
            raise RankingError('対戦記録が見つかりません。', 404)
        name, damage, enemy, mode, difficulty, created, payload, has_face = row
        return {'id': game_id, 'name': name, 'damage': damage, 'enemy': enemy, 'mode': mode,
                'difficulty': difficulty, 'created': created, 'hasFace': bool(has_face), 'turns': json.loads(payload) if payload else None}

    def face(self, game_id):
        if not isinstance(game_id, str) or not re.fullmatch(r'[0-9a-f]{32}', game_id):
            raise RankingError('顔画像が見つかりません。', 404)
        with self.db() as db:
            row = db.execute('SELECT f.png FROM cpu_faces f JOIN cpu_scores s ON s.game=f.game WHERE f.game=?', (game_id,)).fetchone()
        if row is None:
            raise RankingError('この記録には顔画像がありません。', 404)
        self.image_check(row[0])
        return base64.b64decode(row[0].split(',', 1)[1], validate=True)

    def cleanup(self):
        now = self.clock()
        for token in list(self.games):
            if now - self.games[token]['touched'] > 1800 and not self.games[token]['busy']:
                del self.games[token]

    def start(self, body, mode):
        difficulty, enemy = body.get('difficulty'), body.get('enemy')
        if difficulty not in DIFFICULTIES or enemy not in ('mame', 'nobio', 'kakube', 'pote', 'sankichi', 'higemochi'):
            raise RankingError('難易度や対戦相手が不正です。')
        for key in ('playerImage', 'cpuImage'):
            self.image_check(body.get(key))
        with self.lock:
            self.cleanup()
            if len(self.games) >= 256:
                raise RankingError('対戦が混雑しています。しばらく待ってください。', 429)
            token = secrets.token_urlsafe(32)
            self.games[token] = {'id': secrets.token_hex(16), 'mode': mode, 'difficulty': difficulty, 'enemy': enemy,
                                 'playerImage': body['playerImage'], 'cpuImage': body['cpuImage'], 'portrait': body['playerImage'],
                                 'visualMemory': {}, 'turns': [], 'playerHistory': [], 'cpuHistory': [], 'busy': False, 'touched': self.clock(), 'registered': False}
            return {'token': token, 'mode': mode}

    def auth(self, body):
        self.cleanup()
        token = body.get('token')
        game = self.games.get(token) if isinstance(token, str) else None
        if game is None:
            raise RankingError('対戦記録の有効期限が切れました。新しい対戦を始めてください。', 404)
        game['touched'] = self.clock()
        return game

    def play(self, body):
        with self.lock:
            game = self.auth(body)
            number, text = body.get('round'), body.get('text')
            if type(number) is not int or not 1 <= number <= 3 or not isinstance(text, str) or not 1 <= len(text.strip()) <= 120:
                raise RankingError('ラウンドまたは発言が不正です。')
            text = text.strip()
            if number <= len(game['turns']):
                previous = game['turns'][number-1]
                if previous['player']['text'] == text:
                    return previous['response']  # Lost-response retry, no second AI request.
                raise RankingError('このラウンドは確定済みです。', 409)
            if number != len(game['turns']) + 1 or game['busy']:
                raise RankingError('攻撃の順序が不正か、採点中です。', 409)
            if not self.workers.acquire(blocking=False):
                raise RankingError('採点が混雑しています。少し待って再送信してください。', 429)
            game['busy'] = True
            task = {key: game[key] for key in ('playerImage', 'cpuImage')}
            if game['mode'] == 'gemini':
                task['_visualMemory'] = game['visualMemory']
            task.update(text=text, round=number, playerHistory=list(game['playerHistory']), cpuHistory=list(game['cpuHistory']))
        try:
            response = self.judge(task, game['mode'])
            # Validate both results before committing either score or history.
            for result in (response['player'], response['cpu']['score']):
                if type(result.get('damage')) is not int or not 0 <= result['damage'] <= 30 or not isinstance(result.get('reason'), str):
                    raise ValueError('採点結果の形式が不正です。')
            reply = response['cpu']['text']
            if not isinstance(reply, str) or not 1 <= len(reply.strip()) <= 120:
                raise ValueError('CPUの返答が不正です。')
            with self.lock:
                game['turns'].append({'player': {'text': text, 'damage': response['player']['damage']}, 'response': response})
                game['playerHistory'].append(text)
                game['cpuHistory'].append(reply)
                if len(game['turns']) == 3:
                    # Finished games only need scores for registration/retries.
                    game.pop('playerImage', None)
                    game.pop('cpuImage', None)
                    game.pop('visualMemory', None)
                return response
        finally:
            with self.lock:
                game['busy'] = False
                game['touched'] = self.clock()
            self.workers.release()

    def register(self, body):
        with self.lock:
            game = self.auth(body)
            if game['busy'] or len(game['turns']) != 3:
                raise RankingError('3ラウンドを完了してから登録してください。', 409)
            name = body.get('name')
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 20 or any(unicodedata.category(c).startswith('C') for c in name):
                raise RankingError('名前は1〜20文字にしてください。')
            damage = sum(turn['player']['damage'] for turn in game['turns'])
            hp = {'player': 100, 'cpu': 100}
            turns = []
            scale = {'easy': .6, 'normal': .8, 'hard': 1}[game['difficulty']]
            for number, turn in enumerate(game['turns'], 1):
                response = turn['response']
                player = {'text': turn['player']['text'], 'damage': turn['player']['damage'], 'reason': response['player']['reason'][:1200]}
                raw = response['cpu']['score']['damage']
                cpu = {'text': response['cpu']['text'], 'damage': math.floor(raw * scale + .5),
                       'rawDamage': raw, 'reason': response['cpu']['score']['reason'][:1200]}
                hp['cpu'] -= player['damage']
                hp['player'] -= cpu['damage']
                turns.append({'round': number, 'player': player, 'cpu': cpu, 'hp': dict(hp)})
            with self.db() as db:
                db.execute('INSERT OR IGNORE INTO cpu_scores(game,name,mode,difficulty,enemy,damage) VALUES(?,?,?,?,?,?)',
                           (game['id'], name.strip(), game['mode'], game['difficulty'], game['enemy'], damage))
                db.execute('INSERT OR IGNORE INTO cpu_logs(game,payload) VALUES(?,?)', (game['id'], json.dumps(turns, ensure_ascii=False)))
                db.execute('INSERT OR IGNORE INTO cpu_faces(game,png) VALUES(?,?)', (game['id'], game['portrait']))
            game['registered'] = True
            return {'registered': True, 'damage': damage}
