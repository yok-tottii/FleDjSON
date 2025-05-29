"""
test_data_manager.py
DataManagerクラスのテストを行うモジュール
"""
import unittest
import json
import os
import tempfile
import shutil
from typing import Dict, Any

# ここでは仮想的なFlet実装をモックしておく
class MockFlet:
    class Page:
        def __init__(self):
            self.controls = []
            self.snack_bar = None
            self.title = ""
            
        def update(self):
            pass
            
    class Colors:
        ERROR = "#FF0000"
        GREEN_700 = "#00FF00"
        GREEN_ACCENT_700 = "#00FF00"
        
    class SnackBar:
        def __init__(self, content=None, bgcolor=None, open=False, action=None, duration=None):
            self.content = content
            self.bgcolor = bgcolor
            self.open = open
            self.action = action
            self.duration = duration
            
    class Text:
        def __init__(self, value):
            self.value = value
            
    class FilePickerResultEvent:
        def __init__(self, files=None, path=None):
            self.files = files or []
            self.path = path

# mockモジュールとして設定
import sys
sys.modules['flet'] = MockFlet
import flet as ft

# データマネージャーのインポート
from src.managers.data_manager import DataManager


class TestDataManager(unittest.TestCase):
    """DataManagerクラスのテストケース"""
    
    def setUp(self):
        """各テスト前の準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.sample_file = os.path.join(self.temp_dir, "test_data.json")
        
        # サンプルJSONデータ
        self.sample_data = [
            {
                "id": "1",
                "name": "Item 1",
                "depth": 0,
                "children": ["2", "3"]
            },
            {
                "id": "2",
                "name": "Item 2",
                "depth": 1,
                "children": []
            },
            {
                "id": "3",
                "name": "Item 3",
                "depth": 1,
                "children": ["4"]
            },
            {
                "id": "4",
                "name": "Item 4",
                "depth": 2,
                "children": []
            }
        ]
        
        # サンプルデータをファイルに書き込み
        with open(self.sample_file, 'w', encoding='utf-8') as f:
            json.dump(self.sample_data, f)
        
        # モックの状態と制御
        self.app_state: Dict[str, Any] = {
            "page": ft.Page(),
            "raw_data": [],
            "data_map": {},
            "children_map": {},
            "root_ids": [],
            "selected_node_id": None,
            "edit_buffer": {},
            "is_dirty": False,
            "add_mode": False
        }
        self.ui_controls = {
            "status_bar": MockFlet.SnackBar(content=MockFlet.Text(""))
        }
        
        # 解析結果のモック
        self.mock_analysis_results = {
            "heuristic_suggestions": {
                "identifier": "id",
                "children_link": "children",
                "label": "name"
            },
            "field_details": [
                {
                    "name": "id",
                    "types": [("string", 4)],
                    "is_unique": True
                },
                {
                    "name": "name",
                    "types": [("string", 4)],
                    "is_unique": True
                },
                {
                    "name": "depth",
                    "types": [("int", 4)],
                    "is_unique": False
                },
                {
                    "name": "children",
                    "types": [("list[string]", 4)],
                    "is_unique": False
                }
            ]
        }
        
        # DataManagerのインスタンス化
        self.data_manager = DataManager(self.app_state, self.ui_controls)
    
    def tearDown(self):
        """各テスト後のクリーンアップ"""
        shutil.rmtree(self.temp_dir)
    
    def test_load_json_file(self):
        """load_json_file メソッドのテスト"""
        # AnalysisManagerのモック
        class MockAnalysisManager:
            def analyze_json_structure(self, **kwargs):
                return self.mock_analysis_results
        
        self.app_state["analysis_manager"] = MockAnalysisManager()
        self.app_state["analysis_manager"].mock_analysis_results = self.mock_analysis_results
        
        # ファイル読み込みを実行
        result = self.data_manager.load_json_file(self.sample_file)
        
        # アサーション
        self.assertTrue(result)
        self.assertEqual(len(self.app_state["raw_data"]), 4)
        self.assertEqual(len(self.app_state["data_map"]), 4)
        self.assertEqual(len(self.app_state["root_ids"]), 1)
        self.assertEqual(self.app_state["data_map"]["1"]["name"], "Item 1")
    
    def test_get_value_by_path(self):
        """get_value_by_path メソッドのテスト"""
        # テストデータ
        test_data = {
            "a": {
                "b": [
                    {"c": 1},
                    {"c": 2}
                ]
            }
        }
        
        # 基本的なパス
        self.assertEqual(
            self.data_manager.get_value_by_path(test_data, "a.b[0].c"),
            1
        )
        
        # リスト内の別要素
        self.assertEqual(
            self.data_manager.get_value_by_path(test_data, "a.b[1].c"),
            2
        )
        
        # 参照情報を取得
        ref_info = self.data_manager.get_value_by_path(test_data, "a.b[0].c", True)
        self.assertEqual(ref_info["key"], "c")
        self.assertEqual(ref_info["value"], 1)
        self.assertEqual(ref_info["parent"], test_data["a"]["b"][0])
    
    def test_set_value_by_path(self):
        """set_value_by_path メソッドのテスト"""
        # テストデータ
        test_data = {
            "a": {
                "b": [
                    {"c": 1},
                    {"c": 2}
                ]
            }
        }
        
        # 値を設定
        self.data_manager.set_value_by_path(test_data, "a.b[0].c", 100)
        self.assertEqual(test_data["a"]["b"][0]["c"], 100)
        
        # 新しいフィールドを設定
        self.data_manager.set_value_by_path(test_data, "a.b[0].d", "new field")
        self.assertEqual(test_data["a"]["b"][0]["d"], "new field")
        
        # 新しいパスを設定（中間のオブジェクトを自動作成）
        self.data_manager.set_value_by_path(test_data, "a.x.y", "auto-created")
        self.assertEqual(test_data["a"]["x"]["y"], "auto-created")
    
    def test_convert_value_based_on_type(self):
        """convert_value_based_on_type メソッドのテスト"""
        # 整数への変換
        self.assertEqual(
            self.data_manager.convert_value_based_on_type("123", "int", "field"),
            123
        )
        
        # 浮動小数点数への変換
        self.assertEqual(
            self.data_manager.convert_value_based_on_type("123.45", "float", "field"),
            123.45
        )
        
        # 真偽値への変換
        self.assertEqual(
            self.data_manager.convert_value_based_on_type("true", "bool", "field"),
            True
        )
        self.assertEqual(
            self.data_manager.convert_value_based_on_type("false", "bool", "field"),
            False
        )
        
        # 型ヒントなしの自動判定
        self.assertEqual(
            self.data_manager.convert_value_based_on_type("123", None, "field"),
            123
        )
        self.assertEqual(
            self.data_manager.convert_value_based_on_type("true", None, "field"),
            True
        )
        self.assertEqual(
            self.data_manager.convert_value_based_on_type("just a string", None, "field"),
            "just a string"
        )


if __name__ == "__main__":
    unittest.main()