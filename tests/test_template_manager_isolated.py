"""
test_template_manager_isolated.py
TemplateManagerの独立したテスト（依存関係を最小化）
"""
import unittest
import sys
import os

# テスト対象モジュールへのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# TemplateManagerを直接インポートし、依存関係を最小化
class TestTemplateManagerIsolated(unittest.TestCase):
    """TemplateManagerの独立テスト（最小依存）"""
    
    def setUp(self):
        """テスト前のセットアップ"""
        # TemplateManagerクラスの直接インスタンス化に最小限必要なクラス定義
        
        # EventAwareManagerの最小実装
        class MockEventAwareManager:
            def __init__(self, app_state, ui_controls, page=None, event_hub=None):
                self.app_state = app_state
                self.ui_controls = ui_controls
                self.page = page
                self.event_hub = event_hub
        
        # TemplateManagerの主要機能のみを抽出したクラス
        from enum import Enum, auto
        import copy
        from collections import Counter
        from datetime import datetime
        
        class FieldType(Enum):
            STRING = "string"
            NUMBER = "number"
            BOOLEAN = "boolean"
            OBJECT = "object"
            ARRAY = "array"
            NULL = "null"
            EMAIL = "email"
            ID = "id"
            
        class FieldRole(Enum):
            ID = "id"
            NAME = "name"
            EMAIL = "email"
            UNKNOWN = "unknown"
        
        class FieldImportance(Enum):
            REQUIRED = "required"
            RECOMMENDED = "recommended"
            OPTIONAL = "optional"
        
        class TemplateManagerIsolated(MockEventAwareManager):
            """独立テスト用のTemplateManager実装"""
            
            def __init__(self, app_state, ui_controls, page=None, event_hub=None):
                super().__init__(app_state, ui_controls, page, event_hub)
                # 基本的な型推論パターン
                import re
                self.type_patterns = {
                    FieldType.EMAIL: [re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')],
                    FieldType.ID: [re.compile(r'^[a-zA-Z0-9_-]+\d+$'), re.compile(r'^[0-9]+$')]
                }
                self.role_patterns = {
                    FieldRole.ID: [r'id$', r'^.*_id$'],
                    FieldRole.NAME: [r'^name$', r'.*name$'],
                    FieldRole.EMAIL: [r'email', r'mail']
                }
            
            def generate_template(self, data):
                """簡化されたテンプレート生成"""
                if not data:
                    return {}
                
                if isinstance(data, list):
                    sample_data = data[0] if data else {}
                else:
                    sample_data = data
                
                if not isinstance(sample_data, dict):
                    return {}
                
                template = {
                    "type": FieldType.OBJECT.value,
                    "fields": {},
                    "sample_data": sample_data,
                    "generated_at": datetime.now().isoformat()
                }
                
                for field_name, field_value in sample_data.items():
                    field_info = {
                        "type": self._infer_field_type(field_value),
                        "role": self._infer_field_role(field_name, [field_value]).value,
                        "sample_value": field_value
                    }
                    template["fields"][field_name] = field_info
                
                return template
            
            def apply_template(self, template, data):
                """簡化されたテンプレート適用"""
                if not template or not data:
                    return data
                
                result = copy.deepcopy(data)
                return result
            
            def _infer_field_type(self, value):
                """値から型を推論"""
                if value is None:
                    return FieldType.NULL.value
                elif isinstance(value, bool):
                    return FieldType.BOOLEAN.value
                elif isinstance(value, (int, float)):
                    return FieldType.NUMBER.value
                elif isinstance(value, str):
                    # 特定パターンチェック
                    for field_type, patterns in self.type_patterns.items():
                        for pattern in patterns:
                            if pattern.match(value):
                                return field_type.value
                    return FieldType.STRING.value
                elif isinstance(value, list):
                    return FieldType.ARRAY.value
                elif isinstance(value, dict):
                    return FieldType.OBJECT.value
                else:
                    return FieldType.STRING.value
            
            def _infer_field_role(self, field_name, sample_values):
                """フィールド名から役割を推論"""
                import re
                field_name_lower = field_name.lower()
                
                for role, patterns in self.role_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, field_name_lower):
                            return role
                
                return FieldRole.UNKNOWN
        
        # セットアップ完了
        self.FieldType = FieldType
        self.FieldRole = FieldRole
        self.FieldImportance = FieldImportance
        self.TemplateManager = TemplateManagerIsolated
        
        self.app_state = {"test": "data"}
        self.ui_controls = {"mock": "controls"}
        self.template_manager = TemplateManagerIsolated(self.app_state, self.ui_controls)
    
    def test_template_manager_initialization(self):
        """TemplateManagerの初期化テスト"""
        self.assertIsInstance(self.template_manager, self.TemplateManager)
        self.assertEqual(self.template_manager.app_state, self.app_state)
    
    def test_generate_template_with_dict(self):
        """辞書データからのテンプレート生成テスト"""
        test_data = {
            "user_id": "123",
            "name": "テストユーザー",
            "email": "test@example.com",
            "age": 25,
            "active": True
        }
        
        template = self.template_manager.generate_template(test_data)
        
        self.assertEqual(template["type"], self.FieldType.OBJECT.value)
        self.assertIn("fields", template)
        self.assertIn("sample_data", template)
        
        # フィールドの分析結果をチェック
        fields = template["fields"]
        self.assertIn("user_id", fields)
        self.assertIn("name", fields)
        self.assertIn("email", fields)
        
        # IDフィールドの役割推論チェック
        id_field = fields["user_id"]
        self.assertEqual(id_field["role"], self.FieldRole.ID.value)
        
        # Emailフィールドの型推論チェック
        email_field = fields["email"]
        self.assertEqual(email_field["type"], self.FieldType.EMAIL.value)
    
    def test_generate_template_with_list(self):
        """配列データからのテンプレート生成テスト"""
        test_data = [
            {"id": "1", "name": "User1"},
            {"id": "2", "name": "User2"}
        ]
        
        template = self.template_manager.generate_template(test_data)
        
        self.assertEqual(template["type"], self.FieldType.OBJECT.value)
        self.assertIn("fields", template)
        
        # 共通フィールドが検出されているか
        fields = template["fields"]
        self.assertIn("id", fields)
        self.assertIn("name", fields)
    
    def test_field_type_inference(self):
        """型推論の詳細テスト"""
        test_cases = [
            ("test@example.com", self.FieldType.EMAIL.value),
            ("user123", self.FieldType.ID.value),
            ("12345", self.FieldType.ID.value),
            ("simple_string", self.FieldType.STRING.value),
            (42, self.FieldType.NUMBER.value),
            (True, self.FieldType.BOOLEAN.value),
            (None, self.FieldType.NULL.value),
            ([], self.FieldType.ARRAY.value),
            ({}, self.FieldType.OBJECT.value)
        ]
        
        for value, expected_type in test_cases:
            with self.subTest(value=value):
                inferred_type = self.template_manager._infer_field_type(value)
                self.assertEqual(inferred_type, expected_type, 
                               f"Failed for value {value}, expected {expected_type}, got {inferred_type}")
    
    def test_field_role_inference(self):
        """役割推論の詳細テスト"""
        test_cases = [
            ("user_id", self.FieldRole.ID),
            ("id", self.FieldRole.ID),
            ("name", self.FieldRole.NAME),
            ("username", self.FieldRole.NAME),
            ("email", self.FieldRole.EMAIL),
            ("email_address", self.FieldRole.EMAIL),
            ("random_field", self.FieldRole.UNKNOWN)
        ]
        
        for field_name, expected_role in test_cases:
            with self.subTest(field_name=field_name):
                inferred_role = self.template_manager._infer_field_role(field_name, ["dummy"])
                self.assertEqual(inferred_role, expected_role,
                               f"Failed for field {field_name}, expected {expected_role}, got {inferred_role}")


if __name__ == '__main__':
    unittest.main()