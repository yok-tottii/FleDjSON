"""
main.py
FleDjSONのエントリーポイント

Fletアプリケーションのエントリーポイントとして、
FleDjSONAppクラスを初期化して実行する薄いラッパーです。
"""
import flet as ft
import sys
import platform
import os

# アプリケーションパスの解決
if getattr(sys, 'frozen', False):
    # PyInstallerまたはFletビルドで実行されている場合
    if hasattr(sys, '_MEIPASS'):
        # PyInstallerの場合 - 作業ディレクトリを変更
        application_path = os.path.dirname(sys.executable)
        os.chdir(application_path)
    else:
        # Fletビルドの場合 - 作業ディレクトリは変更しない
        # Fletビルドは正しい作業ディレクトリで起動されるため
        pass
else:
    # 通常のPythonスクリプトとして実行されている場合
    application_path = os.path.dirname(os.path.abspath(__file__))
    # 開発環境では作業ディレクトリを変更しない

# Python環境チェック
if sys.version_info < (3, 12):
    print("\n[WARNING] このアプリケーションはPython 3.12以上が必要です")
    print("[ERROR] アプリケーションの起動に失敗しました")
    print("\n[INFO] 修正するには、以下のコマンドを実行してください:")
    print("1. pyenv global 3.12.3")
    print("2. poetry env use python3.12.3")
    print("3. poetry install")
    print("4. poetry run python src/main.py")
    sys.exit(1)

# FleDjSONAppをインポート
from app import FleDjSONApp


def main(page: ft.Page):
    """
    FleDjSONのエントリーポイント
    
    FleDjSONAppクラスを初期化して実行します。
    
    Args:
        page (ft.Page): Fletページオブジェクト
    """
    print("Starting FleDjSON...")
    print(f"System: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print("Environment check passed")
    print("Launching application...\n")
    
    # FleDjSONAppを初期化して実行
    app = FleDjSONApp(page)
    app.run()


if __name__ == "__main__":
    # assetsディレクトリを明示的に指定
    ft.app(target=main, assets_dir="assets")