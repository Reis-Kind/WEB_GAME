"""Configure a dedicated ngrok identity without changing the face game."""
import getpass
import sys
from pathlib import Path
from share_settings import ROOT, ensure_separate

sys.path.insert(0, str(ROOT.parent))
from setup_key import save_settings


def main():
    print('クッション・アリーナ専用のngrok設定です。顔バトルの設定は変更しません。')
    print('https://dashboard.ngrok.com/domains で使用するドメインを確認してください。')
    print('既存ドメインを使う場合は、顔バトル側のトンネルを停止してから起動します。')
    try:
        url = ensure_separate(input('クッション専用のngrokドメイン: '))
        token = getpass.getpass('そのドメインに対応するAuthtoken（入力は非表示）: ').strip()
        if not token:
            print('保存せず終了しました。')
            return
        save_settings(ROOT / '.env', {'NGROK_URL': url, 'NGROK_AUTHTOKEN': token, 'SHARE_PROVIDER': 'ngrok'})
    except (ValueError, OSError) as exc:
        print(f'設定できませんでした: {exc}')
        raise SystemExit(1)
    except (EOFError, KeyboardInterrupt):
        print('\n保存せず終了しました。')
        return
    print('専用の .env に保存しました。python3 cushion-battle/share.py で起動できます（scriptフォルダから）。')


if __name__ == '__main__':
    main()
