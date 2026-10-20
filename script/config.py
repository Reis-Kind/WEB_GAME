"""ゲームのLLM設定。変更後は server.py を再起動してください。"""

# "local": 起動時にOllamaへ自動接続 / "demo": 接続不要のデモ判定
JUDGE_MODE = "local"

# ollama list に表示されるモデル名。取得済みモデルを指定してください。
OLLAMA_MODEL = "qwen3-vl:4b-instruct"

# Pythonサーバーから接続するOllama。ブラウザには公開しません。
OLLAMA_URL = "http://127.0.0.1:11434"
