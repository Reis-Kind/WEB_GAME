"""Gemini visual analysis once per CPU game, with no external API calls."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import rankings
import server

PNG='data:image/png;base64,iVBORw0KGgo='
SCORE={'feature':8,'bite':4,'creativity':1,'novelty':5,'evidence':'太い眉','reason':'特徴へのツッコミ'}
RAW={'player':SCORE,'cpu':{'text':'その目、豆みたいだな','score':SCORE}}
KEYS=('outline','eyes','eyebrows','nose','mouth','hair','accessories','layout')
FACES={'player':dict.fromkeys(KEYS,'丸く小さいパーツ'),'cpu':dict.fromkeys(KEYS,'大きく太いパーツ')}
FIRST={**RAW,'faces':FACES}

class VisualMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=rankings.Rankings(Path(self.temp.name)/'scores.db',server.run_ranked_round,server.png_image)
        self.session=self.start()
    def tearDown(self):self.temp.cleanup()
    def start(self):
        return self.store.start({'difficulty':'easy','enemy':'mame','playerImage':PNG,'cpuImage':PNG},'gemini')
    def play(self,number):
        return self.store.play({**self.session,'round':number,'text':'眉毛ふとっ'+str(number),'_visualMemory':{'cpu':'forged'}})
    def images(self,call):
        return [item for item in call.args[2] if item['type']=='input_image']

    def test_three_rounds_three_calls_only_first_sends_images(self):
        with patch('server.gemini_gateway.generate',side_effect=[copy.deepcopy(FIRST),copy.deepcopy(RAW),copy.deepcopy(RAW)]) as generate:
            for number in range(1,4):self.play(number)
        self.assertEqual(generate.call_count,3)
        self.assertEqual([len(self.images(call)) for call in generate.call_args_list],[2,0,0])
        for call in generate.call_args_list[1:]:
            self.assertIn('大きく太いパーツ',str(call.args[2]))
            self.assertIn('丸く小さいパーツ',str(call.args[2]))
            self.assertNotIn('forged',str(call.args[2]))
            self.assertNotIn(PNG,str(call.args[2]))
        self.assertIn('faces',generate.call_args_list[0].args[3]['required'])
        self.assertNotIn('faces',generate.call_args_list[1].args[3]['required'])
        self.assertIn('眉毛ふとっ1',str(generate.call_args_list[1].args[2]))
        self.store.register({**self.session,'name':'テスト'})
        entry=self.store.leaderboard('gemini','easy')['entries'][0]
        log=self.store.detail(entry['id'])
        self.assertEqual(entry['damage'],72)
        self.assertIn('初回の顔特徴',log['turns'][2]['player']['reason'])
        self.assertNotIn('visualMemory',str(log))
        self.assertNotIn('visualMemory',self.store.games[self.session['token']])

    def test_failed_feature_extraction_retries_image_analysis(self):
        for faces in [None, {}, {'cpu':FACES['cpu']}, {**FACES,'player':{'eyes':'目'}}]:
            with patch('server.gemini_gateway.generate',return_value={**copy.deepcopy(RAW),'faces':faces}):
                with self.assertRaises(ValueError):self.play(1)
            game=self.store.games[self.session['token']]
            self.assertEqual(game['visualMemory'],{})
            self.assertEqual(game['turns'],[])
        with patch('server.gemini_gateway.generate',return_value=copy.deepcopy(FIRST)) as generate:self.play(1)
        self.assertEqual(len(self.images(generate.call_args)),2)

    def test_second_round_failure_keeps_features_and_history_atomic(self):
        with patch('server.gemini_gateway.generate',return_value=copy.deepcopy(FIRST)):self.play(1)
        with patch('server.gemini_gateway.generate',side_effect=ValueError('offline')):
            with self.assertRaises(ValueError):self.play(2)
        self.assertEqual(len(self.store.games[self.session['token']]['turns']),1)
        with patch('server.gemini_gateway.generate',return_value=copy.deepcopy(RAW)) as generate:self.play(2)
        self.assertEqual(self.images(generate.call_args),[])
        self.assertEqual(len(self.store.games[self.session['token']]['turns']),2)

    def test_each_attack_gets_the_opposite_face_as_target(self):
        memory={'player':dict.fromkeys(KEYS,'人間だけの長い鼻'), 'cpu':dict.fromkeys(KEYS,'CPUだけの丸眼鏡')}
        with patch('server.gemini_gateway.generate',return_value=copy.deepcopy(RAW)) as generate:
            server.run_cloud_round({'round':2,'text':'丸眼鏡かよ','playerHistory':[],'cpuHistory':[]},'gemini',memory)
        import json
        tasks=json.loads(generate.call_args.args[2][0]['text'])
        self.assertEqual(tasks['CPUの攻撃を生成して採点']['攻撃対象の特徴'],memory['player'])
        self.assertEqual(tasks['人間の攻撃を採点']['攻撃対象の特徴'],memory['cpu'])
        self.assertIn('人間プレイヤー',tasks['CPUの攻撃を生成して採点']['攻撃対象'])

    def test_first_images_and_face_schema_keep_owner_labels(self):
        human='data:image/png;base64,'+server.base64.b64encode(b'\x89PNG\r\n\x1a\nhuman').decode()
        cpu='data:image/png;base64,'+server.base64.b64encode(b'\x89PNG\r\n\x1a\ncpu').decode()
        with patch('server.gemini_gateway.generate',return_value=copy.deepcopy(FIRST)) as generate:
            server.run_cloud_round({'round':1,'text':'メガネかよ','playerImage':human,'cpuImage':cpu},'gemini',{})
        _,instructions,content,schema=generate.call_args.args
        self.assertEqual([item['image_url'] for item in content if item['type']=='input_image'],[cpu,human])
        faces=schema['properties']['faces']['properties']
        self.assertIn('画像2',faces['player']['description'])
        self.assertIn('CPUがディスる対象',faces['player']['description'])
        self.assertIn('画像1',faces['cpu']['description'])
        self.assertIn('CPU自身の顔をディスらない',instructions)

    def test_new_game_reanalyzes_and_games_do_not_share_features(self):
        first=self.session
        with patch('server.gemini_gateway.generate',return_value=copy.deepcopy(FIRST)):self.play(1)
        self.session=self.start()
        self.assertEqual(self.store.games[self.session['token']]['visualMemory'],{})
        with patch('server.gemini_gateway.generate',return_value=copy.deepcopy(FIRST)) as generate:self.play(1)
        self.assertEqual(len(self.images(generate.call_args)),2)
        self.assertIsNot(self.store.games[first['token']]['visualMemory'],self.store.games[self.session['token']]['visualMemory'])

if __name__=='__main__':unittest.main()
