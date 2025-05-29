#!/usr/bin/env python3
"""
名前を付けて保存後のファイル名表示更新のテスト

手動テスト手順:
1. アプリケーションを起動
2. JSONファイルを開く
3. 画面上部のファイル名と解析結果ボックスのファイル名を確認
4. 「名前を付けて保存...」ボタンをクリック
5. 別の名前で保存
6. 画面上部のファイル名と解析結果ボックスが新しいファイル名に更新されることを確認
7. その後Ctrl+Sで保存すると、新しいファイルに保存されることを確認
"""

import os
import sys
import json
from datetime import datetime

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_test_data():
    """テスト用のJSONファイルを作成"""
    test_data = [
        {
            "id": 1,
            "name": "テストデータ1",
            "timestamp": datetime.now().isoformat()
        },
        {
            "id": 2,
            "name": "テストデータ2",
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    # テスト用ファイルを作成
    test_file = "/tmp/test_save_as_original.json"
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] テストファイルを作成しました: {test_file}")
    print("\n手動テスト手順:")
    print("1. poetry run python src/main.py でアプリを起動")
    print(f"2. 「JSONファイルを選択」で {test_file} を開く")
    print("3. ファイル名が「test_save_as_original.json」と表示されることを確認")
    print("4. 「名前を付けて保存...」をクリック")
    print("5. 「test_save_as_new.json」など別の名前で保存")
    print("6. 画面上部とファイル解析結果の両方で新しいファイル名が表示されることを確認")
    print("7. データを編集してCtrl+Sで保存")
    print("8. 新しいファイルに保存されることを確認")

if __name__ == "__main__":
    create_test_data()