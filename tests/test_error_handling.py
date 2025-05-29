"""
test_error_handling.py
エラー処理と回復メカニズムのテストモジュール

ErrorHandlerとAppErrorの機能をテストします。
"""
import pytest
import os
import json
import sys
from unittest.mock import MagicMock, patch

# テスト用のFletモックをインポート
from . import conftest

# テスト対象のモジュールをインポート
from src.error_handling import (
    ErrorHandler, AppError, ErrorSeverity, ErrorCategory, RecoveryAction
)


@pytest.mark.unit
class TestAppError:
    """AppErrorクラスの単体テスト"""

    def test_app_error_init(self):
        """AppErrorの初期化テスト"""
        # 基本的な初期化
        error = AppError("テストエラー")
        assert error.message == "テストエラー"
        assert error.severity == ErrorSeverity.ERROR  # デフォルト値
        assert error.category == ErrorCategory.OTHER  # デフォルト値
        assert error.recovery_actions == []  # デフォルト値
        assert error.original_exception is None  # デフォルト値
        assert isinstance(error.context, dict)  # コンテキストが辞書
        assert error.timestamp > 0  # タイムスタンプがセットされている

        # カスタムパラメータを使った初期化
        orig_exception = ValueError("元の例外")
        context = {"key": "value"}
        recovery_actions = [RecoveryAction.RETRY, RecoveryAction.CANCEL]
        
        error = AppError(
            "カスタムエラー",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.VALIDATION,
            recovery_actions=recovery_actions,
            original_exception=orig_exception,
            context=context
        )
        
        assert error.message == "カスタムエラー"
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.category == ErrorCategory.VALIDATION
        assert error.recovery_actions == recovery_actions
        assert error.original_exception == orig_exception
        assert error.context == context
    
    def test_app_error_str(self):
        """文字列表現のテスト"""
        error = AppError(
            "エラーメッセージ",
            severity=ErrorSeverity.WARNING,
            category=ErrorCategory.FILE_IO
        )
        
        error_str = str(error)
        assert "WARNING" in error_str
        assert "FILE_IO" in error_str
        assert "エラーメッセージ" in error_str
    
    def test_app_error_to_dict(self):
        """辞書変換のテスト"""
        error = AppError(
            "辞書変換テスト",
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.DATA_PROCESSING,
            recovery_actions=[RecoveryAction.RETRY],
            context={"test": True}
        )
        
        error_dict = error.to_dict()
        assert error_dict["message"] == "辞書変換テスト"
        assert error_dict["severity"] == "ERROR"
        assert error_dict["category"] == "DATA_PROCESSING"
        assert error_dict["recovery_actions"] == ["RETRY"]
        assert error_dict["context"] == {"test": True}
        assert "timestamp" in error_dict
    
    def test_from_exception(self):
        """例外からAppErrorを作成するテスト"""
        # IOエラーからのAppError
        io_error = IOError("ファイルIOエラー")
        app_error = AppError.from_exception(io_error)
        
        assert app_error.message == "ファイルIOエラー"
        assert app_error.category == ErrorCategory.FILE_IO  # 自動判定
        
        # JSONエラーからのAppError
        json_error = json.JSONDecodeError("JSONパース失敗", "invalid json", 0)
        app_error = AppError.from_exception(json_error)
        
        assert "JSONパース失敗" in app_error.message
        assert app_error.category == ErrorCategory.DATA_PROCESSING
        
        # カスタムパラメータの上書き
        value_error = ValueError("値エラー")
        app_error = AppError.from_exception(
            value_error,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.WARNING
        )
        
        assert app_error.message == "値エラー"
        assert app_error.category == ErrorCategory.VALIDATION  # 上書き
        assert app_error.severity == ErrorSeverity.WARNING
        assert app_error.original_exception == value_error


@pytest.mark.unit
class TestErrorHandler:
    """ErrorHandlerクラスの単体テスト"""
    
    def test_init(self, sample_app_state, ui_controls):
        """ErrorHandlerの初期化テスト"""
        handler = ErrorHandler(sample_app_state, ui_controls)
        
        assert handler.app_state == sample_app_state
        assert handler.ui_controls == ui_controls
        assert handler.logger is not None
        assert isinstance(handler.error_history, list)
        assert isinstance(handler.error_counts, dict)
        assert len(handler.error_counts) == len(ErrorCategory)
        assert isinstance(handler.recovery_callbacks, dict)
    
    def test_handle_error(self, sample_app_state, ui_controls):
        """handle_errorメソッドのテスト"""
        handler = ErrorHandler(sample_app_state, ui_controls)
        
        # モックFeedbackManagerを設定
        mock_feedback_manager = MagicMock()
        sample_app_state["feedback_manager"] = mock_feedback_manager
        
        # エラー処理
        app_error = AppError(
            "テストエラー",
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.FILE_IO
        )
        
        result = handler.handle_error(app_error, operation_id="test_op", show_ui=True)
        
        # エラー履歴に追加されたか
        assert len(handler.error_history) == 1
        assert handler.error_history[0] == app_error
        
        # エラーカウントが更新されたか
        assert handler.error_counts[ErrorCategory.FILE_IO] == 1
        
        # FeedbackManagerが通知されたか
        mock_feedback_manager.error_operation.assert_called_once()
        assert mock_feedback_manager.error_operation.call_args[0][0] == "test_op"
        
        # 通常の例外処理
        with patch.object(handler, '_show_error_ui') as mock_show_ui:
            exception = ValueError("通常の例外")
            handler.handle_error(exception, show_ui=True)
            
            # AppErrorに変換されるか
            mock_show_ui.assert_called_once()
            error_arg = mock_show_ui.call_args[0][0]
            assert isinstance(error_arg, AppError)
            assert error_arg.message == "通常の例外"
    
    def test_recovery_execution(self, sample_app_state, ui_controls):
        """回復アクションの実行テスト"""
        handler = ErrorHandler(sample_app_state, ui_controls)
        
        # 回復コールバックの登録
        retry_callback = MagicMock(return_value=True)
        handler.register_recovery_callback(RecoveryAction.RETRY, retry_callback)
        
        # テスト用エラー
        app_error = AppError(
            "リカバリーテスト",
            recovery_actions=[RecoveryAction.RETRY]
        )
        
        # 回復アクションの実行
        result = handler.execute_recovery_action(app_error, RecoveryAction.RETRY)
        assert result is True
        retry_callback.assert_called_once_with(app_error)
        
        # サポートされていないアクションを実行
        result = handler.execute_recovery_action(app_error, RecoveryAction.ROLLBACK)
        assert result is False  # サポートされていないアクション
        
        # エラーに定義されていないアクションを実行
        app_error = AppError("リカバリーなし")  # 回復アクションなし
        result = handler.execute_recovery_action(app_error, RecoveryAction.RETRY)
        assert result is False
    
    def test_error_stats(self, sample_app_state, ui_controls):
        """エラー統計情報の取得テスト"""
        handler = ErrorHandler(sample_app_state, ui_controls)
        
        # 各種エラーを追加
        handler.handle_error(
            AppError("エラー1", category=ErrorCategory.FILE_IO, severity=ErrorSeverity.ERROR)
        )
        handler.handle_error(
            AppError("エラー2", category=ErrorCategory.DATA_PROCESSING, severity=ErrorSeverity.WARNING)
        )
        handler.handle_error(
            AppError("エラー3", category=ErrorCategory.FILE_IO, severity=ErrorSeverity.CRITICAL)
        )
        
        # 統計情報を取得
        stats = handler.get_error_stats()
        
        assert stats["total_errors"] == 3
        assert stats["error_counts_by_category"]["FILE_IO"] == 2
        assert stats["error_counts_by_category"]["DATA_PROCESSING"] == 1
        assert stats["critical_errors"] == 1
        assert len(stats["recent_errors"]) == 3
        
        # 履歴クリア
        handler.clear_error_history()
        assert len(handler.error_history) == 0
        assert sum(handler.error_counts.values()) == 0


@pytest.mark.integration
@pytest.mark.error
class TestErrorIntegration:
    """エラー処理の統合テスト"""
    
    def test_app_event_integration(self, sample_app_state, ui_controls, mock_flet):
        """アプリケーションイベントとの統合テスト"""
        # EventHubのモック
        mock_event_hub = MagicMock()
        sample_app_state["event_hub"] = mock_event_hub
        
        handler = ErrorHandler(sample_app_state, ui_controls)
        
        # エラー処理と発行されるイベント
        try:
            with patch.object(handler, '_show_error_ui'):
                handler.handle_error(
                    AppError("ファイルエラー", category=ErrorCategory.FILE_IO),
                    show_ui=True
                )
        except:
            pass  # 例外を無視
        
        # イベント発行が呼ばれたか
        mock_event_hub.publish.assert_called()
        
        # イベントの種類と内容をチェック
        event_type = mock_event_hub.publish.call_args[0][0]
        event_data = mock_event_hub.publish.call_args[0][1]
        
        assert event_type.name == "APP_ERROR"
        assert isinstance(event_data, dict)
        assert "message" in event_data
        assert event_data["category"] == "FILE_IO"
    
    def test_with_error_handling_decorator(self, sample_app_state, ui_controls):
        """エラーハンドリングデコレータのテスト"""
        from src.error_handling import with_error_handling
        
        # ErrorHandlerを設定
        handler = ErrorHandler(sample_app_state, ui_controls)
        sample_app_state["error_handler"] = handler
        
        # テスト対象の関数
        @with_error_handling(
            category=ErrorCategory.DATA_PROCESSING,
            recovery_actions=[RecoveryAction.RETRY]
        )
        def process_data(self, data, update_progress=None):
            if data == "error":
                raise ValueError("テストエラー")
            return "success"
        
        # selfオブジェクトのモック
        mock_self = MagicMock()
        mock_self.app_state = sample_app_state
        
        # 正常系
        result = process_data(mock_self, "valid")
        assert result == "success"
        
        # 異常系
        with pytest.raises(ValueError):
            process_data(mock_self, "error")
        
        # エラーが記録されたか
        assert len(handler.error_history) == 1
        assert "テストエラー" in handler.error_history[0].message
        assert handler.error_history[0].category == ErrorCategory.DATA_PROCESSING
        assert RecoveryAction.RETRY in handler.error_history[0].recovery_actions


@pytest.mark.e2e
@pytest.mark.error
class TestFileOperationErrors:
    """ファイル操作エラーのエンドツーエンドテスト"""
    
    def test_file_not_found(self, sample_app_state, ui_controls, temp_dir):
        """存在しないファイルへのアクセスエラー"""
        # フィードバックマネージャーのモック
        mock_feedback_manager = MagicMock()
        sample_app_state["feedback_manager"] = mock_feedback_manager
        
        # ErrorHandlerの設定
        handler = ErrorHandler(sample_app_state, ui_controls)
        sample_app_state["error_handler"] = handler
        
        # 存在しないファイルパス
        nonexistent_file = os.path.join(temp_dir, "nonexistent.json")
        
        # エラー処理
        app_error = AppError(
            f"ファイル '{os.path.basename(nonexistent_file)}' が見つかりません。",
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.FILE_IO,
            recovery_actions=[RecoveryAction.RETRY, RecoveryAction.CANCEL],
            context={"file_path": nonexistent_file}
        )
        
        # エラーを処理
        operation_id = "file_load"
        handler.handle_error(app_error, operation_id)
        
        # フィードバックが呼ばれたか
        mock_feedback_manager.error_operation.assert_called_once()
        assert mock_feedback_manager.error_operation.call_args[0][0] == operation_id
        assert "見つかりません" in mock_feedback_manager.error_operation.call_args[0][1]
        
        # エラー統計にカウントされたか
        stats = handler.get_error_stats()
        assert stats["error_counts_by_category"]["FILE_IO"] == 1
    
    def test_json_parse_error(self, sample_app_state, ui_controls, temp_dir):
        """JSONパースエラー"""
        # フィードバックマネージャーのモック
        mock_feedback_manager = MagicMock()
        sample_app_state["feedback_manager"] = mock_feedback_manager
        
        # ErrorHandlerの設定
        handler = ErrorHandler(sample_app_state, ui_controls)
        sample_app_state["error_handler"] = handler
        
        # 不正なJSONファイルを作成
        invalid_json_file = os.path.join(temp_dir, "invalid.json")
        with open(invalid_json_file, 'w') as f:
            f.write('{"unclosed: "string"}')  # 不正なJSON
        
        # エラー処理
        try:
            with open(invalid_json_file, 'r') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            app_error = AppError.from_exception(
                e,
                category=ErrorCategory.DATA_PROCESSING,
                context={"file_path": invalid_json_file}
            )
            
            # エラーを処理
            operation_id = "file_load"
            handler.handle_error(app_error, operation_id)
            
            # フィードバックが呼ばれたか
            mock_feedback_manager.error_operation.assert_called_once()
            assert "JSONDecode" in mock_feedback_manager.error_operation.call_args[0][1] or "解析" in mock_feedback_manager.error_operation.call_args[0][1]
            
            # エラー統計にカウントされたか
            stats = handler.get_error_stats()
            assert stats["error_counts_by_category"]["DATA_PROCESSING"] == 1