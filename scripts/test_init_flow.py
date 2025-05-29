#!/usr/bin/env python3
"""初期化フローテスト"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import flet as ft
from app import FleDjSONApp

# グローバル変数でアプリインスタンスを保持
app_instance = None

def main(page: ft.Page):
    """テストアプリケーション"""
    global app_instance
    
    print("[TEST] main function called")
    
    # アプリケーションを作成
    app_instance = FleDjSONApp(page)
    print("[TEST] FleDjSONApp instance created")
    
    # runメソッドを明示的に呼び出し
    print("[TEST] Calling app.run()...")
    app_instance.run()
    print("[TEST] app.run() completed")
    
    # 状態を確認
    if hasattr(app_instance, 'page'):
        print(f"[TEST] Page controls count: {len(app_instance.page.controls)}")
        for i, control in enumerate(app_instance.page.controls):
            print(f"[TEST] Control {i}: {type(control).__name__}")


if __name__ == "__main__":
    ft.app(target=main)