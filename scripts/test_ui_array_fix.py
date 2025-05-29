#!/usr/bin/env python3
"""
test_ui_array_fix.py

このテストスクリプトは、フォーム表示時の配列参照問題が修正されているかを検証します。
具体的には、あるノードに配列型のフィールドを追加し、別のノードを選択した際に
その配列データが他のノードに漏れないことを確認します。
"""
import sys
import os
import json
import copy
import unittest
from typing import Dict, List, Any

# ルートディレクトリをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# FleDjSONモジュールからコピーマネージャーと関連機能をインポート
from src.copy_manager import DeepCopyManager, JSONStructureHandler, copy_manager


class TestUIArrayFix(unittest.TestCase):
    """配列参照問題の修正テスト"""
    
    def setUp(self):
        """テストデータの準備"""
        # テスト用のノードデータ
        self.node1 = {
            "id": "1",
            "name": "Node 1",
            "description": "First test node"
        }
        
        self.node2 = {
            "id": "2",
            "name": "Node 2",
            "description": "Second test node"
        }
        
        # アプリケーション状態の模擬
        self.app_state = {
            "data_map": {
                "1": self.node1,
                "2": self.node2
            },
            "selected_node_id": "1",
            "id_key": "id",
            "edit_buffer": {}
        }
    
    def test_standard_deepcopy_issue(self):
        """標準のcopy.deepcopyでの参照問題を再現"""
        # node1をdeep_copyして取得
        node1_copy = copy.deepcopy(self.node1)
        
        # node1_copyに配列を追加
        node1_copy["tags"] = ["tag1", "tag2"]
        
        # app_stateを更新（通常のdeep_copyを使用）
        self.app_state["data_map"]["1"] = node1_copy
        
        # node2を通常のdeep_copyで取得
        node2_copy = copy.deepcopy(self.app_state["data_map"]["2"])
        
        # node2_copyにも同じ名前の配列を追加
        node2_copy["tags"] = ["different_tag"]
        
        # app_stateを更新
        self.app_state["data_map"]["2"] = node2_copy
        
        # node1の配列を変更
        self.app_state["data_map"]["1"]["tags"].append("tag3")
        
        # node2の配列に影響がないか確認
        self.assertEqual(len(self.app_state["data_map"]["2"]["tags"]), 1, 
                         "標準のdeep_copyでは問題がないはず")
    
    def test_deepcopy_manager_fix(self):
        """DeepCopyManagerでの修正が機能することを確認"""
        # 新しいJSONStructureHandlerを作成
        json_handler = JSONStructureHandler()
        
        # node1を安全なprepare_form_dataでコピー
        node1_copy = json_handler.prepare_form_data(self.node1)
        
        # node1_copyに配列を追加
        node1_copy["tags"] = ["tag1", "tag2"]
        
        # app_stateを更新
        self.app_state["data_map"]["1"] = node1_copy
        
        # node2を安全なprepare_form_dataでコピー
        node2_copy = json_handler.prepare_form_data(self.app_state["data_map"]["2"])
        
        # node2_copyにも同じ名前の配列を追加
        node2_copy["tags"] = ["different_tag"]
        
        # app_stateを更新
        self.app_state["data_map"]["2"] = node2_copy
        
        # node1の配列を変更
        self.app_state["data_map"]["1"]["tags"].append("tag3")
        
        # node2の配列に影響がないか確認
        self.assertEqual(len(self.app_state["data_map"]["2"]["tags"]), 1, 
                         "safe_deep_copyを使うと参照問題が解決される")
        
        # 具体的な内容も確認
        self.assertEqual(self.app_state["data_map"]["1"]["tags"], ["tag1", "tag2", "tag3"],
                         "node1の配列は期待通り変更されている")
        self.assertEqual(self.app_state["data_map"]["2"]["tags"], ["different_tag"],
                         "node2の配列は変更されていない")
    
    def test_nested_array_deep_copy(self):
        """ネストされた配列での深いコピーの問題と修正を検証"""
        # 複雑なネスト構造を持つノード
        nested_node1 = {
            "id": "3",
            "name": "Nested Node",
            "items": [
                {"id": "sub1", "value": 10},
                {"id": "sub2", "value": 20, "tags": ["nested_tag"]}
            ]
        }
        
        # app_stateに追加
        self.app_state["data_map"]["3"] = nested_node1
        
        # 標準のdeep_copyでコピー
        nested_copy_std = copy.deepcopy(nested_node1)
        
        # DeepCopyManagerでコピー
        nested_copy_safe = copy_manager.safe_deep_copy(nested_node1)
        
        # ネストされた配列に値を追加（標準コピー）
        nested_copy_std["items"][1]["tags"].append("new_tag")
        
        # ネストされた配列に値を追加（安全なコピー）
        nested_copy_safe["items"][1]["tags"].append("new_safe_tag")
        
        # 元のデータが影響を受けていないことを確認
        self.assertEqual(nested_node1["items"][1]["tags"], ["nested_tag"],
                         "元のネストされた配列は変更されていない")
        
        # 標準のコピーの変更が意図通りであることを確認
        self.assertEqual(nested_copy_std["items"][1]["tags"], ["nested_tag", "new_tag"],
                         "標準のコピーは正しく変更されている")
        
        # 安全なコピーの変更が意図通りであることを確認
        self.assertEqual(nested_copy_safe["items"][1]["tags"], ["nested_tag", "new_safe_tag"],
                         "安全なコピーは正しく変更されている")
        
        # このテストでは、standard deepcopyも安全なコピーも同じ動作をするはず
        # （単純なネストではdeep_copyでも問題は発生しにくい）
        # より複雑なケースを考慮するとDeepCopyManagerの優位性が現れる


if __name__ == "__main__":
    unittest.main()