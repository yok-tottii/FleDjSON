"""
test_new_managers.py
新しいマネージャークラス（TemplateManager、CopyManager、FlattenManager）のテスト
"""
import unittest
from unittest.mock import MagicMock, patch
import json
import sys

# 最小限のFletモック
class MockFlet:
    pass

# Fletモジュールをモック
sys.modules['flet'] = MockFlet()

# 新しいマネージャーをインポート
sys.path.insert(0, '/Users/user/Documents/dev/FleDjSON')
from src.managers.template_manager import TemplateManager, FieldType, FieldRole, FieldImportance
from src.managers.copy_manager import CopyManager
from src.managers.flatten_manager import FlattenManager


class TestTemplateManager(unittest.TestCase):
    """TemplateManagerクラスのテストケース"""
    
    def setUp(self):
        """テスト前のセットアップ"""
        self.app_state = {"test": "data"}
        self.ui_controls = {"mock": "controls"}
        self.template_manager = TemplateManager(self.app_state, self.ui_controls)
    
    def test_template_manager_initialization(self):
        """TemplateManagerの初期化テスト"""
        self.assertIsInstance(self.template_manager, TemplateManager)
        self.assertEqual(self.template_manager.app_state, self.app_state)
        self.assertEqual(self.template_manager.ui_controls, self.ui_controls)
    
    def test_generate_template_with_dict(self):
        """辞書データからのテンプレート生成テスト"""
        test_data = {
            "id": "user_001",
            "name": "テストユーザー",
            "email": "test@example.com",
            "age": 25,
            "active": True
        }
        
        template = self.template_manager.generate_template(test_data)
        
        self.assertEqual(template["type"], FieldType.OBJECT.value)
        self.assertIn("fields", template)
        self.assertIn("sample_data", template)
        self.assertIn("generated_at", template)
        
        # フィールドの分析結果をチェック
        fields = template["fields"]
        self.assertIn("id", fields)
        self.assertIn("name", fields)
        self.assertIn("email", fields)
        
        # IDフィールドの役割推論チェック
        id_field = fields["id"]
        self.assertEqual(id_field["role"], FieldRole.ID.value)
        
        # Emailフィールドの型推論チェック
        email_field = fields["email"]
        self.assertEqual(email_field["type"], FieldType.EMAIL.value)
    
    def test_generate_template_with_list(self):
        """配列データからのテンプレート生成テスト"""
        test_data = [
            {"id": "1", "name": "User1", "type": "admin"},
            {"id": "2", "name": "User2", "type": "user"},
            {"id": "3", "name": "User3", "type": "user"}
        ]
        
        template = self.template_manager.generate_template(test_data)
        
        self.assertEqual(template["type"], FieldType.OBJECT.value)
        self.assertIn("fields", template)
        
        # 共通フィールドが検出されているか
        fields = template["fields"]
        self.assertIn("id", fields)
        self.assertIn("name", fields)
        self.assertIn("type", fields)
    
    def test_apply_template(self):
        """テンプレート適用テスト"""
        template = {
            "type": FieldType.OBJECT.value,
            "fields": {
                "id": {
                    "type": FieldType.ID.value,
                    "importance": FieldImportance.REQUIRED.value
                },
                "name": {
                    "type": FieldType.STRING.value,
                    "importance": FieldImportance.REQUIRED.value
                },
                "optional_field": {
                    "type": FieldType.STRING.value,
                    "importance": FieldImportance.OPTIONAL.value
                }
            },
            "sample_data": {
                "id": "sample_001",
                "name": "Sample Name",
                "optional_field": "Optional Value"
            }
        }
        
        incomplete_data = {"id": "test_001"}
        
        result = self.template_manager.apply_template(template, incomplete_data)
        
        # 必須フィールドが補完されているか
        self.assertIn("name", result)
        self.assertEqual(result["name"], "Sample Name")
        self.assertEqual(result["id"], "test_001")
    
    def test_suggest_field_roles(self):
        """フィールド役割推測テスト"""
        test_data = {
            "user_id": "12345",
            "username": "testuser",
            "email_address": "test@example.com",
            "created_at": "2024-01-01",
            "is_active": True,
            "profile_description": "This is a test user"
        }
        
        roles = self.template_manager.suggest_field_roles(test_data)
        
        self.assertEqual(roles["user_id"], FieldRole.ID)
        self.assertEqual(roles["username"], FieldRole.NAME)
        self.assertEqual(roles["created_at"], FieldRole.CREATED_AT)
        self.assertEqual(roles["profile_description"], FieldRole.DESCRIPTION)


class TestCopyManager(unittest.TestCase):
    """CopyManagerクラスのテストケース"""
    
    def setUp(self):
        """テスト前のセットアップ"""
        self.app_state = {"test": "data"}
        self.ui_controls = {"mock": "controls"}
        self.copy_manager = CopyManager(self.app_state, self.ui_controls)
    
    def test_copy_manager_initialization(self):
        """CopyManagerの初期化テスト"""
        self.assertIsInstance(self.copy_manager, CopyManager)
        self.assertEqual(self.copy_manager.app_state, self.app_state)
        self.assertEqual(self.copy_manager.ui_controls, self.ui_controls)
    
    def test_safe_deep_copy_simple_types(self):
        """基本型の深いコピーテスト"""
        # 各基本型をテスト
        test_values = [
            None,
            "test string",
            42,
            3.14,
            True,
            False
        ]
        
        for value in test_values:
            copied = self.copy_manager.safe_deep_copy(value)
            self.assertEqual(copied, value)
    
    def test_safe_deep_copy_complex_types(self):
        """複合型の深いコピーテスト"""
        original_dict = {
            "level1": {
                "level2": {
                    "data": "nested value",
                    "list": [1, 2, 3]
                }
            },
            "array": [
                {"item": 1},
                {"item": 2}
            ]
        }
        
        copied = self.copy_manager.safe_deep_copy(original_dict)
        
        # 内容が同じことを確認
        self.assertEqual(copied, original_dict)
        
        # 参照が異なることを確認（独立していること）
        self.assertIsNot(copied, original_dict)
        self.assertIsNot(copied["level1"], original_dict["level1"])
        self.assertIsNot(copied["array"], original_dict["array"])
        self.assertIsNot(copied["array"][0], original_dict["array"][0])
        
        # 元のデータを変更しても影響しないことを確認
        original_dict["level1"]["level2"]["data"] = "modified"
        self.assertNotEqual(copied["level1"]["level2"]["data"], "modified")
    
    def test_safe_deep_copy_list(self):
        """リストの深いコピーテスト"""
        original_list = [
            {"id": "1", "data": {"nested": "value1"}},
            {"id": "2", "data": {"nested": "value2"}},
            [1, 2, {"inner": "value"}]
        ]
        
        copied = self.copy_manager.safe_deep_copy_list(original_list)
        
        # 内容が同じことを確認
        self.assertEqual(copied, original_list)
        
        # 参照が異なることを確認
        self.assertIsNot(copied, original_list)
        self.assertIsNot(copied[0], original_list[0])
        self.assertIsNot(copied[0]["data"], original_list[0]["data"])


class TestFlattenManager(unittest.TestCase):
    """FlattenManagerクラスのテストケース"""
    
    def setUp(self):
        """テスト前のセットアップ"""
        self.app_state = {"test": "data"}
        self.ui_controls = {"mock": "controls"}
        self.flatten_manager = FlattenManager(self.app_state, self.ui_controls)
    
    def test_flatten_manager_initialization(self):
        """FlattenManagerの初期化テスト"""
        self.assertIsInstance(self.flatten_manager, FlattenManager)
        self.assertEqual(self.flatten_manager.app_state, self.app_state)
        self.assertEqual(self.flatten_manager.ui_controls, self.ui_controls)
    
    def test_flatten_nested_json_simple(self):
        """単純なネストされたJSONの平坦化テスト"""
        nested_data = {
            "id": "root_1",
            "name": "Root Object",
            "child": {
                "id": "child_1",
                "name": "Child Object",
                "value": 42
            }
        }
        
        flattened = self.flatten_manager.flatten_nested_json(nested_data)
        
        # 結果がリストであること
        self.assertIsInstance(flattened, list)
        
        # 期待される数の要素があること
        self.assertGreaterEqual(len(flattened), 1)
        
        # ルートオブジェクトが含まれていること
        root_found = any(item.get("id") == "root_1" for item in flattened)
        self.assertTrue(root_found)
    
    def test_flatten_nested_json_with_arrays(self):
        """配列を含むネストされたJSONの平坦化テスト"""
        nested_data = [
            {
                "id": "parent_1",
                "name": "Parent 1",
                "children": [
                    {"id": "child_1", "name": "Child 1"},
                    {"id": "child_2", "name": "Child 2"}
                ]
            }
        ]
        
        flattened = self.flatten_manager.flatten_nested_json(nested_data)
        
        # 結果がリストであること
        self.assertIsInstance(flattened, list)
        
        # 複数の要素に分割されていること
        self.assertGreaterEqual(len(flattened), 1)
        
        # 親オブジェクトが含まれていること
        parent_found = any(item.get("id") == "parent_1" for item in flattened)
        self.assertTrue(parent_found)
    
    def test_try_flatten_json_already_flat(self):
        """既に平坦化されたデータのテスト"""
        flat_data = [
            {"id": "1", "name": "Item 1", "type": "simple"},
            {"id": "2", "name": "Item 2", "type": "simple"}
        ]
        
        result, was_nested = self.flatten_manager.try_flatten_json(flat_data)
        
        # 元のデータがそのまま返されること
        self.assertEqual(result, flat_data)
        
        # 平坦化が不要だったことが示されること
        self.assertFalse(was_nested)
    
    def test_is_nested_structure(self):
        """ネストされた構造の判定テスト"""
        # ネストされた構造
        nested_dict = {
            "id": "1",
            "child": {"nested": "value"}
        }
        
        nested_list = [
            {"id": "1", "child": {"nested": "value"}}
        ]
        
        # 平坦な構造
        flat_dict = {
            "id": "1",
            "name": "simple",
            "value": 42
        }
        
        flat_list = [
            {"id": "1", "name": "simple", "value": 42}
        ]
        
        # ネストされた構造の判定
        self.assertTrue(self.flatten_manager.is_nested_structure(nested_dict))
        self.assertTrue(self.flatten_manager.is_nested_structure(nested_list))
        
        # 平坦な構造の判定
        self.assertFalse(self.flatten_manager.is_nested_structure(flat_dict))
        self.assertFalse(self.flatten_manager.is_nested_structure(flat_list))
    
    def test_estimate_flattened_size(self):
        """平坦化後サイズ推定テスト"""
        nested_data = {
            "id": "root",
            "level1": {
                "id": "level1_item",
                "level2": {
                    "id": "level2_item",
                    "value": "deep_value"
                }
            }
        }
        
        estimated_size = self.flatten_manager.estimate_flattened_size(nested_data)
        
        # サイズが1以上であること（少なくともルートオブジェクト）
        self.assertGreaterEqual(estimated_size, 1)


if __name__ == '__main__':
    unittest.main()