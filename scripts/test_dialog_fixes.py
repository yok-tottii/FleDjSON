"""
test_dialog_fixes.py
ダイアログ表示の修正をテストするためのスクリプト
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import flet as ft

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 必要なモジュールをインポート
import src.ui_helpers
import src.main
import src.form_handlers

# グローバルモック
app_state_mock = {
    "page": MagicMock(),
    "file_path": "/path/to/test.json",
    "raw_data": [{"id": 1, "name": "テスト1"}, {"id": 2, "name": "テスト2"}],
    "is_dirty": False,
    "node_deleted_since_last_save": False,
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
    "detail_save_button": MagicMock(),
    "save_button": MagicMock(),
    "detail_cancel_button": MagicMock(),
    "detail_delete_button": MagicMock(),
    "detail_form_column": MagicMock(),
    "tree_view": MagicMock()
}

class DialogFixesTest(unittest.TestCase):
    def setUp(self):
        # テスト用にモジュールのグローバル変数を上書き
        fledjson.ui_helpers.app_state = app_state_mock
        fledjson.ui_helpers.ui_controls = ui_controls_mock
        
        # ページのモック
        app_state_mock["page"] = MagicMock()
        app_state_mock["page"].dialog = None
        app_state_mock["page"].overlay = []
        app_state_mock["page"].snack_bar = None
        
        # ディープコピーではなく、テスト用に再度直接設定
        app_state_mock["is_dirty"] = False
        app_state_mock["node_deleted_since_last_save"] = False
        app_state_mock["confirmation_dialog_showing"] = False
        
        # スパイを設定
        ui_controls_mock["detail_save_button"].disabled = True  # 初期状態ではグレーアウト
        ui_controls_mock["detail_save_button"].update = MagicMock()
        ui_controls_mock["detail_save_button"]._page = app_state_mock["page"]
        
        ui_controls_mock["detail_cancel_button"].disabled = True  # 初期状態ではグレーアウト
        ui_controls_mock["detail_cancel_button"].update = MagicMock()
        
        ui_controls_mock["save_button"].disabled = False  # 初期状態では有効
        ui_controls_mock["save_button"].update = MagicMock()
        
        # 保存関数をモック
        self.original_save_directly = fledjson.ui_helpers.save_file_directly
        fledjson.ui_helpers.save_file_directly = MagicMock(return_value=True)
        
        print("[OK] テスト環境のセットアップ完了")
        
    def tearDown(self):
        # 元の関数を復元
        fledjson.ui_helpers.save_file_directly = self.original_save_directly
        
    def test_update_ui_save_state(self):
        """UI保存状態の更新機能をテスト"""
        print("\n=== update_ui_save_state のテスト ===")
        
        # まず初期状態を確認
        is_dirty = app_state_mock.get("is_dirty", False)
        initial_disabled = ui_controls_mock["detail_save_button"].disabled
        print(f"初期状態: is_dirty={is_dirty}, detail_save_button.disabled={initial_disabled}")
        
        # is_dirtyフラグを設定
        app_state_mock["is_dirty"] = True
        
        # update_ui_save_stateを呼び出し
        from src.ui_helpers import update_ui_save_state
        update_ui_save_state()
        
        # 状態を確認
        final_disabled = ui_controls_mock["detail_save_button"].disabled
        print(f"更新後の状態: is_dirty=True, detail_save_button.disabled={final_disabled}")
        
        # 検証
        self.assertFalse(final_disabled, "is_dirtyがTrueのとき、ボタンは有効化されるべき")
        ui_controls_mock["detail_save_button"].update.assert_called()
        app_state_mock["page"].update.assert_called()
        
        print("[OK] UI保存状態のテスト成功")
        
    def test_show_save_confirmation(self):
        """保存確認ダイアログの表示をテスト"""
        print("\n=== show_save_confirmation のテスト ===")
        
        # node_deleted_since_last_saveフラグを設定
        app_state_mock["node_deleted_since_last_save"] = True
        
        # show_save_confirmationを呼び出し
        from src.ui_helpers import show_save_confirmation
        result = show_save_confirmation("/path/to/test.json")
        
        # 結果の確認
        self.assertTrue(result, "show_save_confirmationはTrueを返すべき")
        self.assertIsNotNone(app_state_mock["page"].dialog, "ダイアログが表示されるべき")
        self.assertTrue(app_state_mock["page"].dialog.open, "ダイアログが開かれるべき")
        self.assertTrue(app_state_mock["confirmation_dialog_showing"], "confirmation_dialog_showingフラグが設定されるべき")
        app_state_mock["page"].update.assert_called()
        
        # ダイアログのアクション（保存ボタン）をシミュレート
        save_button = app_state_mock["page"].dialog.actions[1]  # 「保存」は2番目のボタン
        
        # クリックをシミュレート
        mock_event = MagicMock()
        mock_event._mock_name = 'mock'  # テスト用にフラグを設定
        save_button.on_click(mock_event)
        
        # 保存が実行されたか確認
        fledjson.ui_helpers.save_file_directly.assert_called_once()
        self.assertFalse(app_state_mock["node_deleted_since_last_save"], "フラグがリセットされるべき")
        self.assertFalse(app_state_mock["confirmation_dialog_showing"], "confirmation_dialog_showingフラグがリセットされるべき")
        
        print("[OK] 保存確認ダイアログのテスト成功")
        
    def test_keyboard_shortcut_save(self):
        """キーボードショートカット保存をテスト"""
        print("\n=== ショートカットキー保存のテスト ===")
        
        # ショートカットイベントを模擬
        mock_key_event = MagicMock()
        mock_key_event.key = "S"
        mock_key_event.ctrl = True
        mock_key_event.meta = False
        mock_key_event.page = app_state_mock["page"]
        
        # 元のperform_save_operationを保存
        original_perform_save = fledjson.ui_helpers.perform_save_operation
        
        # モックに置き換え
        fledjson.ui_helpers.perform_save_operation = MagicMock(return_value=True)
        
        try:
            # 通常の保存
            app_state_mock["node_deleted_since_last_save"] = False
            fledjson.main.handle_keyboard_event(mock_key_event)
            
            # 検証
            fledjson.ui_helpers.perform_save_operation.assert_called_once()
            fledjson.ui_helpers.perform_save_operation.reset_mock()
            app_state_mock["page"].update.assert_called()
            
            print("[OK] 通常のショートカット保存テスト成功")
            
            # ノード削除後の保存
            app_state_mock["node_deleted_since_last_save"] = True
            app_state_mock["page"].reset_mock()
            
            fledjson.main.handle_keyboard_event(mock_key_event)
            
            # 検証
            fledjson.ui_helpers.perform_save_operation.assert_called_once()
            app_state_mock["page"].update.assert_called()
            
            print("[OK] ノード削除後のショートカット保存テスト成功")
            
        finally:
            # 元の関数を復元
            fledjson.ui_helpers.perform_save_operation = original_perform_save

    def test_form_change_updates_button(self):
        """フォーム変更時にボタン状態が更新されるかテスト"""
        print("\n=== フォーム変更時のボタン状態更新テスト ===")
        
        # is_dirtyを初期化
        app_state_mock["is_dirty"] = False
        ui_controls_mock["detail_save_button"].disabled = True
        ui_controls_mock["detail_save_button"].update.reset_mock()
        app_state_mock["page"].update.reset_mock()
        
        # handle_data_changeを呼び出し
        from src.ui_helpers import handle_data_change
        handle_data_change(True)
        
        # 検証
        self.assertTrue(app_state_mock["is_dirty"], "is_dirtyフラグが設定されるべき")
        self.assertFalse(ui_controls_mock["detail_save_button"].disabled, "ボタンは有効化されるべき")
        ui_controls_mock["detail_save_button"].update.assert_called()
        app_state_mock["page"].update.assert_called()
        
        print("[OK] フォーム変更時のボタン状態更新テスト成功")

def run_tests():
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
    print("\n[OK] すべてのテストが完了しました")

if __name__ == "__main__":
    run_tests()