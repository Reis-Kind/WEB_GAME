import tempfile
import sqlite3
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import rankings
import server

IMAGE='data:image/png;base64,iVBORw0KGgo='

class RankingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.calls=[]
        def judge(body,mode):
            self.calls.append(body)
            return {'player':{'damage':23,'reason':'a'},'cpu':{'text':'CPUの目が豆','score':{'damage':10,'reason':'b'}}}
        self.store=rankings.Rankings(Path(self.temp.name)/'scores.sqlite3',judge,server.png_image)
        self.session=self.start()

    def tearDown(self):self.temp.cleanup()

    def start(self,mode='demo',difficulty='easy'):
        return self.store.start({'playerImage':IMAGE,'cpuImage':IMAGE,'difficulty':difficulty,'enemy':'mame'},mode)

    def play(self,number,**extra):
        return self.store.play({**self.session,'round':number,'text':'目が豆'+str(number),**extra})

    def finish(self):
        for n in range(1,4):self.play(n)

    def test_sum_is_server_owned_and_registration_is_idempotent(self):
        self.finish()
        for _ in range(2):
            result=self.store.register({**self.session,'name':'テスト','damage':9999,'difficulty':'hard'})
            self.assertEqual(result,{'registered':True,'damage':69})
        entries=self.store.leaderboard('demo','easy')['entries']
        self.assertEqual(len(entries),1)
        self.assertEqual({k:entries[0][k] for k in ('rank','name','damage','enemy')},{'rank':1,'name':'テスト','damage':69,'enemy':'mame'})
        self.assertTrue(entries[0]['hasLog'])
        self.assertEqual(self.store.leaderboard('demo','hard')['entries'],[])
        self.assertEqual(self.store.leaderboard('gemini','easy')['entries'],[])
        restarted=rankings.Rankings(self.store.database,None,server.png_image)
        self.assertEqual(restarted.leaderboard('demo','easy')['entries'],entries)

    def test_incomplete_game_invalid_name_and_bad_token(self):
        for token in ['wrong',None,[],{}]:
            with self.assertRaises(rankings.RankingError):self.store.register({'token':token,'name':'x'})
        self.play(1)
        with self.assertRaises(rankings.RankingError):self.store.register({**self.session,'name':'x'})
        self.play(2);self.play(3)
        for name in ['', 'x'*21, '\nabc', '\u202ex', None]:
            with self.assertRaises(rankings.RankingError):self.store.register({**self.session,'name':name})

    def test_order_retry_and_history_cannot_be_forged(self):
        with self.assertRaises(rankings.RankingError):self.play(2)
        first=self.play(1,playerHistory=['forged'],cpuHistory=['forged'])
        self.assertEqual(self.play(1),first)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0]['playerHistory'],[])
        self.play(2)
        self.assertEqual(self.calls[1]['playerHistory'],['目が豆1'])
        self.assertEqual(self.calls[1]['cpuHistory'],['CPUの目が豆'])
        with self.assertRaises(rankings.RankingError):self.play(1,text='別の文')
        with self.assertRaises(rankings.RankingError):self.play(True)

    def test_failed_score_is_atomic_and_retryable(self):
        with patch.object(self.store,'judge',side_effect=ValueError('failed')):
            with self.assertRaises(ValueError):self.play(1)
        self.assertEqual(self.store.games[self.session['token']]['turns'],[])
        for damage in [31, -1, True, 1.5]:
            with patch.object(self.store,'judge',return_value={'player':{'damage':23,'reason':'ok'},'cpu':{'text':'cpu','score':{'damage':damage,'reason':'bad'}}}):
                with self.assertRaises(ValueError):self.play(1)
        self.play(1)
        self.assertEqual(len(self.store.games[self.session['token']]['turns']),1)

    def test_busy_duplicate_and_global_capacity(self):
        event=threading.Event();started=threading.Event();original=self.store.judge
        def judge(body,mode):
            started.set();event.wait(2);return original(body,mode)
        self.store.judge=judge
        thread=threading.Thread(target=lambda:self.play(1));thread.start();self.assertTrue(started.wait(1))
        try:
            with self.assertRaises(rankings.RankingError):self.play(1)
            with self.assertRaises(rankings.RankingError):self.store.register({**self.session,'name':'x'})
        finally:event.set();thread.join()
        self.store.workers.acquire();self.store.workers.acquire()
        try:
            with self.assertRaises(rankings.RankingError) as caught:self.play(2)
            self.assertEqual(caught.exception.status,429)
        finally:self.store.workers.release();self.store.workers.release()
        self.play(2)

    def test_ties_have_same_rank_and_demo_is_separate(self):
        self.finish();self.store.register({**self.session,'name':'A'})
        self.session=self.start();self.finish();self.store.register({**self.session,'name':'B'})
        self.assertEqual([e['rank'] for e in self.store.leaderboard('demo','easy')['entries']],[1,1])
        self.session=self.start('gemini');self.finish();self.store.register({**self.session,'name':'C'})
        self.assertEqual(len(self.store.leaderboard('demo','easy')['entries']),2)
        self.assertEqual(len(self.store.leaderboard('gemini','easy')['entries']),1)

    def test_higher_damage_ranks_first_and_save_failure_can_retry(self):
        self.finish()
        with patch.object(self.store, 'db', side_effect=sqlite3.OperationalError('locked')):
            with self.assertRaises(sqlite3.Error):self.store.register({**self.session,'name':'A'})
        self.store.register({**self.session,'name':'A'})
        self.session=self.start()
        self.store.judge=lambda body,mode:{'player':{'damage':30,'reason':'a'},'cpu':{'text':'cpu','score':{'damage':0,'reason':'b'}}}
        self.finish();self.store.register({**self.session,'name':'B'})
        self.assertEqual([(e['name'],e['damage'],e['rank']) for e in self.store.leaderboard('demo','easy')['entries']],[('B',90,1),('A',69,2)])

    def test_expiry_and_validation(self):
        with self.assertRaises(rankings.RankingError):self.store.leaderboard('demo','invalid')
        with self.assertRaises(rankings.RankingError):self.start(difficulty='invalid')
        with self.assertRaises(ValueError):self.store.start({'difficulty':'easy','enemy':'mame','playerImage':'bad','cpuImage':IMAGE},'demo')
        self.store.clock=lambda:1e20
        with self.assertRaises(rankings.RankingError):self.play(1)
        self.assertEqual(self.store.games,{})

    def test_demo_matches_browser_rules(self):
        self.assertEqual(rankings.demo_score('眉毛、海苔',[])['damage'],25)
        self.assertEqual(rankings.demo_score('眉毛ふとっ',[])['damage'],18)
        self.assertEqual(rankings.demo_score('バカ',[])['damage'],6)
        self.assertEqual(rankings.demo_score('眉毛 海苔',['眉毛、海苔'])['damage'],2)
        self.assertEqual(rankings.demo_score('!!!',[])['damage'],0)

    def test_public_log_is_authoritative_and_includes_scaled_cpu_hp(self):
        self.finish()
        self.store.register({**self.session,'name':'<b>name</b>','turns':[{'text':'forged'}]})
        entry=self.store.leaderboard('demo','easy')['entries'][0]
        log=self.store.detail(entry['id'])
        self.assertEqual(len(log['turns']),3)
        self.assertEqual(log['turns'][0]['player'],{'text':'目が豆1','damage':23,'reason':'a'})
        self.assertEqual(log['turns'][0]['cpu']['damage'],6)
        self.assertEqual(log['turns'][-1]['hp'],{'player':82,'cpu':31})
        self.assertNotIn(self.session['token'],str(log))
        self.assertNotIn('playerImage',str(log))
        self.assertNotIn('forged',str(log))
        restarted=rankings.Rankings(self.store.database,None,server.png_image)
        self.assertEqual(restarted.detail(entry['id']),log)

    def test_legacy_database_keeps_scores_without_inventing_logs(self):
        legacy=Path(self.temp.name)/'old.sqlite3'
        with sqlite3.connect(legacy) as db:
            db.execute('CREATE TABLE cpu_scores (game TEXT PRIMARY KEY, name TEXT, mode TEXT, difficulty TEXT, enemy TEXT, damage INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP)')
            db.execute('INSERT INTO cpu_scores(game,name,mode,difficulty,enemy,damage) VALUES(?,?,?,?,?,?)',('a'*32,'昔の記録','demo','easy','mame',50))
        old=rankings.Rankings(legacy,None,server.png_image)
        entries=old.leaderboard('demo','easy')['entries']
        self.assertFalse(entries[0]['hasLog'])
        self.assertFalse(entries[0]['hasFace'])
        with self.assertRaises(rankings.RankingError):old.face('a'*32)
        self.assertIsNone(old.detail('a'*32)['turns'])
        for game in ['invalid', 'b'*32, "' OR 1=1 --", None]:
            with self.assertRaises(rankings.RankingError) as error:old.detail(game)
            self.assertEqual(error.exception.status,404)

    def test_portrait_published_only_on_registration_from_actual_game(self):
        game_id=self.store.games[self.session['token']]['id']
        with self.assertRaises(rankings.RankingError):self.store.face(game_id)
        self.finish()
        with self.assertRaises(rankings.RankingError):self.store.face(game_id)
        self.store.register({**self.session,'name':'顔あり','portrait':'forged','playerImage':'forged'})
        entry=self.store.leaderboard('demo','easy')['entries'][0]
        self.assertTrue(entry['hasFace'])
        self.assertTrue(self.store.detail(game_id)['hasFace'])
        self.assertEqual(self.store.face(game_id),server.base64.b64decode(IMAGE.split(',')[1]))
        restarted=rankings.Rankings(self.store.database,None,server.png_image)
        self.assertEqual(restarted.face(game_id),self.store.face(game_id))
        self.store.register({**self.session,'name':'別名','portrait':'forged'})
        self.assertEqual(self.store.face(game_id),restarted.face(game_id))

    def test_cloud_uses_existing_cpu_gateway(self):
        with patch('server.run_cloud_round',return_value={'ok':True}) as mocked:
            self.assertEqual(server.run_ranked_round({'text':'x'},'gemini'),{'ok':True})
            mocked.assert_called_once_with({'text':'x'},'gemini')

if __name__=='__main__':unittest.main()
