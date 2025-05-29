#!/usr/bin/env python3
"""
ノード削除後の保存確認ダイアログの動作テスト

テスト手順：
1. アプリケーションを起動
2. JSONファイルを読み込む
3. ノードを削除する
4. Ctrl+S（またはCmd+S）で保存を試みる
5. 確認ダイアログが表示されることを確認
"""

import flet as ft
import time
import sys
import os

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
from app import FleDjSONApp

def test_delete_confirmation(page: ft.Page):
    """削除確認ダイアログのテスト"""
    print("\n=== ノード削除後の保存確認ダイアログテスト ===\n")
    
    # アプリケーションの初期化
    app = FleDjSONApp(page)
    app.run()
    
    # テスト用のJSONデータを作成
    test_data = [
        {"id": 1, "name": "Root", "children": [2, 3]},
        {"id": 2, "name": "Child 1", "parent": 1},
        {"id": 3, "name": "Child 2", "parent": 1}
    ]
    
    # DataManagerを取得してテストデータを設定
    data_manager = app.managers.get("data_manager")
    if data_manager:
        # テストデータを直接設定
        app.app_state["raw_data"] = test_data
        app.app_state["current_file"] = "/tmp/test_delete.json"
        
        # データマップを構築
        data_manager.build_data_map_and_tree()
        
        print("[OK] テストデータを設定しました")
        print(f"  ノード数: {len(test_data)}")
        
        # フラグの初期状態を確認
        print(f"\n初期状態:")
        print(f"  node_deleted_since_last_save: {app.app_state.get('node_deleted_since_last_save', 'undefined')}")
        
        # ノードを削除（シミュレート）
        print(f"\nノード '2' を削除します...")
        success = data_manager.delete_node("2")
        
        if success:
            print(f"[OK] ノード削除成功")
            print(f"  node_deleted_since_last_save: {app.app_state.get('node_deleted_since_last_save', 'undefined')}")
            
            # UIを更新
            ui_manager = app.managers.get("ui_manager")
            if ui_manager:
                ui_manager.update_tree_view()
                
            print("\nテスト手順:")
            print("1. Ctrl+S（Mac: Cmd+S）を押して保存を試みてください")
            print("2. 削除確認ダイアログが表示されることを確認してください")
            print("3. キャンセルを選択すると保存されません")
            print("4. 保存を選択すると削除が確定されます")
            
        else:
            print("[ERROR] ノード削除失敗")
    else:
        print("[ERROR] DataManagerが見つかりません")
    
    print("\n=== テスト準備完了 ===")
    print("アプリケーションでテストを実行してください")

if __name__ == "__main__":
    print("ノード削除後の保存確認ダイアログテストを開始します...")
    ft.app(target=test_delete_confirmation)