#!/usr/bin/env python3
"""
検索機能バグ修正テスト

このスクリプトは、新規追加したノードが検索に引っかからないバグの修正をテストするためのものです。
修正前は、新規ノード追加時に検索インデックスが更新されなかったため、追加したノードが検索に引っかかりませんでした。
修正後は、以下の改善を行っています：
- ノード追加後に検索インデックスを確実に更新する
- 検索マネージャーがない場合は作成する
- 検索インデックスの完全再構築を行い、確実性を高める
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
from src.search_manager import SearchManager

def create_test_data() -> Dict[str, Any]:
    """テスト用のデータを作成"""
    return {
        "raw_data": [
            {
                "id": "1",
                "name": "ノード1",
                "description": "ルートノード1",
                "tags": ["テスト", "サンプル"]
            },
            {
                "id": "2",
                "name": "ノード2",
                "description": "ルートノード2",
                "tags": ["サンプル", "データ"]
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

def print_search_index(search_manager, title: str = "検索インデックス"):
    """検索インデックスの内容を出力する"""
    print(f"\n{title}:")
    for item in search_manager.search_index:
        print(f"  ID: {item['id']}")
        print(f"  テキスト（最初の50文字）: {item['text'][:50]}...")
        print()

def perform_search(search_manager, keyword: str):
    """検索を実行し、結果を表示する"""
    print(f"\n[DEBUG] キーワード '{keyword}' で検索:")
    
    # 検索クエリを実行
    keyword_lower = keyword.lower()
    
    # 検索結果を収集
    results = []
    for item in search_manager.search_index:
        if keyword_lower in item['text'].lower():
            results.append(item)
    
    # 結果を表示
    if results:
        print(f"[OK] {len(results)}件の結果が見つかりました")
        for i, result in enumerate(results):
            print(f"  [{i+1}] ID: {result['id']}")
            
            # キーワードの周辺テキストを表示
            text = result['text'].lower()
            pos = text.find(keyword_lower)
            if pos >= 0:
                start = max(0, pos - 20)
                end = min(len(text), pos + len(keyword_lower) + 20)
                context = text[start:end]
                print(f"      コンテキスト: ...{context}...")
    else:
        print("[ERROR] 結果は見つかりませんでした")
    print()

def main():
    """メイン処理"""
    print("=== 検索機能のテスト開始 ===")
    
    # テスト環境の設定
    app_state = create_test_data()
    ui_controls = {}
    
    # data_mapを初期化
    for item in app_state["raw_data"]:
        app_state["data_map"][item["id"]] = item
    
    # DataManagerとSearchManagerの作成
    data_manager = DataManager(app_state, ui_controls)
    search_manager = SearchManager(app_state, ui_controls)
    app_state["search_manager"] = search_manager
    
    # 初期インデックスを構築
    search_manager.build_search_index()
    print_search_index(search_manager, "初期検索インデックス")
    
    # 初期検索テスト
    perform_search(search_manager, "テスト")
    perform_search(search_manager, "サンプル")
    
    # テスト1: 特徴的なキーワードを持つ新しいノードを追加
    print("\n--- テスト1: 特徴的なキーワードを持つノードを追加 ---")
    unique_node = {
        "id": "3",
        "name": "特徴的なノード",
        "description": "このノードは特徴的なキーワード「UNIQUESTRING123」を含む",
        "tags": ["特殊", "UNIQUESTRING123"]
    }
    
    data_manager.add_new_node(None, unique_node)
    print("[OK] 新しいノードを追加しました")
    
    # 追加後の検索インデックスを確認
    print_search_index(search_manager, "ノード追加後の検索インデックス")
    
    # 追加したノードのキーワードで検索
    perform_search(search_manager, "UNIQUESTRING123")
    
    # テスト2: 複数のフィールドにデータを持つノードを追加
    print("\n--- テスト2: 複数のフィールドにデータを持つノードを追加 ---")
    multi_field_node = {
        "id": "4",
        "name": "複数フィールドノード",
        "description": "複数のフィールドにデータを持つノード",
        "email": "test@example.com",
        "phone": "123-456-7890",
        "tags": ["メール", "電話"],
        "extra": {
            "note": "これは追加データです",
            "priority": "高"
        }
    }
    
    data_manager.add_new_node("1", multi_field_node)
    print("[OK] 複数フィールドを持つノードを追加しました")
    
    # 各フィールドで検索
    perform_search(search_manager, "test@example.com")
    perform_search(search_manager, "123-456-7890")
    perform_search(search_manager, "追加データ")
    
    # テスト3: 子ノードを持つ親ノードを追加
    print("\n--- テスト3: 子ノードを持つ親ノードを追加 ---")
    parent_node = {
        "id": "5",
        "name": "親ノード",
        "description": "子を持つ親ノード",
        "tags": ["親", "PARENTTAG"]
    }
    
    data_manager.add_new_node(None, parent_node)
    
    child_node = {
        "id": "6",
        "name": "子ノード",
        "description": "親に属する子ノード",
        "tags": ["子", "CHILDTAG"]
    }
    
    data_manager.add_new_node("5", child_node)
    print("[OK] 親ノードと子ノードを追加しました")
    
    # 親と子のタグで検索
    perform_search(search_manager, "PARENTTAG")
    perform_search(search_manager, "CHILDTAG")
    
    print("\n=== 検索機能のテスト完了 ===")
    
    # 期待される結果の確認
    print("\n期待される結果:")
    print("1. 新規追加したノードが検索インデックスに含まれる")
    print("2. 特徴的なキーワードで検索すると、該当するノードが見つかる")
    print("3. 複数のフィールドにあるデータで検索できる")
    print("4. 親ノードと子ノードの両方が検索で見つかる")

if __name__ == "__main__":
    main()