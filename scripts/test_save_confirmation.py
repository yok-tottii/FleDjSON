"""
test_save_confirmation.py
保存確認ダイアログの機能をテストするスクリプト
"""
import sys
import os
import flet as ft
from unittest.mock import MagicMock
import json
import tempfile

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 必要なモジュールをインポート
from src.ui_helpers import show_save_confirmation, perform_save_operation, save_file_directly, update_ui_save_state
from src.data_handlers import delete_node

# グローバルモック
app_state_mock = {
    "page": MagicMock(),
    "file_path": None,
    "raw_data": None,
    "is_dirty": False,
    "node_deleted_since_last_save": False,
    "data_map": {},
    "root_ids": [],
    "children_map": {},
    "id_key": "id",
    "edit_buffer": {},
    "delete_confirm_mode": False
}

ui_controls_mock = {
    "detail_save_button": MagicMock(),
    "save_button": MagicMock(),
    "tree_view": MagicMock()
}


def setup_mocks():
    """モックのセットアップ"""
    # モジュールのグローバル変数を上書き
    import src.ui_helpers
    fledjson.ui_helpers.app_state = app_state_mock
    fledjson.ui_helpers.ui_controls = ui_controls_mock
    
    # update_tree_viewをモックに置き換え
    fledjson.ui_helpers.update_tree_view = MagicMock()
    
    import src.data_handlers
    fledjson.data_handlers.app_state = app_state_mock
    fledjson.data_handlers.ui_controls = ui_controls_mock
    
    # ページのモック
    app_state_mock["page"] = MagicMock()
    app_state_mock["page"].dialog = None
    app_state_mock["page"].overlay = []
    app_state_mock["page"].snack_bar = None
    
    # サンプルデータの作成
    app_state_mock["raw_data"] = [
        {"id": 1, "name": "ノード1"},
        {"id": 2, "name": "ノード2"},
        {"id": 3, "name": "ノード3"}
    ]
    
    # データマップのセットアップ
    app_state_mock["data_map"] = {
        "1": {"id": 1, "name": "ノード1"},
        "2": {"id": 2, "name": "ノード2"},
        "3": {"id": 3, "name": "ノード3"}
    }
    
    # ルートIDsのセットアップ
    app_state_mock["root_ids"] = ["1", "2", "3"]
    
    # 一時ファイルパスを作成
    temp_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    temp_file.close()
    app_state_mock["file_path"] = temp_file.name
    
    print(f"[OK] モックのセットアップが完了しました。一時ファイルパス: {app_state_mock['file_path']}")
    return temp_file.name


def clean_up(temp_file_path):
    """テスト用の一時ファイルを削除"""
    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)
        print(f"[OK] 一時ファイルを削除しました: {temp_file_path}")


def test_normal_save():
    """通常の保存テスト（確認ダイアログなし）"""
    print("\n=== 通常の保存テスト（確認ダイアログなし） ===")
    
    # 保存前の状態
    app_state_mock["is_dirty"] = True
    app_state_mock["node_deleted_since_last_save"] = False
    
    # 保存操作
    result = perform_save_operation()
    
    # 結果の検証
    print(f"保存結果: {result}")
    print(f"保存後の状態 - is_dirty: {app_state_mock['is_dirty']}")
    print(f"ダイアログ表示: {app_state_mock['page'].dialog is not None}")
    
    assert result is True, "保存操作が成功すべきです"
    assert app_state_mock["is_dirty"] is False, "保存後にis_dirtyフラグがFalseになるべきです"
    assert app_state_mock["page"].dialog is None, "確認ダイアログが表示されるべきではありません"
    
    print("[OK] 通常の保存テストが成功しました")


def test_save_after_node_deletion():
    """ノード削除後の保存テスト（確認ダイアログあり）"""
    print("\n=== ノード削除後の保存テスト（確認ダイアログあり） ===")
    
    # 削除操作をシミュレート
    app_state_mock["node_deleted_since_last_save"] = True
    app_state_mock["is_dirty"] = True
    
    # モジュールをインポート
    import src.ui_helpers
    
    # モックの保存処理を用意
    original_save_directly = fledjson.ui_helpers.save_file_directly
    try:
        # save_file_directlyをモックに置き換え
        mock_save = MagicMock(return_value=True)
        fledjson.ui_helpers.save_file_directly = mock_save
        
        # 保存操作
        result = perform_save_operation()
        
        # 結果の検証
        print(f"保存後のダイアログ: {app_state_mock['page'].dialog is not None}")
        print(f"確認ダイアログのタイトル: {getattr(app_state_mock['page'].dialog, 'title', None)}")
        
        assert result is True, "確認ダイアログは表示されますが、真を返すべきです"
        assert app_state_mock["page"].dialog is not None, "確認ダイアログが表示されるべきです"
        assert app_state_mock["page"].dialog.open is True, "確認ダイアログが開かれるべきです"
        assert app_state_mock["page"].update.called, "ページが更新されるべきです"
        
        # ダイアログからの確認をシミュレート
        on_confirm = app_state_mock["page"].dialog.actions[1].on_click
        
        # Flet Control Eventをシミュレート
        mock_event = MagicMock()
        mock_event.data = "confirm"
        
        # 「保存」ボタンのクリックをシミュレート
        on_confirm(mock_event)
        
        # 確認結果の検証
        assert mock_save.called, "save_file_directlyが呼び出されるべきです"
        assert app_state_mock["node_deleted_since_last_save"] is False, "確認後にnode_deleted_since_last_saveフラグがリセットされるべきです"
        
        print("[OK] ノード削除後の保存テストが成功しました")
    finally:
        # 元の関数を復元
        fledjson.ui_helpers.save_file_directly = original_save_directly


def test_integration():
    """削除から保存までの統合テスト"""
    print("\n=== 削除から保存までの統合テスト ===")
    
    # データの初期化
    app_state_mock["node_deleted_since_last_save"] = False
    app_state_mock["is_dirty"] = False
    
    # モジュールのインポートとパッチ
    import src.data_handlers
    
    # 元の関数を保存
    original_update_tree_view = getattr(fledjson.data_handlers, 'update_tree_view', None)
    original_clear_detail_form = getattr(fledjson.data_handlers, 'clear_detail_form', None)
    
    try:
        # 依存関数をモックに置き換え
        fledjson.data_handlers.update_tree_view = MagicMock()
        fledjson.data_handlers.clear_detail_form = MagicMock()
        
        # ノード2を削除
        delete_node("2")
        
        # 削除後の状態を検証
        print(f"削除後の状態:")
        print(f"  node_deleted_since_last_save: {app_state_mock['node_deleted_since_last_save']}")
        print(f"  root_ids: {app_state_mock['root_ids']}")
        print(f"  data_map keys: {list(app_state_mock['data_map'].keys())}")
        
        assert app_state_mock["node_deleted_since_last_save"] is True, "ノード削除後にフラグが設定されるべきです"
        assert "2" not in app_state_mock["root_ids"], "削除されたノードはroot_idsから削除されるべきです"
        assert "2" not in app_state_mock["data_map"], "削除されたノードはdata_mapから削除されるべきです"
        
        # モジュールをインポート
        import src.ui_helpers
        
        # モックの保存処理を用意
        original_save_directly = fledjson.ui_helpers.save_file_directly
        try:
            # save_file_directlyをモックに置き換え
            mock_save = MagicMock(return_value=True)
            fledjson.ui_helpers.save_file_directly = mock_save
            
            # 保存操作を実行
            result = perform_save_operation()
            
            # 保存操作の結果を検証
            assert result is True, "保存操作は成功すべきです"
            assert app_state_mock["page"].dialog is not None, "ノード削除後の保存では確認ダイアログが表示されるべきです"
            
            print("[OK] 削除から保存までの統合テストが成功しました")
        finally:
            # 元の関数を復元
            fledjson.ui_helpers.save_file_directly = original_save_directly
            
    finally:
        # 元の関数を復元（存在する場合のみ）
        if original_update_tree_view:
            fledjson.data_handlers.update_tree_view = original_update_tree_view
        if original_clear_detail_form:
            fledjson.data_handlers.clear_detail_form = original_clear_detail_form


def run_all_tests():
    """すべてのテストを実行"""
    temp_file_path = setup_mocks()
    
    try:
        test_normal_save()
        # テスト間で状態をリセット
        setup_mocks()
        
        test_save_after_node_deletion()
        # テスト間で状態をリセット
        setup_mocks()
        
        test_integration()
        
        print("\n[OK] すべてのテストが成功しました！")
    except AssertionError as e:
        print(f"\n[ERROR] テストに失敗しました: {e}")
        raise
    finally:
        clean_up(temp_file_path)


if __name__ == "__main__":
    run_all_tests()