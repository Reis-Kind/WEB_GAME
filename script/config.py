"""ゲームのLLM設定。変更後は server.py を再起動してください。"""

# 使用AIはここで管理します。プレイヤー画面にはAI選択を表示しません。
# "gemini": Gemini無料枠を利用 / "gpt": OpenAI API / "local": Ollama / "demo": 接続不要
JUDGE_MODE = "gemini"

# ollama list に表示されるモデル名。取得済みモデルを指定してください。
OLLAMA_MODEL = "qwen3-vl:4b-instruct"

# Pythonサーバーから接続するOllama。ブラウザには公開しません。
OLLAMA_URL = "http://127.0.0.1:11434"

# CPUの口調。絵のパーツを大げさにイジる毒舌スタイル。
ROAST_STYLE = "容赦ない毒舌。顔のパーツの形・大きさ・配置を、変な物や状況にたとえて勢いよくディスる。"

# 画像入力・構造化出力に対応するモデル。APIキーは環境変数または.envのOPENAI_API_KEY。
OPENAI_MODEL = "gpt-5.4-mini"

# 無料枠のある画像対応モデル。AI Studioで無料プランのプロジェクトを使用。
# キーは環境変数GEMINI_API_KEY。無料枠・課金状態の確認はAI Studioで行ってください。
GEMINI_MODEL = "gemini-3.1-flash-lite"
