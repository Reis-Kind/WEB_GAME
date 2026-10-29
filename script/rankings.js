import {ENEMIES} from './enemies.js?v=contour-2';
const $=id=>document.getElementById(id);
async function request(path,body,timeout=10000){
  const response=await fetch('/api/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,cache:'no-store',signal:AbortSignal.timeout(timeout)});
  const data=await response.json();if(!response.ok)throw Error(data.error||'ランキングに接続できません。');return data;
}
function portrait(entry,name){
  const frame=document.createElement('span');frame.className='ranking-portrait';
  const fallback=document.createElement('span');fallback.textContent='◡';fallback.setAttribute('aria-label','顔画像なし');frame.append(fallback);
  if(entry.hasFace){
    const image=new Image();image.alt=name+'が描いた顔';image.loading='lazy';image.decoding='async';
    image.src='/api/ranking/face?id='+encodeURIComponent(entry.id);
    image.onload=()=>{fallback.hidden=true;};image.onerror=()=>{image.remove();fallback.hidden=false;};frame.append(image);
  }
  return frame;
}
export function setupRankings({showScreen}){
  let token=null,unavailable='',difficulty='easy',saving=false,loading=0;
  async function load(){
    const version=++loading;$('ranking-list').replaceChildren();$('ranking-status').textContent='読み込み中…';
    try{
      const data=await request('leaderboard?difficulty='+$('ranking-difficulty').value);
      if(version!==loading)return;
      $('ranking-status').textContent=(data.mode==='demo'?'デモ判定':data.mode==='gemini'?'Gemini判定':data.mode==='gpt'?'GPT判定':'ローカルAI判定')+' · 合計ダメージ上位20件'+(data.entries.length?'':'（まだ記録がありません）');
      for(const entry of data.entries){
        const row=document.createElement('li'),button=document.createElement('button'),rank=document.createElement('b'),name=document.createElement('strong'),score=document.createElement('span');
        rank.textContent=String(entry.rank);name.textContent=entry.name;score.textContent=entry.damage+' DMG';const hint=document.createElement('small');hint.textContent=entry.hasLog?'対戦ログを見る →':'ログなし';
        button.className='ranking-record';button.type='button';button.append(rank,portrait(entry,entry.name),name,score,hint);
        button.onclick=()=>showLog(entry.id);row.append(button);$('ranking-list').append(row);
      }
    }catch(error){if(version===loading)$('ranking-status').textContent=error.message;}
  }
  let logLoading=0;
  async function showLog(id){
    const version=++logLoading;showScreen('ranking-log');
    $('ranking-log-faces').replaceChildren();$('ranking-log-title').textContent='対戦ログ';$('ranking-log-meta').textContent='';$('ranking-log-turns').replaceChildren();$('ranking-log-status').textContent='読み込み中…';
    try{
      const data=await request('ranking/log?id='+encodeURIComponent(id));if(version!==logLoading)return;
      const enemy=ENEMIES.find(enemy=>enemy.id===data.enemy)?.name||'CPU';
      $('ranking-log-title').textContent=data.name+' の対戦';
      $('ranking-log-faces').append(portrait(data,data.name));
      const opponent=document.createElement('img');opponent.className='ranking-enemy';opponent.alt=enemy+'の顔';
      const opponentImage=ENEMIES.find(item=>item.id===data.enemy)?.image;if(opponentImage){opponent.src=opponentImage;$('ranking-log-faces').append(opponent);}
      const mode={demo:'デモ判定（画像未解析）',gemini:'Gemini判定',gpt:'GPT判定',local:'ローカルAI判定'}[data.mode]||'AI判定';
      $('ranking-log-meta').textContent=`${enemy}戦 · 合計 ${data.damage} ダメージ · ${{easy:'やさしい',normal:'ふつう',hard:'ガチ'}[data.difficulty]} · ${mode}`;
      $('ranking-log-status').textContent=data.turns?'':'この記録にはログが保存されていません。';
      for(const turn of data.turns||[]){
        const row=document.createElement('li'),heading=document.createElement('h3');heading.textContent='ROUND '+turn.round;row.append(heading);
        for(const actor of ['player','cpu']){
          const result=turn[actor],attack=document.createElement('article'),label=document.createElement('strong'),quote=document.createElement('blockquote'),reason=document.createElement('p');
          label.textContent=(actor==='player'?data.name:enemy)+' · '+result.damage+' ダメージ';
          quote.textContent=result.text;reason.textContent=result.reason;
          attack.className='record-attack '+actor;attack.append(label,quote,reason);
          if(actor==='cpu'&&result.rawDamage!==result.damage){const note=document.createElement('small');note.textContent=`難易度補正：${result.rawDamage} → ${result.damage} ダメージ`;attack.append(note);}
          row.append(attack);
        }
        const hp=document.createElement('p');hp.className='record-hp';hp.textContent=`残りHP：${data.name} ${turn.hp.player} ／ ${enemy} ${turn.hp.cpu}`;row.append(hp);$('ranking-log-turns').append(row);
      }
    }catch(error){if(version===logLoading)$('ranking-log-status').textContent=error.message;}
  }
  $('ranking-log-back').onclick=()=>{logLoading++;showScreen('ranking');};
  function open(){showScreen('ranking');$('ranking-difficulty').value=difficulty;load();}
  $('open-ranking').onclick=open;$('result-ranking').onclick=open;$('ranking-difficulty').onchange=load;
  $('ranking-back').onclick=()=>showScreen('title');
  $('ranking-form').onsubmit=async event=>{
    event.preventDefault();if(saving||!token)return;saving=true;$('save-ranking').disabled=true;
    $('ranking-feedback').textContent='登録中…';
    try{
      const result=await request('ranking/register',{token,name:$('ranking-name').value});
      $('ranking-feedback').textContent=result.damage+'ダメージで登録しました！';$('ranking-form').hidden=true;
      try{localStorage.setItem('kao-ranking-name',$('ranking-name').value);}catch{}
    }catch(error){$('ranking-feedback').textContent=error.message;}
    finally{saving=false;$('save-ranking').disabled=false;}
  };
  try{$('ranking-name').value=localStorage.getItem('kao-ranking-name')||'';}catch{}
  return {
    async begin(judge,input,expectedMode){
      token=null;unavailable='';difficulty=input.difficulty;
      $('ranking-form').hidden=true;$('ranking-feedback').textContent='';$('total-damage').textContent='';
      try{
        const session=await request('ranking/start',input);
        if(session.mode!==expectedMode)throw Error('採点設定が更新されています。再読み込みしてください。');
        token=session.token;
        // Battle still owns HP, difficulty scaling, and cut-in timing. The server
        // owns score histories and the sum used for ranking registration.
        return {...judge,playRound:({text,round})=>request('ranking/round',{token:session.token,text,round},modeTimeout(session.mode))};
      }catch(error){unavailable=error.message;return judge;}
    },
    finish(total){
      $('total-damage').textContent='合計 '+total+' ダメージ';
      $('ranking-form').hidden=!token;
      $('ranking-feedback').textContent=token?'登録すると、名前・描いた顔・双方の攻撃文・採点理由が公開されます。':'この対戦はランキング対象外です。'+unavailable;
    }
  };
}
function modeTimeout(mode){return mode==='local'?400000:75000;}
