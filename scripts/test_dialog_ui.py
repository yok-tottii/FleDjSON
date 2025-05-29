"""
ダイアログUIテストスクリプト

このスクリプトは、UIダイアログと通知機能をインタラクティブにテストします。
Fletの各種UI通知方法（ダイアログ、スナックバー、オーバーレイ）が動作するかを確認します。
"""
import flet as ft
import sys
import os
import json

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# アプリケーションモジュールをインポート
import src.ui_helpers

def main(page: ft.Page):
    page.title = "UI要素テスト"
    page.padding = 20
    
    # 診断情報
    page.add(ft.Text("FleDjSON UI要素診断", size=24, weight=ft.FontWeight.BOLD))
    page.add(ft.Text(f"Flet バージョン: {ft.__version__}"))
    
    # 実行環境情報
    import platform
    page.add(ft.Text(f"OS: {platform.system()} {platform.release()}"))
    page.add(ft.Text(f"Python: {sys.version}"))
    
    # 機能サポート診断
    dialog_support = hasattr(page, 'dialog')
    snackbar_support = hasattr(page, 'snack_bar')
    overlay_support = hasattr(page, 'overlay')
    
    # サポート状況を表示
    support_info = ft.Column([
        ft.Text("機能サポート状況:", weight=ft.FontWeight.BOLD),
        ft.Text(f"ダイアログ (page.dialog): {dialog_support}", 
                color=ft.colors.GREEN if dialog_support else ft.colors.RED),
        ft.Text(f"スナックバー (page.snack_bar): {snackbar_support}", 
                color=ft.colors.GREEN if snackbar_support else ft.colors.RED),
        ft.Text(f"オーバーレイ (page.overlay): {overlay_support}", 
                color=ft.colors.GREEN if overlay_support else ft.colors.RED),
    ])
    page.add(support_info)
    page.add(ft.Divider())
    
    # -------------------------------
    # テスト用UI要素
    # -------------------------------
    test_section = ft.Column([
        ft.Text("UI要素テスト", size=20, weight=ft.FontWeight.BOLD),
    ])
    page.add(test_section)
    
    # テスト用のステータス表示
    status_text = ft.Text("テスト実行前", color=ft.colors.BLUE, size=16)
    status_details = ft.Text("詳細情報はここに表示されます。", style=ft.TextThemeStyle.BODY_SMALL)
    
    # スナックバーのテスト
    def test_snackbar(e):
        try:
            status_text.value = "スナックバーをテスト中..."
            status_text.color = ft.colors.BLUE
            page.update()
            
            page.snack_bar = ft.SnackBar(
                content=ft.Text("これはテスト用スナックバーです"),
                action="OK",
                action_color=ft.colors.AMBER,
                on_action=lambda _: print("スナックバーのOKボタンがクリックされました"),
                open=True,
                bgcolor=ft.colors.BLUE_700,
                duration=5000
            )
            page.update()
            
            status_text.value = "スナックバーを表示しました"
            status_text.color = ft.colors.GREEN
            status_details.value = "スクリーン下部にスナックバーが表示されているはずです"
            page.update()
        except Exception as ex:
            status_text.value = "スナックバーの表示に失敗しました"
            status_text.color = ft.colors.RED
            status_details.value = f"エラー: {str(ex)}"
            page.update()
    
    # 標準ダイアログのテスト
    def test_dialog(e):
        try:
            status_text.value = "標準ダイアログをテスト中..."
            status_text.color = ft.colors.BLUE
            page.update()
            
            def on_dialog_close(e):
                status_text.value = "ダイアログが閉じられました"
                page.update()
            
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("標準ダイアログテスト"),
                content=ft.Text("これはAlertDialogです。このダイアログが表示されていますか？"),
                actions=[
                    ft.TextButton("閉じる", on_click=lambda e: (
                        setattr(page.dialog, 'open', False),
                        on_dialog_close(e)
                    )),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                open=True
            )
            
            page.dialog = dialog
            page.update()
            
            status_text.value = "標準ダイアログを表示しました"
            status_text.color = ft.colors.GREEN
            status_details.value = "画面上にダイアログが表示されているはずです"
            page.update()
        except Exception as ex:
            status_text.value = "標準ダイアログの表示に失敗しました"
            status_text.color = ft.colors.RED
            status_details.value = f"エラー: {str(ex)}"
            page.update()
    
    # カスタムオーバーレイモーダルのテスト
    def test_overlay_modal(e):
        try:
            status_text.value = "オーバーレイモーダルをテスト中..."
            status_text.color = ft.colors.BLUE
            page.update()
            
            def close_modal(e, modal_id="test_modal"):
                for item in list(page.overlay):
                    if hasattr(item, 'data') and item.data == modal_id:
                        page.overlay.remove(item)
                        break
                status_text.value = "オーバーレイモーダルを閉じました"
                page.update()
            
            # カスタムモーダルを作成
            modal_container = ft.Container(
                data="test_modal",  # IDを設定
                content=ft.Container(
                    width=400,
                    height=200,
                    bgcolor=ft.colors.SURFACE,
                    border_radius=10,
                    padding=20,
                    content=ft.Column([
                        ft.Text("カスタムオーバーレイモーダル", weight=ft.FontWeight.BOLD, size=18),
                        ft.Container(height=10),  # スペーサー
                        ft.Text("これはpage.overlayを使用した独自のモーダルUIです。表示されていますか？"),
                        ft.Container(height=15),  # スペーサー
                        ft.Row([
                            ft.ElevatedButton(
                                "閉じる", 
                                on_click=lambda x: close_modal(x)
                            ),
                        ], alignment=ft.MainAxisAlignment.END)
                    ]),
                    shadow=ft.BoxShadow(
                        spread_radius=5,
                        blur_radius=10,
                        color=ft.colors.with_opacity(0.3, ft.colors.BLACK)
                    )
                ),
                width=page.width,
                height=page.height,
                bgcolor=ft.colors.with_opacity(0.5, ft.colors.BLACK),
                alignment=ft.alignment.center,
            )
            
            # オーバーレイに追加
            page.overlay.append(modal_container)
            page.update()
            
            status_text.value = "オーバーレイモーダルを表示しました"
            status_text.color = ft.colors.GREEN
            status_details.value = "画面全体に半透明のオーバーレイとモーダルが表示されているはずです"
            page.update()
        except Exception as ex:
            status_text.value = "オーバーレイモーダルの表示に失敗しました"
            status_text.color = ft.colors.RED
            status_details.value = f"エラー: {str(ex)}"
            page.update()
    
    # 実際の保存確認ダイアログテスト
    def test_save_confirmation(e):
        try:
            status_text.value = "保存確認ダイアログをテスト中..."
            status_text.color = ft.colors.BLUE
            page.update()
            
            # アプリケーション状態の模擬設定
            app_state_mock = {
                "page": page,
                "file_path": "/path/to/test.json",
                "raw_data": [{"id": 1, "name": "テスト1"}, {"id": 2, "name": "テスト2"}],
                "is_dirty": False,
                "node_deleted_since_last_save": True,  # ノード削除後の状態
                "confirmation_dialog_showing": False,
                "data_map": {
                    "1": {"id": 1, "name": "テスト1"}, 
                    "2": {"id": 2, "name": "テスト2"}
                },
                "root_ids": ["1", "2"],
                "children_map": {},
                "id_key": "id",
                "edit_buffer": {}
            }
            
            ui_controls_mock = {
                "detail_save_button": ft.ElevatedButton("保存", disabled=True),
                "save_button": ft.ElevatedButton("保存", disabled=False),
                "detail_cancel_button": ft.TextButton("キャンセル", disabled=True),
                "detail_form_column": ft.Column([]),
                "tree_view": ft.Column([])
            }
            
            # モジュールのグローバル変数を一時的に置き換え
            original_app_state = fledjson.ui_helpers.app_state.copy()
            original_ui_controls = fledjson.ui_helpers.ui_controls.copy()
            original_save_directly = fledjson.ui_helpers.save_file_directly
            
            # モックに置き換え
            fledjson.ui_helpers.app_state = app_state_mock
            fledjson.ui_helpers.ui_controls = ui_controls_mock
            
            # 保存関数をモック化
            def mock_save_directly(page, file_path):
                status_text.value = f"保存処理が実行されました: {file_path}"
                status_text.color = ft.colors.GREEN
                status_details.value = "保存成功（モック）"
                page.update()
                return True
            
            fledjson.ui_helpers.save_file_directly = mock_save_directly
            
            # 実際の確認ダイアログを表示
            result = fledjson.ui_helpers.show_save_confirmation("/path/to/test.json")
            
            if result:
                status_text.value = "保存確認ダイアログを表示しました"
                status_text.color = ft.colors.GREEN
                status_details.value = "画面にダイアログまたはスナックバーが表示されているはずです"
            else:
                status_text.value = "保存確認ダイアログの表示に失敗しました"
                status_text.color = ft.colors.RED
                status_details.value = "UI表示には失敗しましたが、安全のために保存は実行されていません"
            
            page.update()
            
            # テスト後にoriginalの値に戻す関数
            def restore_originals():
                fledjson.ui_helpers.app_state = original_app_state
                fledjson.ui_helpers.ui_controls = original_ui_controls
                fledjson.ui_helpers.save_file_directly = original_save_directly
            
            # 遅延実行して確実に元に戻す
            page.set_timer(10000, lambda _: restore_originals())
            
        except Exception as ex:
            status_text.value = "保存確認ダイアログテスト中にエラーが発生しました"
            status_text.color = ft.colors.RED
            status_details.value = f"エラー: {str(ex)}"
            page.update()
    
    # テストボタンを作成
    test_buttons = ft.Column([
        ft.ElevatedButton("スナックバーをテスト", on_click=test_snackbar, width=300),
        ft.ElevatedButton("標準ダイアログをテスト", on_click=test_dialog, width=300),
        ft.ElevatedButton("オーバーレイモーダルをテスト", on_click=test_overlay_modal, width=300),
        ft.ElevatedButton("保存確認ダイアログをテスト", on_click=test_save_confirmation, width=300),
    ], spacing=10)
    
    test_section.controls.append(test_buttons)
    test_section.controls.append(ft.Container(height=20))  # スペーサー
    test_section.controls.append(ft.Text("テスト結果:", weight=ft.FontWeight.BOLD))
    test_section.controls.append(status_text)
    test_section.controls.append(status_details)
    
    # 情報セクション
    info_section = ft.Column([
        ft.Container(height=20),  # スペーサー
        ft.Text("使用方法", size=18, weight=ft.FontWeight.BOLD),
        ft.Text("1. 各テストボタンをクリックすると、対応するUI要素が表示されます"),
        ft.Text("2. UI要素が表示されない場合は、ステータステキストで結果を確認してください"),
        ft.Text("3. ダイアログは他のUI要素と重なることがあります"),
    ])
    page.add(info_section)

if __name__ == "__main__":
    ft.app(target=main)