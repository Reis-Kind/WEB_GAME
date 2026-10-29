import io
import json
import os
import tempfile
from pathlib import Path
import rankings
import unittest
from unittest.mock import patch
import gemini_gateway
from gemini_wire import compact_round,expand_round
import server

SCORE={'feature':8,'bite':4,'creativity':1,'novelty':5,'evidence':'太い眉','reason':'特徴を捉えた'}
EXPANDED={'player':SCORE,'cpu':{'text':'目、豆じゃん','score':SCORE}}
COMPACT={'p':[8,4,1,5],'pe':'太い眉','pr':'特徴を捉えた','t':'目、豆じゃん','c':[8,4,1,5],'ce':'太い眉','cr':'特徴を捉えた'}
SCHEMA={'type':'object','properties':{'player':server.MODEL_SCHEMA,'cpu':{'type':'object'}},'required':['player','cpu']}

class WireTests(unittest.TestCase):
    def test_compact_round_retains_all_scores_evidence_and_reasons(self):
        schema,instructions,faces=compact_round(SCHEMA,'test')
        self.assertFalse(faces)
        self.assertEqual(schema['properties']['p']['minItems'],4)
        self.assertEqual(expand_round(COMPACT,False),EXPANDED)
        self.assertIn('creativity(0〜5)',instructions)
        raw=len(json.dumps(EXPANDED,ensure_ascii=False,separators=(',',':')).encode())
        compact=len(json.dumps(COMPACT,ensure_ascii=False,separators=(',',':')).encode())
        self.assertLess(compact,raw*.75)

    def test_faces_still_use_same_schema_and_payload(self):
        face_schema={'type':'object'}
        wire,_,faces=compact_round({**SCHEMA,'properties':{**SCHEMA['properties'],'faces':face_schema}},'test')
        self.assertTrue(faces)
        self.assertEqual(wire['properties']['faces'],face_schema)
        with self.assertRaises(ValueError):expand_round(COMPACT,True)
        self.assertEqual(expand_round({**COMPACT,'faces':{'player':{},'cpu':{}}},True)['faces'],{'player':{},'cpu':{}})

    def test_invalid_scores_and_reasons_rejected(self):
        for bad in [[8,4,6,5],[8,4,1,6],[True,4,1,5],[-1,4,1,5],[11,4,1,5],[8,4,1],None]:
            with self.assertRaises(ValueError):expand_round({**COMPACT,'p':bad},False)
        for changes in [{'pr':''},{'pe':None},{'t':''},{'t':'a'*121}]:
            with self.assertRaises(ValueError):expand_round({**COMPACT,**changes},False)

    def test_generic_schema_is_unchanged(self):
        wire,instructions,compact=compact_round(server.MODEL_SCHEMA,'test')
        self.assertIs(wire,server.MODEL_SCHEMA)
        self.assertEqual(instructions,'test')
        self.assertIsNone(compact)

    def response(self,value):
        return io.BytesIO(json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(value)}]}}],
                                     'usageMetadata':{'candidatesTokenCount':123}}).encode())

    def test_gateway_translates_and_logs_only_metadata(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'mock-key'}),patch('gemini_gateway.urlopen',return_value=self.response(COMPACT)) as call,self.assertLogs('kao.ai',level='INFO') as logs:
            result=gemini_gateway.generate('gemini-3.1-flash-lite','test',[],SCHEMA)
        self.assertEqual(result,EXPANDED)
        payload=json.loads(call.call_args.args[0].data)
        self.assertIn('p',payload['generationConfig']['responseJsonSchema']['properties'])
        self.assertNotIn('player',payload['generationConfig']['responseJsonSchema']['properties'])
        self.assertIn('output_tokens=123',logs.output[0])
        self.assertNotIn('mock-key',logs.output[0])
        self.assertNotIn('太い眉',logs.output[0])

    def test_full_ranked_game_expands_compact_outputs_and_reuses_faces(self):
        fields=('outline','eyes','eyebrows','nose','mouth','hair','accessories','layout')
        faces={'player':dict.fromkeys(fields,'小さい丸い目'),'cpu':dict.fromkeys(fields,'太い眉')}
        sent=[]
        def api(request,timeout):
            payload=json.loads(request.data)
            sent.append(sum('inlineData' in part for part in payload['contents'][0]['parts']))
            value=dict(COMPACT)
            if 'faces' in payload['generationConfig']['responseJsonSchema']['properties']:value['faces']=faces
            return self.response(value)
        with tempfile.TemporaryDirectory() as directory:
            store=rankings.Rankings(Path(directory)/'scores.db',server.run_ranked_round,server.png_image)
            image='data:image/png;base64,iVBORw0KGgo='
            session=store.start({'difficulty':'easy','enemy':'mame','playerImage':image,'cpuImage':image},'gemini')
            with patch.dict(os.environ,{'GEMINI_API_KEY':'mock-key'}),patch('gemini_gateway.urlopen',side_effect=api),self.assertLogs('kao.ai',level='INFO'):
                for number in range(1,4):
                    result=store.play({**session,'round':number,'text':'眉毛ふとっ'+str(number)})
                    self.assertIn('player',result)
                    self.assertNotIn('p',result)
            self.assertEqual(sent,[2,0,0])
            self.assertEqual(store.register({**session,'name':'test'})['damage'],72)

    def test_malformed_gateway_result_fails_without_fake_score(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'mock-key'}),patch('gemini_gateway.urlopen',return_value=self.response({**COMPACT,'c':[30]})):
            with self.assertRaises(gemini_gateway.GeminiError):gemini_gateway.generate('gemini-3.1-flash-lite','test',[],SCHEMA)

if __name__=='__main__':unittest.main()
