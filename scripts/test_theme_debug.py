#!/usr/bin/env python3
"""テーマボタンデバッグテスト"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# 最初のインポートとデバッグ出力
print("[DEBUG] Starting imports...")
import flet as ft
print(f"[DEBUG] Flet version: {ft.__version__ if hasattr(ft, '__version__') else 'Unknown'}")

from app import FleDjSONApp

def main(page: ft.Page):
    """テストアプリケーション"""
    print("[DEBUG] main function called")
    
    # アプリケーションを作成
    app = FleDjSONApp(page)
    
    # デバッグ: managersの状態を確認
    print(f"[DEBUG] app.managers keys: {list(app.managers.keys())}")
    
    # アプリケーションを実行
    app.run()
    
    # 3秒後に自動終了
    import threading
    def close_app():
        import time
        time.sleep(3)
        print("[DEBUG] Auto-closing app after 3 seconds")
        page.window_close()
    
    threading.Thread(target=close_app, daemon=True).start()


if __name__ == "__main__":
    print("[DEBUG] Starting Flet app...")
    ft.app(target=main)