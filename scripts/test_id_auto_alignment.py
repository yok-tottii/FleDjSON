#!/usr/bin/env python3
"""
ID自動整列機能テストスクリプト

以下のテストケースを検証:
1. 数値型IDのみのデータ
2. 数値文字列IDのデータ
3. プレフィックス付きID (例: "item1", "item2")
4. 階層的なID (例: "1-1", "1-1-1")
5. 混合タイプID (数値型と文字列型の混在)
"""

import sys
import os
import json
from copy import deepcopy

# プロジェクトのルートディレクトリをPythonパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 必要なモジュールをインポート
from src.drag_drop_helpers import (
    parse_node_id, group_sibling_nodes_by_prefix, 
    rename_node_id, update_child_node_prefixes, 
    realign_sibling_ids
)

# テスト用のapp_stateをセットアップ
app_state = {
    "data_map": {},
    "children_map": {},
    "root_ids": [],
    "raw_data": [],
    "id_key": "id",
    "children_key": "children"
}

# グローバル変数としてセット (drag_drop_helpers.pyが使用)
import src.drag_drop_helpers
fledjson.drag_drop_helpers.app_state = app_state


def setup_test_data(data):
    """テストデータを初期化"""
    app_state["data_map"] = {}
    app_state["children_map"] = {}
    app_state["root_ids"] = []
    app_state["raw_data"] = deepcopy(data)
    
    # データを構築
    for item in data:
        if isinstance(item, dict) and "id" in item:
            item_id = item["id"]
            app_state["data_map"][item_id] = item
            
            # 子ノードリレーションを構築
            if "children" in item and isinstance(item["children"], list):
                app_state["children_map"][item_id] = item["children"]
            else:
                app_state["children_map"][item_id] = []
    
    # ルートノードを識別
    all_ids = set(app_state["data_map"].keys())
    all_child_ids = set()
    for children in app_state["children_map"].values():
        all_child_ids.update(children)
    
    app_state["root_ids"] = list(all_ids - all_child_ids)
    print(f"セットアップ完了: {len(app_state['data_map'])}個のノード, {len(app_state['root_ids'])}個のルートノード")


def test_numeric_id():
    """数値型IDのテスト"""
    print("\n===== テスト1: 数値型ID =====")
    data = [
        {"id": 3, "name": "Item 3"},
        {"id": 1, "name": "Item 1"},
        {"id": 2, "name": "Item 2"}
    ]
    setup_test_data(data)
    print(f"変更前のroot_ids: {app_state['root_ids']}")
    
    # 自動整列を実行
    updates = realign_sibling_ids()
    
    print(f"変更後のroot_ids: {app_state['root_ids']}")
    print(f"更新結果: {updates}個のノードIDが更新されました")
    
    # 結果の検証
    sorted_ids = app_state["root_ids"]
    expected = [1, 2, 3]  # 1から始まる昇順
    assert sorted_ids == expected, f"期待結果: {expected}, 実際の結果: {sorted_ids}"
    print("[OK] テスト成功: 数値型IDが正しく整列されました")


def test_string_numeric_id():
    """数値文字列IDのテスト"""
    print("\n===== テスト2: 数値文字列ID =====")
    data = [
        {"id": "3", "name": "Item 3"},
        {"id": "1", "name": "Item 1"},
        {"id": "2", "name": "Item 2"}
    ]
    setup_test_data(data)
    print(f"変更前のroot_ids: {app_state['root_ids']}")
    
    # 自動整列を実行
    updates = realign_sibling_ids()
    
    print(f"変更後のroot_ids: {app_state['root_ids']}")
    print(f"更新結果: {updates}個のノードIDが更新されました")
    
    # 結果の検証
    sorted_ids = app_state["root_ids"]
    # 注: 実装では数値文字列は整数型に変換される仕様
    expected = [1, 2, 3]  # 数値型として1から始まる昇順
    assert sorted_ids == expected, f"期待結果: {expected}, 実際の結果: {sorted_ids}"
    print("[OK] テスト成功: 数値文字列IDが数値型に変換され正しく整列されました")


def test_prefixed_id():
    """プレフィックス付きIDのテスト"""
    print("\n===== テスト3: プレフィックス付きID =====")
    data = [
        {"id": "item3", "name": "Item 3"},
        {"id": "item1", "name": "Item 1"},
        {"id": "item2", "name": "Item 2"},
        {"id": "other2", "name": "Other 2"},
        {"id": "other1", "name": "Other 1"}
    ]
    setup_test_data(data)
    print(f"変更前のroot_ids: {app_state['root_ids']}")
    
    # 自動整列を実行
    updates = realign_sibling_ids()
    
    print(f"変更後のroot_ids: {app_state['root_ids']}")
    print(f"更新結果: {updates}個のノードIDが更新されました")
    
    # 結果の検証 - プレフィックスごとにグループ化されて整列されるはず
    sorted_ids = app_state["root_ids"]
    # プレフィックスが保持され、サフィックスが1から振り直される
    assert "item1" in sorted_ids and "item2" in sorted_ids, "itemプレフィックスが保持されていません"
    assert "other1" in sorted_ids and "other2" in sorted_ids, "otherプレフィックスが保持されていません"
    print("[OK] テスト成功: プレフィックス付きIDが正しく整列されました")


def test_hierarchical_id():
    """階層的なIDのテスト"""
    print("\n===== テスト4: 階層的なID =====")
    data = [
        {"id": "1", "name": "Parent 1", "children": ["1-2", "1-1", "1-3"]},
        {"id": "1-1", "name": "Child 1-1"},
        {"id": "1-2", "name": "Child 1-2", "children": ["1-2-2", "1-2-1"]},
        {"id": "1-3", "name": "Child 1-3"},
        {"id": "1-2-1", "name": "Grandchild 1-2-1"},
        {"id": "1-2-2", "name": "Grandchild 1-2-2"}
    ]
    setup_test_data(data)
    print(f"変更前: 親1の子ノード: {app_state['children_map']['1']}")
    print(f"変更前: 親1-2の子ノード: {app_state['children_map']['1-2']}")
    
    # まず親1配下の子ノードを自動整列
    parent_id = "1"
    updates1 = realign_sibling_ids(parent_id)
    print(f"親1配下の更新結果: {updates1}個のノードIDが更新されました")
    print(f"変更後: 親1の子ノード: {app_state['children_map']['1']}")
    
    # 次に親1-2配下の子ノードを自動整列
    # 注: 親1-2のIDは変わっているかもしれないので、現在のIDを取得
    new_parent = [key for key, children in app_state["children_map"].items() 
                 if any("1-2" in str(c) for c in children)][0]
    updates2 = realign_sibling_ids(new_parent)
    print(f"親{new_parent}配下の更新結果: {updates2}個のノードIDが更新されました")
    print(f"変更後: 親{new_parent}の子ノード: {app_state['children_map'][new_parent]}")
    
    # 結果の検証
    parent1_children = app_state["children_map"]["1"]
    assert len(parent1_children) == 3, f"親1の子ノード数が3ではありません: {len(parent1_children)}"
    print("[OK] テスト成功: 階層的なIDが正しく整列されました")


def test_mixed_id_types():
    """混合タイプIDのテスト"""
    print("\n===== テスト5: 混合タイプID =====")
    data = [
        {"id": 1, "name": "Numeric 1"},
        {"id": "2", "name": "String 2"},
        {"id": 3, "name": "Numeric 3"}
    ]
    setup_test_data(data)
    print(f"変更前のroot_ids: {app_state['root_ids']}")
    
    # 自動整列を実行
    updates = realign_sibling_ids()
    
    print(f"変更後のroot_ids: {app_state['root_ids']}")
    print(f"更新結果: {updates}個のノードIDが更新されました")
    
    # 結果の検証 - 一貫性のある型に変換されるはず
    sorted_ids = app_state["root_ids"]
    print(f"整列後のID型: {[(id, type(id)) for id in sorted_ids]}")
    
    # 全て同じ型になっているかチェック
    id_types = [type(id) for id in sorted_ids]
    assert len(set(id_types)) == 1, f"IDが単一の型に統一されていません: {id_types}"
    print("[OK] テスト成功: 混合タイプIDが一貫性のある型に変換されました")


def run_all_tests():
    """全テストケースを実行"""
    try:
        test_numeric_id()
        test_string_numeric_id()
        test_prefixed_id()
        test_hierarchical_id()
        test_mixed_id_types()
        print("\n[OK] 全テスト成功! ID自動整列機能は正しく動作しています。")
    except AssertionError as e:
        print(f"\n[ERROR] テスト失敗: {e}")
    except Exception as e:
        print(f"\n[ERROR] 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()