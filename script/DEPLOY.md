# 無料の固定URLで公開する（Render + Turso）

2026-10-29に公式ドキュメントを確認した構成です。ここまでの変更で公開の準備は完了していますが、あなたのRender/Tursoへの登録・本番公開はまだ行っていません。

## 調査結果と選定

| 処理 | 現在の実装 | 公開時の置き場所 |
| --- | --- | --- |
| 画面・お絵描き・3D・音・演出 | HTML/CSS/JavaScript、ブラウザ内 | Renderから配信 |
| 採点・CPUの発言 | PythonのHTTP APIからGemini/GPTに接続 | RenderのPythonプロセス |
| ランキング・顔画像・対戦ログ | SQLiteの3テーブル | Tursoの永続DB |
| 対戦中の履歴・特徴メモ・トークン | Pythonメモリ（最大256対戦、無操作30分） | Renderの単一プロセスのメモリ |
| WebSocket・オンライン対戦 | 使用なし・未実装 | 不要 |

GitHub Pages等の静的ホスティングだけでは、現在のAI判定と共有ランキングを維持できません。RenderならPythonの構成をそのまま使えます。ただし無料Renderのローカルファイルは休止・再起動・更新で消えるので、ランキングだけTursoへ移します。標準ライブラリのHTTPS通信で接続し、追加パッケージは不要です。

- **同じWi-Fiは不要**。RenderのHTTPS URLに4G/5Gからアクセスできます。
- **ngrokの「Visit Site」確認操作は不要**。ただし休止からの復帰中にはRenderの読み込み画面が表示されます。
- URLはRenderが割り当てる `https://サービス名.onrender.com`。同じサービスを更新・再起動する限り継続利用できます。名前の空き状況で実際の文字列は変わります。削除して作り直さないでください。
- ホストはクラウドなのでPCを止めても使えます。ngrok・share.pyを起動する必要はありません。
- 独自ドメイン、有料プラン、有料ディスク、Render Postgresは作成しません。

[Render Web Services](https://render.com/docs/web-services)、[無料枠の制限](https://render.com/docs/free)、[Turso料金](https://turso.tech/pricing)、[Turso HTTP仕様](https://docs.turso.tech/sdk/http/reference)。

## 1. Tursoに無料DBを用意

[Turso](https://turso.tech/)に登録し、**Free**プランでデータベースを1個作ります。管理画面でデータベースURLと読み書き可能なデータベース用トークンを取得します。組織管理用のAPIトークンとは別です。

CLIを使う場合は[公式の導入手順](https://docs.turso.tech/cli/installation)に従い、次を実行します。

```bash
turso auth login
turso db create kao-battle
turso db show kao-battle --url
turso db tokens create kao-battle
```

最後のコマンドは秘密のトークンを表示します。チャット・GitHub・スクリーンショットに載せず、次のRenderのEnvironmentに設定してください。期限付きトークンを使う場合は、期限前に再発行してRenderの値を更新します。

新規DBのテーブルは最初のランキング操作時に自動作成されます。既存のローカルランキングも残したい場合は、空のDBを作る代わりに、このページ後半の移行手順を先に実行してください。

## 2. コードをGitHubへ反映

このリポジトリは `WEB_GAME/` がGitのルートで、その中の `script/` にアプリがあります。今回の変更と既存のゲーム本体をコミットし、Renderに接続するGitHubブランチへpushします。非公開リポジトリでも構いません。

`.env` と `.data/` はGit対象外です。GeminiのキーもTursoのトークンもコミットしません。過去に公開したキーは失効・再発行し、新しいキーを使ってください。

```bash
# WEB_GAMEディレクトリで実行
cd ..
git status --short
git add script
git diff --cached --stat
git commit -m "Prepare Render hosting with persistent Turso rankings"
git push
```

ほかの作業変更も含まれる場合は、コミット前に対象を確認してください。

## 3. Renderへ公開（あなたの操作）

[Render](https://dashboard.render.com/)に登録し、GitHubを連携します。まず分かりやすい **New → Web Service** の方法で作成できます。

| 項目 | 設定値 |
| --- | --- |
| Repository / Branch | このゲームをpushしたリポジトリとブランチ |
| Name | 希望のサービス名（例 `kao-battle`、空き状況による） |
| Language | Python 3 |
| Root Directory | `script` |
| Build Command | `python -m compileall -q .` |
| Start Command | `python -u server.py --cloud` |
| Instance Type | **Free** |
| Health Check Path | `/healthz`（Advanced等で設定） |

**Environment** に次を追加します。実際の値はこの表やファイルへ書かず、Renderの入力欄にだけ入力してください。

| 変数 | 値 |
| --- | --- |
| `PYTHON_VERSION` | `3.12.8` |
| `JUDGE_MODE` | `gemini` |
| `GEMINI_API_KEY` | あなたの新しいGemini APIキー |
| `TURSO_DATABASE_URL` | 取得した `libsql://...` または `https://...` のDB URL |
| `TURSO_AUTH_TOKEN` | データベース用の読み書きトークン |
| `GEMINI_MODEL` | 任意。省略時は `config.py` のモデル |

API接続なしで先に公開を試すなら `JUDGE_MODE=demo` にし、`GEMINI_API_KEY` は不要です。Tursoの2変数はデモでも必要です。クラウド起動では未設定のまま消えるSQLiteに保存することを防ぐため、DB設定がなければ起動を止めます。`PORT` はRenderの値を自動で使い、`0.0.0.0`で待ち受けます。公開HTTPS経由の同一オリジンAPIリクエストに対応済みです。

**Deploy Web Service** を押し、Liveになるまで待ちます。表示された `https://…onrender.com` を保存してください。そのURLが今後の固定URLです。公開後の確認が済むまでは、現在のngrok側を消す必要はありません。

設定ファイルから作る場合は、同梱の `script/render.yaml` を使って **New → Blueprint** でも作成できます。Blueprint Pathを **`script/render.yaml`** にし、未設定の3つの秘密情報を入力してください。`rootDir: script` はリポジトリルート基準です。もし将来scriptの中身だけを独立したリポジトリにする場合はRoot Directoryを空にし、YAMLのrootDirも変更します。

## 4. 本番での確認

1. 公開URLの `/healthz` に `{"ok":true}` が出ることを確認します。これはプロセスの生存確認であり、DBやGeminiの接続確認ではありません。
2. スマホのWi-Fiを切り、4G/5Gでタイトルを開きます。
3. 顔を描いて3ラウンド対戦し、結果の採点理由を開きます。
4. 顔・記録・ログの公開登録を行い、ランキングとログ・顔を確認します。
5. Renderで同じサービスを再デプロイし、同じURLで登録した記録が残ることを確認します。
6. PCを止めてスマホからアクセスします。初回に起動待ちが出る場合は約1分待ちます。

接続エラーはRenderのLogsと各サービスの利用量を確認します。`GEMINI_API_KEYが未設定`ならRenderのEnvironment、モデル利用不可ならモデル名とAI Studioの利用可能モデル、ランキング保存失敗ならTursoのURL・トークン・期限・無料枠を確認してください。

## 無料枠と維持できない部分

- **Render**：15分アクセスがなければ休止し、復帰に約1分かかります。常時即応ではありません。無料稼働時間はワークスペースで月750時間共有。帯域・ビルド時間にも上限があり、無料枠超過時の停止や支払方法に応じた課金の扱いは公式ページとダッシュボードで確認してください。有料プランへの切り替えや有料リソース追加は行いません。
- **Turso Free**：確認時点でストレージ5GB、月5億行読み取り・1,000万行書き込み。顔をbase64で保存するため、利用人数に応じて容量を消費します。将来も同じ無料枠が続く保証はありません。上限・利用量はTursoの画面で確認してください。
- **Gemini**：公開サーバーが無料でもAIが無制限になるわけではありません。無料枠プロジェクトと対象モデルを使い、AI Studioで現在のRPM/TPM/RPDを確認してください。上限超過は判定エラーになります。GPTに切り替えると別途API料金がかかるため、この構成では変更しません。[公式レート制限](https://ai.google.dev/gemini-api/docs/rate-limits)
- **対戦中の状態**：メモリ管理を維持しています。休止・再起動・デプロイで途中の対戦や未登録の結果は失われ、やり直しが必要です。登録済みのランキング・顔・ログはTursoに残ります。更新はなるべく人が遊んでいない時間に行ってください。
- **同時アクセス**：ランキング経由の採点は現在同時2件に制限しています。大量アクセス対応・常時稼働保証は含みません。単一プロセスを前提にしており、複数台へのスケールアウトには対戦状態のDB化も必要です。
- **Ollama**：PC内のOllamaはクラウドから接続できず、PC停止でも遊べる条件を満たさないため、クラウド起動でlocalモードを拒否します。Geminiまたはデモで利用してください。
- **公開内容**：従来どおり、登録した名前・顔・発言・採点理由は公開されます。APIキー・DBトークン・セッショントークンはランキングに含みません。アカウント制やオンライン対戦は追加していません。

## 既存ランキングも移す場合（任意・初回だけ）

ローカルDBは削除も自動移行もしていません。移行時はngrok公開とローカルサーバーを一旦停止し、次のバックアップを作ります。`script/`内で実行します。対象DBがない場合は実行不要です。

```bash
python3 - <<'PY'
import sqlite3
from pathlib import Path
source = Path('.data/rankings.sqlite3').resolve()
if not source.exists():
    raise SystemExit('既存DBがありません。新規DBで開始してください。')
backup = Path('.data/rankings-migration.sqlite3')
if backup.exists():
    raise SystemExit('移行用ファイルが既にあります。上書きせず確認してください。')
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
    with sqlite3.connect(backup) as dst:
        src.backup(dst)
print('移行用バックアップを作成しました。元DBは変更していません。')
PY
# 新規作成と同時にインポート。既に使っているDBは上書きしない。
turso db create kao-battle --from-file .data/rankings-migration.sqlite3
```

このDBのURLとトークンをRenderに設定します。元DBとバックアップはGitへ追加しません。これは登録済み記録の移行で、対戦中のセッションは移せません。詳細は[Tursoの既存SQLite取込](https://docs.turso.tech/cli/db/create)を参照してください。

## 今後の更新

コードを修正→ローカルで動作確認→GitHubへcommit/push。RenderのAuto-Deployが有効なら、接続ブランチへのpushで更新されます。無効の場合は **Manual Deploy → Deploy latest commit**。同じサービスを更新する限りURLはそのままです。DBを作り直す必要はありません。

キー・モデルの変更はRenderのEnvironmentを更新して再デプロイします。キーをコードやGitへ書く必要はありません。ローカル開発時は従来の `.env` を使えます。ローカルでTurso変数を設定しなければ従来のSQLiteを使うので、本番ランキングを触らず開発できます。

検証コマンド（外部API不要）：

```bash
python3 -m unittest discover -s tests -q
PYTHONPATH=. python3 tests/cloud_smoke_check.py
```

ローカル80テスト、HTTPS転送を想定したHTTP経由のデモ3ラウンド、登録・顔・ログ、ストア再作成後の永続化を確認済みです。Turso API互換のローカルテストサーバーを使用しています。実際のRender/Tursoアカウント上でのデプロイ、実Turso接続、4G/5Gからの疎通、ホスティング地域からのGemini接続は、上記の本番確認がまだ必要です。
