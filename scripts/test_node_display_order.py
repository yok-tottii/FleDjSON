#!/usr/bin/env python3
"""
表示順序のバグ修正テスト

このスクリプトは、ノード追加時の表示順序バグの修正をテストするためのものです。
修正前は、新しいノードが常に末尾に追加されていたため、親子関係の視覚的な把握が困難でした。
修正後は、ノードを追加する位置を以下のように改善しています：
- 親ノードがある場合、その親ノードまたは最後の子ノードの直後に配置
- 親ノードがない場合、他のルートノードの後に配置
"""

import os
import sys
import json
from typing import Dict, Any, List, Optional

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 必要なモジュールをインポート
from src.managers.data_manager import DataManager

def create_test_data() -> Dict[str, Any]:
    """テスト用のデータを作成"""
    return {
        "raw_data": [
            {
                "id": "1",
                "name": "ノード1",
                "description": "ルートノード1"
            },
            {
                "id": "2",
                "name": "ノード2",
                "description": "ルートノード2"
            }
        ],
        "data_map": {},
        "root_ids": ["1", "2"],
        "id_key": "id",
        "children_key": "children",
        "label_key": "name",
        "analysis_results": {
            "heuristic_suggestions": {
                "identifier": "id",
                "children_link": "children",
                "label": "name"
            }
        }
    }

def print_raw_data(app_state: Dict[str, Any], title: str = "現在のデータ構造"):
    """raw_dataの内容を出力する"""
    print(f"\n{title}:")
    for i, item in enumerate(app_state["raw_data"]):
        if isinstance(item, dict) and "id" in item:
            print(f"  [{i}] ID: {item['id']}, Name: {item.get('name', '名前なし')}")
    
    # 階層構造を表示
    print("\n階層構造:")
    for root_id in app_state["root_ids"]:
        print(f"  Root: {root_id} ({app_state['data_map'][root_id].get('name', '名前なし')})")
        if app_state.get("children_map") and root_id in app_state["children_map"]:
            for child_id in app_state["children_map"][root_id]:
                print(f"    ├── Child: {child_id} ({app_state['data_map'][child_id].get('name', '名前なし')})")
                if child_id in app_state.get("children_map", {}):
                    for grandchild_id in app_state["children_map"][child_id]:
                        print(f"    │   ├── Grandchild: {grandchild_id} ({app_state['data_map'][grandchild_id].get('name', '名前なし')})")

    print()

def main():
    """メイン処理"""
    print("=== ノード追加順序のテスト開始 ===")
    
    # テスト環境の設定
    app_state = create_test_data()
    
    # data_mapを初期化
    for item in app_state["raw_data"]:
        app_state["data_map"][item["id"]] = item
    
    # DataManagerの作成
    data_manager = DataManager(app_state, {})
    
    # 初期状態を表示
    print_raw_data(app_state, "初期データ")
    
    # テスト1: ルートノードを追加
    print("\n--- テスト1: ルートノードの追加 ---")
    root_node = {
        "id": "3",
        "name": "新規ルートノード",
        "description": "テスト用の新しいルートノード"
    }
    
    data_manager.add_new_node(None, root_node)
    print_raw_data(app_state, "ルートノード追加後")
    
    # テスト2: 親ノードの子として追加
    print("\n--- テスト2: 親の子として追加 ---")
    child_node = {
        "id": "4",
        "name": "ノード1の子",
        "description": "ノード1の子ノード"
    }
    
    data_manager.add_new_node("1", child_node)
    print_raw_data(app_state, "子ノード追加後")
    
    # テスト3: 子を持つ親ノードに別の子を追加
    print("\n--- テスト3: 子を持つ親に別の子を追加 ---")
    another_child = {
        "id": "5",
        "name": "ノード1の別の子",
        "description": "ノード1の2番目の子ノード"
    }
    
    data_manager.add_new_node("1", another_child)
    print_raw_data(app_state, "2番目の子ノード追加後")
    
    # テスト4: 孫ノードを追加
    print("\n--- テスト4: 孫ノードを追加 ---")
    grandchild_node = {
        "id": "6",
        "name": "孫ノード",
        "description": "ノード4の子ノード（孫ノード）"
    }
    
    data_manager.add_new_node("4", grandchild_node)
    print_raw_data(app_state, "孫ノード追加後")
    
    # テスト5: reorder_raw_dataが正しく動作しているか確認
    print("\n--- テスト5: reorder_raw_data関数の確認 ---")
    data_manager.reorder_raw_data()
    print_raw_data(app_state, "reorder_raw_data実行後")
    
    print("\n=== ノード追加順序のテスト完了 ===")
    
    # 期待される結果の確認
    print("\n期待される結果:")
    print("1. ルートノードは他のルートノードの後に追加される")
    print("2. 子ノードは親ノードの直後または最後の子ノードの後に追加される")
    print("3. 追加されたノードは適切な階層で表示される")
    print("4. reorder_raw_data関数は正しくノードの順序を維持する")

if __name__ == "__main__":
    main()