#!/usr/bin/env python3
"""
CopyManagerの分離テスト
Fletの依存関係を最小限に抑えた単体テスト
"""

import unittest
from unittest.mock import Mock
import sys
import os

# テスト対象のモジュールをインポート
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from managers.copy_manager import CopyManager


class TestCopyManagerIsolated(unittest.TestCase):
    """CopyManagerの分離テスト"""
    
    def setUp(self):
        """テストの準備"""
        self.app_state = {
            "data_map": {
                "1": {"id": "1", "name": "Test 1", "tags": ["tag1", "tag2"]},
                "2": {"id": "2", "name": "Test 2", "nested": {"value": 42}},
                "3": {"id": "3", "name": "Test 3", "items": [{"type": "A"}, {"type": "B"}]}
            },
            "children_map": {
                "1": ["2"],
                "2": ["3"]
            },
            "root_ids": ["1"]
        }
        
        self.ui_controls = {}
        
        # CopyManagerのインスタンスを作成
        self.copy_manager = CopyManager(
            app_state=self.app_state,
            ui_controls=self.ui_controls,
            page=None,
            event_hub=None
        )
    
    def test_copy_manager_initialization(self):
        """CopyManagerの初期化テスト"""
        self.assertIsNotNone(self.copy_manager)
        self.assertEqual(self.copy_manager.app_state, self.app_state)
        self.assertEqual(self.copy_manager.ui_controls, self.ui_controls)
    
    def test_deep_copy_simple_data(self):
        """単純なデータの深いコピーテスト"""
        original_data = {"id": "test", "name": "Original", "value": 123}
        copied_data = self.copy_manager.deep_copy(original_data)
        
        self.assertEqual(copied_data, original_data)
        self.assertIsNot(copied_data, original_data)  # 異なるオブジェクトであることを確認
        
        # オリジナルを変更してもコピーに影響しないことを確認
        original_data["name"] = "Modified"
        self.assertEqual(copied_data["name"], "Original")
    
    def test_deep_copy_nested_data(self):
        """ネストしたデータの深いコピーテスト"""
        original_data = {
            "id": "test",
            "metadata": {
                "created": "2024-01-01",
                "tags": ["tag1", "tag2"]
            },
            "items": [
                {"type": "A", "value": 1},
                {"type": "B", "value": 2}
            ]
        }
        
        copied_data = self.copy_manager.deep_copy(original_data)
        
        self.assertEqual(copied_data, original_data)
        self.assertIsNot(copied_data, original_data)
        self.assertIsNot(copied_data["metadata"], original_data["metadata"])
        self.assertIsNot(copied_data["metadata"]["tags"], original_data["metadata"]["tags"])
        self.assertIsNot(copied_data["items"], original_data["items"])
        self.assertIsNot(copied_data["items"][0], original_data["items"][0])
        
        # ネストした要素を変更してもオリジナルに影響しないことを確認
        copied_data["metadata"]["tags"].append("tag3")
        self.assertEqual(len(original_data["metadata"]["tags"]), 2)
        
        copied_data["items"][0]["value"] = 999
        self.assertEqual(original_data["items"][0]["value"], 1)
    
    def test_deep_copy_list_data(self):
        """リストデータの深いコピーテスト"""
        original_list = [
            {"id": "1", "values": [1, 2, 3]},
            {"id": "2", "nested": {"key": "value"}},
            "simple_string",
            42
        ]
        
        copied_list = self.copy_manager.deep_copy(original_list)
        
        self.assertEqual(copied_list, original_list)
        self.assertIsNot(copied_list, original_list)
        self.assertIsNot(copied_list[0], original_list[0])
        self.assertIsNot(copied_list[0]["values"], original_list[0]["values"])
        self.assertIsNot(copied_list[1]["nested"], original_list[1]["nested"])
        
        # 配列要素を変更してもオリジナルに影響しないことを確認
        copied_list[0]["values"].append(4)
        self.assertEqual(len(original_list[0]["values"]), 3)
    
    def test_deep_copy_with_none_values(self):
        """None値を含むデータの深いコピーテスト"""
        original_data = {
            "id": "test",
            "nullable_field": None,
            "optional_data": {
                "value": None,
                "items": [None, "valid", None]
            }
        }
        
        copied_data = self.copy_manager.deep_copy(original_data)
        
        self.assertEqual(copied_data, original_data)
        self.assertIsNot(copied_data, original_data)
        self.assertIsNot(copied_data["optional_data"], original_data["optional_data"])
        self.assertIsNot(copied_data["optional_data"]["items"], original_data["optional_data"]["items"])
        
        # None値が正しくコピーされることを確認
        self.assertIsNone(copied_data["nullable_field"])
        self.assertIsNone(copied_data["optional_data"]["value"])
        self.assertIsNone(copied_data["optional_data"]["items"][0])
        self.assertIsNone(copied_data["optional_data"]["items"][2])
    
    def test_deep_copy_edge_cases(self):
        """エッジケースの深いコピーテスト"""
        # 空のデータ構造
        self.assertEqual(self.copy_manager.deep_copy({}), {})
        self.assertEqual(self.copy_manager.deep_copy([]), [])
        
        # 単純な値
        self.assertEqual(self.copy_manager.deep_copy("string"), "string")
        self.assertEqual(self.copy_manager.deep_copy(123), 123)
        self.assertEqual(self.copy_manager.deep_copy(True), True)
        self.assertEqual(self.copy_manager.deep_copy(None), None)
        
        # 複雑な構造
        complex_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "array": [1, 2, {"deep": "value"}]
                    }
                }
            }
        }
        
        copied_complex = self.copy_manager.deep_copy(complex_data)
        self.assertEqual(copied_complex, complex_data)
        self.assertIsNot(copied_complex["level1"]["level2"]["level3"]["array"][2], 
                        complex_data["level1"]["level2"]["level3"]["array"][2])


if __name__ == '__main__':
    unittest.main()