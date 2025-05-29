"""
テスト:フィールド順序保持機能のテスト
"""
import os
import sys
import time
import flet as ft
from pathlib import Path

# プロジェクトルートへのパスを追加
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fledjson.utils import try_parse_json

def main(page: ft.Page):
    page.title = "フィールド順序保持テスト"
    page.theme_mode = "light"
    
    # グローバル状態の初期化
    app_state = {}
    ui_controls = {}
    
    # テスト用の関数
    def test_order_preservation(e=None):
        from fledjson.form_handlers import app_state, ui_controls, _key_input_order, _input_counter
        from fledjson.form_handlers import update_tree_view, update_detail_form, on_form_field_change
        from fledjson.form_handlers import toggle_add_mode, update_add_form, commit_new_node
        from fledjson.data_handlers import set_value_by_path, get_value_by_path
        
        # グローバル変数を設定
        app_state.update({
            "raw_data": [],
            "data_map": {},
            "children_map": {},
            "root_ids": [],
            "edit_buffer": {},
            "id_key": "id",
            "label_key": "name",
            "is_dirty": False,
            "add_mode": False,
            "selected_node_id": None,
            "analysis_results": {
                "heuristic_suggestions": {
                    "identifier": "id",
                    "label": "name",
                    "main_children": "children",
                    "alternative_children": []
                },
                "field_details": [
                    {"name": "id", "types": [("string", 100.0)]},
                    {"name": "name", "types": [("string", 100.0)]},
                    {"name": "profile", "types": [("dict", 100.0)]},
                    {"name": "tags", "types": [("list", 100.0)]},
                    {"name": "contact", "types": [("dict", 100.0)]},
                ]
            }
        })
        
        # UI関連の初期化
        detail_form_column = ft.Column([ft.Text("詳細フォーム")])
        add_form_column = ft.Column([ft.Text("追加フォーム")])
        tree_view = ft.Column([ft.Text("ツリービュー")])
        
        ui_controls.update({
            "tree_view": tree_view,
            "detail_form_column": detail_form_column,
            "add_form_column": add_form_column,
            "detail_save_button": ft.ElevatedButton("保存"),
            "detail_cancel_button": ft.OutlinedButton("キャンセル"),
            "detail_delete_button": ft.OutlinedButton("削除"),
            "add_data_button": ft.ElevatedButton("データ追加"),
            "add_save_button": ft.ElevatedButton("追加"),
            "add_cancel_button": ft.OutlinedButton("キャンセル")
        })
        
        # ページにUIを追加
        page.add(
            ft.Column([
                ft.Text("フィールド入力順序保持テスト", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Row([
                    ft.Column([
                        ft.Text("左ペイン - ツリービュー"),
                        tree_view
                    ], expand=1),
                    ft.VerticalDivider(),
                    ft.Column([
                        ft.Text("右ペイン - 詳細/追加フォーム"),
                        detail_form_column,
                        add_form_column
                    ], expand=1)
                ], expand=True),
                ft.Row([
                    ft.ElevatedButton("データ追加モードに切り替え", on_click=lambda _: toggle_add_mode(_))
                ])
            ])
        )
        
        # 追加モードに切り替え
        toggle_add_mode(ft.ControlEvent(target=None, page=page))
        
        # フォームにサンプルデータを入力する関数
        def simulate_input(e=None):
            # 入力順序: id, name, profile, tags, contact (意図的にIDから始めて階層は後ろにする)
            inputs = [
                ("id", "test_123"),
                ("name", "テスト用データ"),
                ("profile.bio", "これはサンプルのバイオグラフィーです"),
                ("profile.age", "30"),
                ("tags[0]", "タグ1"),
                ("tags[1]", "タグ2"),
                ("contact.email", "test@example.com"),
                ("contact.phone", "123-456-7890")
            ]
            
            # テキストフィールドの作成とイベント発火をシミュレート
            for key_path, value in inputs:
                textfield = ft.TextField(
                    value=value,
                    data={"path": key_path, "type": "string" if "." not in key_path and "[" not in key_path else None}
                )
                
                # フォーム変更イベントをシミュレート
                event = ft.ControlEvent(
                    target=textfield,
                    control=textfield,
                    page=page
                )
                
                # 変更を記録
                on_form_field_change(event)
                
                # 順序を記録するために少し待機（実際のユーザー入力をシミュレート）
                time.sleep(0.1)
            
            # 入力順序の確認
            print("\n===== 入力順序の確認 =====")
            for key in sorted(app_state["edit_buffer"].keys()):
                print(f"Input key: {key} = {app_state['edit_buffer'][key]}")
            
            # バッファ内容を確認
            print("\n===== バッファの内容 =====")
            print(app_state["edit_buffer"])
        
        # シミュレーションを実行
        simulate_input()
        
        # 新規ノードをコミット
        commit_event = ft.ControlEvent(
            target=None,
            page=page
        )
        commit_new_node(commit_event)
        
        # 結果を確認
        print("\n===== コミット後のノードデータ =====")
        node_id = app_state["selected_node_id"]
        node_data = app_state["data_map"].get(node_id, {})
        
        # 項目が正しい順序で保存されているか確認
        import json
        formatted_json = json.dumps(node_data, indent=2, ensure_ascii=False)
        print(formatted_json)
        
        # UIに結果を表示
        result_text = ft.Text(
            f"保存された順序:\n{formatted_json}",
            selectable=True
        )
        
        page.add(
            ft.Container(
                content=ft.Column([
                    ft.Text("テスト結果", size=18, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Text("JSONデータが入力順に従って保存されているか確認してください：", italic=True),
                    ft.Container(
                        content=result_text,
                        padding=10,
                        border=ft.border.all(1, ft.colors.GREY),
                        border_radius=5,
                        bgcolor=ft.colors.BLACK12
                    )
                ]),
                padding=20,
                margin=10,
                border=ft.border.all(1, ft.colors.BLUE),
                border_radius=10
            )
        )
    
    # テストの実行
    page.add(
        ft.ElevatedButton("フィールド順序保持テストを実行", on_click=test_order_preservation)
    )

ft.app(target=main)