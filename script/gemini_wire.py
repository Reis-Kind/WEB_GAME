"""Compact Gemini round outputs, expanded before existing scoring validation."""
FIELDS=('feature','bite','creativity','novelty')


def compact_round(schema, instructions):
    if not isinstance(schema.get('properties'),dict) or not {'player','cpu'} <= schema['properties'].keys():
        return schema, instructions, None
    scores={'type':'array','items':{'type':'integer','minimum':0,'maximum':10},'minItems':4,'maxItems':4}
    properties={}
    if 'faces' in schema['properties']:
        properties['faces']=schema['properties']['faces']
    properties.update({'p':{**scores,'description':'人間の発言をCPUの顔（画像1）に照合した点数'},'pe':{'type':'string'},'pr':{'type':'string'},'t':{'type':'string','description':'CPUから人間プレイヤーの顔（画像2）への攻撃文。CPU自身を攻撃しない'},
                       'c':{**scores,'description':'tを人間の顔（画像2）に照合した点数'},'ce':{'type':'string','description':'人間プレイヤーの顔にある、tが狙った特徴。CPUの特徴ではない'},'cr':{'type':'string'}})
    wire={'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
    instructions += (' 出力JSONは指定の短縮形式だけを使う。player/cpuの長いキーは出力しない。'
                     'p=playerの点数、c=cpu.scoreの点数。両配列は必ず[feature(0〜10),bite(0〜10),creativity(0〜5),novelty(0〜5)]の4整数。'
                     'pe/ce=それぞれのevidence（12文字以内）、pr/cr=それぞれのreason（16文字以内）、t=cpu.text（25文字以内）。'
                     't,c,ce,crはすべて人間プレイヤーの顔（画像2）が対象。p,pe,prだけCPUの顔（画像1）が対象。採点基準・履歴の扱いは変えない。facesが要求された場合は先に従来の形式で出力。')
    return wire, instructions, 'faces' in properties


def expand_round(value, with_faces):
    def score(key):
        numbers=value.get(key)
        if not isinstance(numbers,list) or len(numbers)!=4 or any(type(n) is not int or not 0<=n<=limit for n,limit in zip(numbers,(10,10,5,5))):
            raise ValueError('Invalid compact scores')
        evidence,reason=value.get(key+'e'),value.get(key+'r')
        if not isinstance(evidence,str) or not isinstance(reason,str) or not reason.strip():
            raise ValueError('Invalid compact reasons')
        return {**dict(zip(FIELDS,numbers)),'evidence':evidence,'reason':reason}
    if not isinstance(value.get('t'),str) or not 1<=len(value['t'].strip())<=120:
        raise ValueError('Invalid compact CPU line')
    result={'player':score('p'),'cpu':{'text':value['t'],'score':score('c')}}
    if with_faces:
        if not isinstance(value.get('faces'),dict):raise ValueError('Missing faces')
        result['faces']=value['faces']
    return result
