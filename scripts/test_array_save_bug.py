#!/usr/bin/env python
"""
配列型追加時のショートカットキー保存バグの検証スクリプト

このスクリプトは以下の問題を検証します：
- JSONノード編集時に新しい配列型フィールドを追加
- キーボードショートカット（Ctrl+S/Cmd+S）で保存
- 他のノードに同じフィールドが追加されてしまう問題
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

# テスト用データの作成
TEST_DATA = [
    {"id": 1, "name": "Item 1"},
    {"id": 2, "name": "Item 2"},
    {"id": 3, "name": "Item 3"}
]

# シンプルなテスト用JSON
SIMPLE_TEST_FILE = "test_array_save_bug.json"

# より複雑なテストケース
NESTED_TEST_DATA = [
    {"id": 1, "name": "Parent 1", "children": [{"id": "c1", "name": "Child 1"}]},
    {"id": 2, "name": "Parent 2"}
]

MIXED_TEST_DATA = [
    {"id": 1, "name": "Item 1", "tags": ["tag1", 123, True, {"nested": "obj"}]},
    {"id": 2, "name": "Item 2"}
]

NESTED_TEST_FILE = "test_array_save_bug_nested.json"
MIXED_TEST_FILE = "test_array_save_bug_mixed.json"


def create_test_files():
    """テスト用JSONファイルを作成"""
    # 一時ディレクトリにテストファイルを作成
    test_dir = Path(tempfile.gettempdir()) / "fledjson_test"
    test_dir.mkdir(exist_ok=True)
    
    # シンプルなテストファイル
    simple_file = test_dir / SIMPLE_TEST_FILE
    with open(simple_file, 'w', encoding='utf-8') as f:
        json.dump(TEST_DATA, f, ensure_ascii=False, indent=2)
    
    # ネストしたテストファイル
    nested_file = test_dir / NESTED_TEST_FILE
    with open(nested_file, 'w', encoding='utf-8') as f:
        json.dump(NESTED_TEST_DATA, f, ensure_ascii=False, indent=2)
    
    # 混合型テストファイル
    mixed_file = test_dir / MIXED_TEST_FILE
    with open(mixed_file, 'w', encoding='utf-8') as f:
        json.dump(MIXED_TEST_DATA, f, ensure_ascii=False, indent=2)
    
    print(f"テストファイルを作成しました:")
    print(f"- {simple_file}")
    print(f"- {nested_file}")
    print(f"- {mixed_file}")
    
    return {
        "simple": str(simple_file),
        "nested": str(nested_file),
        "mixed": str(mixed_file)
    }


def verify_test_results(file_path):
    """テスト結果を検証する"""
    # ファイルを読み込んで各ノードを検証
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # ID=1のノードには新しい配列フィールドがあるはず
    node1 = next((item for item in data if isinstance(item, dict) and item.get("id") == 1), None)
    if not node1 or "new_array" not in node1:
        print(f"[ERROR] エラー: ID=1のノードに'new_array'フィールドがありません!")
        return False
    
    # ID=2と3のノードには新しい配列フィールドがないはず
    other_nodes_with_array = [
        item for item in data 
        if isinstance(item, dict) and item.get("id") != 1 and "new_array" in item
    ]
    
    if other_nodes_with_array:
        print(f"[ERROR] バグが発生! 他のノードにも配列フィールドが漏れています:")
        for node in other_nodes_with_array:
            print(f"  - ID={node.get('id')} に 'new_array' = {node.get('new_array')} が存在")
        return False
    
    print(f"[OK] テスト成功! 配列フィールドは正しく分離されています")
    return True


def test_array_independence(test_files):
    """配列参照の独立性を検証するテスト"""
    results = {}
    
    # 各テストファイルに対して検証
    for test_type, file_path in test_files.items():
        print(f"\n----- {test_type}テストケースの検証 -----")
        print(f"テストファイル: {file_path}")
        
        # テスト手順:
        # 1. フレットアプリを起動してファイルを読み込む
        # 2. ノード1を選択・編集して配列型フィールドを追加
        # 3. ショートカットキーで保存
        # 4. ファイル内容を検証
        
        # テスト実行
        print(f"以下の手順でテストを実行してください:")
        print(f"1. アプリケーションを起動")
        print(f"2. テストファイル {file_path} を読み込む")
        print(f"3. ID=1のノードを選択して編集")
        print(f"4. フィールド名='new_array'、値='[\"test\", 123]'を追加")
        print(f"5. Ctrl+S/Cmd+Sでショートカット保存")
        print(f"6. アプリケーションを閉じる")
        print(f"7. Y キーを押してテスト結果を検証")
        
        # ユーザーの確認を待つ
        user_input = input("テストを実行し、検証する準備ができたら Y を押してください: ")
        if user_input.strip().upper() == 'Y':
            results[test_type] = verify_test_results(file_path)
    
    # 全体の結果を表示
    print("\n===== テスト結果サマリー =====")
    all_passed = all(results.values())
    if all_passed:
        print("[OK] すべてのテストが成功しました!")
    else:
        print("[ERROR] 一部のテストが失敗しました:")
        for test_type, result in results.items():
            print(f"  - {test_type}: {'[OK] 成功' if result else '[ERROR] 失敗'}")
    
    return all_passed


if __name__ == "__main__":
    print("配列型追加時のショートカットキー保存バグの検証を開始します...\n")
    
    # テストファイルの作成
    test_files = create_test_files()
    
    # テスト実行
    success = test_array_independence(test_files)
    
    # 終了コード
    sys.exit(0 if success else 1)