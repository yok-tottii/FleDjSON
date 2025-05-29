"""
test_ui_manager.py
UIManagerクラスのテストを行うモジュール
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
        
        def get_control(self, id):
            return None
            
    class Colors:
        ERROR = "#FF0000"
        GREEN_700 = "#00FF00"
        GREEN_ACCENT_700 = "#00FF00"
        PRIMARY = "#2196F3"
        ON_SURFACE_VARIANT = "#757575"
        
        @staticmethod
        def with_opacity(opacity, color):
            return color
        
    class SnackBar:
        def __init__(self, content=None, bgcolor=None, open=False, action=None, duration=None):
            self.content = content
            self.bgcolor = bgcolor
            self.open = open
            self.action = action
            self.duration = duration
            
    class Text:
        def __init__(self, value, size=None, color=None, weight=None):
            self.value = value
            self.size = size
            self.color = color
            self.weight = weight
        
        def update(self):
            pass
            
    class Container:
        def __init__(self, content=None, width=None, height=None, padding=None, bgcolor=None, 
                     border_radius=None, data=None, on_click=None, ink=None):
            self.content = content
            self.width = width
            self.height = height
            self.padding = padding
            self.bgcolor = bgcolor
            self.border_radius = border_radius
            self.data = data
            self.on_click = on_click
            self.ink = ink
            self.visible = True
            self.controls = []
            
        def update(self):
            pass
            
    class Row:
        def __init__(self, controls=None, spacing=None):
            self.controls = controls or []
            self.spacing = spacing
            
    class Column:
        def __init__(self, controls=None, spacing=None):
            self.controls = controls or []
            self.spacing = spacing
            
    class Icon:
        def __init__(self, name=None, size=None, color=None):
            self.name = name
            self.size = size
            self.color = color
            
    class FontWeight:
        BOLD = "bold"
        NORMAL = "normal"
        
    class Draggable:
        def __init__(self, group=None, content=None, data=None, disabled=False, visible=True):
            self.group = group
            self.content = content
            self.data = data
            self.disabled = disabled
            self.visible = visible
            
    class DragTarget:
        def __init__(self, group=None, content=None, data=None, on_accept=None, 
                     on_will_accept=None, on_leave=None):
            self.group = group
            self.content = content
            self.data = data
            self.on_accept = on_accept
            self.on_will_accept = on_will_accept
            self.on_leave = on_leave
            
    class Icons:
        FOLDER_OPEN = "folder_open"
        ARTICLE_OUTLINED = "article_outlined"

# mockモジュールとして設定
import sys
sys.modules['flet'] = MockFlet
import flet as ft

# UIマネージャーのインポート
from src.managers.ui_manager import UIManager


class TestUIManager(unittest.TestCase):
    """UIManagerクラスのテストケース"""
    
    def setUp(self):
        """各テスト前の準備"""
        # テスト用の一時ディレクトリ
        self.temp_dir = tempfile.mkdtemp()
        
        # モックの状態と制御
        self.app_state: Dict[str, Any] = {
            "page": ft.Page(),
            "raw_data": [],
            "data_map": {},
            "children_map": {},
            "root_ids": [],
            "selected_node_id": None,
            "tree_drag_locked": True,
            "analysis_results": {
                "heuristic_suggestions": {
                    "identifier": "id",
                    "children_link": "children",
                    "label": "name"
                },
                "field_details": []
            }
        }
        
        self.ui_controls = {
            "tree_view": ft.Column(),
            "detail_form_column": ft.Column(),
            "detail_save_button": ft.Container(),
            "detail_cancel_button": ft.Container(),
            "detail_delete_button": ft.Container(),
        }
        
        # UIManagerのインスタンス化
        self.ui_manager = UIManager(self.app_state, self.ui_controls)
    
    def tearDown(self):
        """各テスト後のクリーンアップ"""
        shutil.rmtree(self.temp_dir)
    
    def test_get_node_display_label(self):
        """get_node_display_label メソッドのテスト"""
        # テストケース1: ラベルキーが存在する場合
        node_data = {"id": "1", "name": "Test Node", "value": 100}
        
        # ラベルキーが設定され、そのキーが存在する場合
        self.app_state["label_key"] = "name"
        self.app_state["id_key"] = "id"
        label = self.ui_manager.get_node_display_label("1", node_data)
        self.assertEqual(label, "1: Test Node")
        
        # テストケース2: ラベルキーが存在しない場合のフォールバック
        self.app_state["label_key"] = "title"  # 存在しないキー
        label = self.ui_manager.get_node_display_label("1", node_data)
        self.assertTrue(label.startswith("value:") or label.startswith("name:"))
        
        # テストケース3: ラベルが生成できない場合のデフォルト
        node_data = {"id": "1", "_private": "hidden"}
        label = self.ui_manager.get_node_display_label("1", node_data)
        self.assertEqual(label, "Object (1)")
    
    def test_update_node_style_recursive(self):
        """update_node_style_recursive メソッドのテスト"""
        # ノードの生成
        node_id = "1"
        self.app_state["data_map"] = {
            "1": {"id": "1", "name": "Test Node"}
        }
        
        # テスト用のツリーコントロールを作成
        node_text = ft.Text("Test Node")
        node_container = ft.Container(
            content=ft.Row([
                ft.Container(width=20),
                ft.Icon(ft.Icons.ARTICLE_OUTLINED),
                node_text
            ]),
            data="1"
        )
        
        tree_view = ft.Column(controls=[node_container])
        
        # 選択状態に更新
        self.ui_manager.update_node_style_recursive([node_container], node_id, True)
        
        # アサーション - 背景色が設定されるはず
        self.assertEqual(node_container.bgcolor, ft.Colors.PRIMARY)
    
    def test_clear_detail_form(self):
        """clear_detail_form メソッドのテスト"""
        # 詳細フォームにダミーコントロールを設定
        self.ui_controls["detail_form_column"].controls = [
            ft.Text("Detail content")
        ]
        
        # 詳細フォームをクリア
        self.ui_manager.clear_detail_form()
        
        # アサーション
        self.assertEqual(len(self.ui_controls["detail_form_column"].controls), 1)
        self.assertEqual(self.ui_controls["detail_form_column"].controls[0].value, "ノードを選択してください")
        self.assertFalse(self.ui_controls["detail_save_button"].visible)
        self.assertFalse(self.ui_controls["detail_cancel_button"].visible)
        self.assertFalse(self.ui_controls["detail_delete_button"].visible)
    
    def test_build_list_tiles(self):
        """build_list_tiles メソッドのテスト"""
        # テスト用のデータ
        self.app_state["data_map"] = {
            "1": {"id": "1", "name": "Parent Node"},
            "2": {"id": "2", "name": "Child Node 1"},
            "3": {"id": "3", "name": "Child Node 2"}
        }
        self.app_state["children_map"] = {
            "1": ["2", "3"]
        }
        self.app_state["id_key"] = "id"
        self.app_state["label_key"] = "name"
        
        # リストタイルを構築
        tiles = self.ui_manager.build_list_tiles(["1"], depth=0)
        
        # アサーション - 親ノード、子ノード2つ、ドロップターゲットを含めて期待される数のコントロール
        # 親: 1ノード + 1ドロップターゲット = 2
        # 子: 2ノード + 2ドロップターゲット = 4
        # 最後のドロップターゲット: 1
        # 合計: 7
        self.assertEqual(len(tiles), 7)
        
        # テストケース2: ロックが解除されている場合
        self.app_state["tree_drag_locked"] = False
        tiles = self.ui_manager.build_list_tiles(["1"], depth=0)
        
        # ドラッグ可能な状態ではDraggableで包まれるため、構造が変わる
        self.assertEqual(len(tiles), 7)
        
        # 最初のコントロールがドロップターゲットであることを確認
        self.assertIsInstance(tiles[0], ft.DragTarget)
        
        # 2番目のコントロールがドラッグ可能なアイテムであることを確認
        self.assertIsInstance(tiles[1], ft.Draggable)
        
        # ドラッグ可能なアイテムの内容がドロップターゲットであることを確認
        self.assertIsInstance(tiles[1].content, ft.DragTarget)


if __name__ == "__main__":
    unittest.main()