#!/usr/bin/env python3
"""
FlattenManagerの分離テスト
Fletの依存関係を最小限に抑えた単体テスト
"""

import unittest
from unittest.mock import Mock
import sys
import os

# テスト対象のモジュールをインポート
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from managers.flatten_manager import FlattenManager


class TestFlattenManagerIsolated(unittest.TestCase):
    """FlattenManagerの分離テスト"""
    
    def setUp(self):
        """テストの準備"""
        self.app_state = {}
        self.ui_controls = {}
        
        # FlattenManagerのインスタンスを作成
        self.flatten_manager = FlattenManager(
            app_state=self.app_state,
            ui_controls=self.ui_controls,
            page=None,
            event_hub=None
        )
    
    def test_flatten_manager_initialization(self):
        """FlattenManagerの初期化テスト"""
        self.assertIsNotNone(self.flatten_manager)
        self.assertEqual(self.flatten_manager.app_state, self.app_state)
        self.assertEqual(self.flatten_manager.ui_controls, self.ui_controls)
    
    def test_flatten_simple_nested_structure(self):
        """単純なネスト構造の平坦化テスト"""
        nested_data = {
            "id": "root",
            "name": "Root Node",
            "children": [
                {
                    "id": "child1",
                    "name": "Child 1",
                    "children": []
                },
                {
                    "id": "child2", 
                    "name": "Child 2",
                    "children": [
                        {
                            "id": "grandchild1",
                            "name": "Grandchild 1",
                            "children": []
                        }
                    ]
                }
            ]
        }
        
        flattened = self.flatten_manager.flatten_nested_json(nested_data)
        
        self.assertEqual(len(flattened), 4)  # root + 2 children + 1 grandchild
        
        # IDでソートして結果を確認
        flattened_by_id = {item["id"]: item for item in flattened}
        
        self.assertIn("root", flattened_by_id)
        self.assertIn("child1", flattened_by_id)
        self.assertIn("child2", flattened_by_id)
        self.assertIn("grandchild1", flattened_by_id)
        
        # 階層構造が削除されていることを確認
        for item in flattened:
            self.assertEqual(item.get("children", []), [])
    
    def test_flatten_list_input(self):
        """リスト形式の入力データの平坦化テスト"""
        nested_list = [
            {
                "id": "item1",
                "name": "Item 1",
                "children": [
                    {
                        "id": "subitem1",
                        "name": "Sub Item 1",
                        "children": []
                    }
                ]
            },
            {
                "id": "item2",
                "name": "Item 2",
                "children": []
            }
        ]
        
        flattened = self.flatten_manager.flatten_nested_json(nested_list)
        
        self.assertEqual(len(flattened), 3)  # 2 items + 1 subitem
        
        flattened_ids = [item["id"] for item in flattened]
        self.assertIn("item1", flattened_ids)
        self.assertIn("item2", flattened_ids)
        self.assertIn("subitem1", flattened_ids)
    
    def test_flatten_custom_keys(self):
        """カスタムキー名での平坦化テスト"""
        nested_data = {
            "user_id": "u1",
            "name": "User 1",
            "subordinates": [
                {
                    "user_id": "u2",
                    "name": "User 2",
                    "subordinates": []
                }
            ]
        }
        
        flattened = self.flatten_manager.flatten_nested_json(
            nested_data, 
            id_key="user_id", 
            children_key="subordinates"
        )
        
        self.assertEqual(len(flattened), 2)
        
        flattened_by_id = {item["user_id"]: item for item in flattened}
        self.assertIn("u1", flattened_by_id)
        self.assertIn("u2", flattened_by_id)
        
        # subordinatesキーが削除されていることを確認
        for item in flattened:
            self.assertEqual(item.get("subordinates", []), [])
    
    def test_flatten_preserves_other_fields(self):
        """平坦化時にその他のフィールドが保持されることを確認"""
        nested_data = {
            "id": "root",
            "name": "Root",
            "description": "Root description",
            "metadata": {
                "created": "2024-01-01",
                "type": "folder"
            },
            "tags": ["important", "root"],
            "children": [
                {
                    "id": "child1",
                    "name": "Child 1",
                    "description": "Child description",
                    "metadata": {
                        "created": "2024-01-02",
                        "type": "file"
                    },
                    "tags": ["child"],
                    "children": []
                }
            ]
        }
        
        flattened = self.flatten_manager.flatten_nested_json(nested_data)
        
        self.assertEqual(len(flattened), 2)
        
        # ルートノードの検証
        root_node = next(item for item in flattened if item["id"] == "root")
        self.assertEqual(root_node["name"], "Root")
        self.assertEqual(root_node["description"], "Root description")
        self.assertEqual(root_node["metadata"]["created"], "2024-01-01")
        self.assertEqual(root_node["metadata"]["type"], "folder")
        self.assertEqual(root_node["tags"], ["important", "root"])
        
        # 子ノードの検証
        child_node = next(item for item in flattened if item["id"] == "child1")
        self.assertEqual(child_node["name"], "Child 1")
        self.assertEqual(child_node["description"], "Child description")
        self.assertEqual(child_node["metadata"]["created"], "2024-01-02")
        self.assertEqual(child_node["metadata"]["type"], "file")
        self.assertEqual(child_node["tags"], ["child"])
    
    def test_flatten_empty_structure(self):
        """空の構造の平坦化テスト"""
        # 空の辞書
        empty_dict = {}
        flattened_dict = self.flatten_manager.flatten_nested_json(empty_dict)
        self.assertEqual(flattened_dict, [])
        
        # 空のリスト
        empty_list = []
        flattened_list = self.flatten_manager.flatten_nested_json(empty_list)
        self.assertEqual(flattened_list, [])
    
    def test_flatten_no_children(self):
        """子ノードがない構造の平坦化テスト"""
        single_node = {
            "id": "single",
            "name": "Single Node",
            "value": 42
        }
        
        flattened = self.flatten_manager.flatten_nested_json(single_node)
        
        self.assertEqual(len(flattened), 1)
        self.assertEqual(flattened[0]["id"], "single")
        self.assertEqual(flattened[0]["name"], "Single Node")
        self.assertEqual(flattened[0]["value"], 42)
        self.assertEqual(flattened[0].get("children", []), [])
    
    def test_flatten_deep_nesting(self):
        """深いネスト構造の平坦化テスト"""
        deep_nested = {
            "id": "level0",
            "children": [
                {
                    "id": "level1",
                    "children": [
                        {
                            "id": "level2",
                            "children": [
                                {
                                    "id": "level3",
                                    "children": [
                                        {
                                            "id": "level4",
                                            "children": []
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        flattened = self.flatten_manager.flatten_nested_json(deep_nested)
        
        self.assertEqual(len(flattened), 5)  # level0 to level4
        
        expected_ids = ["level0", "level1", "level2", "level3", "level4"]
        flattened_ids = [item["id"] for item in flattened]
        
        for expected_id in expected_ids:
            self.assertIn(expected_id, flattened_ids)


if __name__ == '__main__':
    unittest.main()