"""
テスト用のエラーハンドリングシステムのモックを提供するモジュール。
"""
from enum import Enum, auto
import functools
from unittest.mock import MagicMock


class ErrorSeverity(Enum):
    """エラーの重大度"""
    DEBUG = auto()    # デバッグ情報
    INFO = auto()     # 情報
    WARNING = auto()  # 警告
    ERROR = auto()    # エラー
    CRITICAL = auto() # 致命的エラー


class ErrorCategory(Enum):
    """エラーのカテゴリ"""
    GENERAL_ERROR = auto()       # 一般的なエラー
    FILE_ERROR = auto()          # ファイル操作エラー
    DATA_ERROR = auto()          # データ処理エラー
    UI_ERROR = auto()            # UI関連エラー
    NETWORK_ERROR = auto()       # ネットワークエラー
    VALIDATION_ERROR = auto()    # 検証エラー
    VALIDATION = auto()          # 検証エラー
    PERMISSION_ERROR = auto()    # 権限エラー
    CONFIGURATION_ERROR = auto() # 設定エラー
    UNEXPECTED_ERROR = auto()    # 予期しないエラー
    OTHER = auto()               # その他
    FILE_IO = auto()             # ファイルI/Oエラー
    DATA_PROCESSING = auto()     # データ処理エラー


class RecoveryAction(Enum):
    """エラーからの回復方法"""
    RETRY = auto()           # 再試行
    IGNORE = auto()          # 無視して続行
    ROLLBACK = auto()        # 元の状態に戻す
    ALTERNATIVE = auto()     # 代替手段を使用
    USER_DECISION = auto()   # ユーザーに判断を委ねる
    LOG_AND_CONTINUE = auto() # ログに記録して続行
    ABORT = auto()           # 処理を中止
    RESTART = auto()         # プロセスを再起動
    CANCEL = auto()          # キャンセル


class AppError(Exception):
    """
    アプリケーション固有のエラークラス
    重大度、カテゴリ、回復アクションを含む
    """
    def __init__(self, message, severity=ErrorSeverity.ERROR, category=ErrorCategory.OTHER, 
                 recovery_actions=None, source=None, original_exception=None, context=None, details=None):
        """
        AppErrorを初期化します。
        
        Args:
            message (str): エラーメッセージ
            severity (ErrorSeverity): エラーの重大度
            category (ErrorCategory): エラーのカテゴリ
            recovery_actions (list, optional): 回復アクション
            source (str, optional): エラー発生元
            original_exception (Exception, optional): 元の例外
            context (dict, optional): コンテキスト情報
            details (dict, optional): 詳細情報
        """
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.category = category
        self.details = details or {}
        self.source = source
        self.original_exception = original_exception
        self.recovery_actions = recovery_actions or []
        self.context = context or {}
        self.handled = False  # エラーが処理されたかどうか
        self.timestamp = 0
        
    @classmethod
    def from_exception(cls, exception, severity=ErrorSeverity.ERROR, category=None):
        """
        一般的な例外からAppErrorを作成します。
        
        Args:
            exception (Exception): 変換する例外
            severity (ErrorSeverity, optional): エラーの重大度
            category (ErrorCategory, optional): エラーのカテゴリ
            
        Returns:
            AppError: 変換されたAppError
        """
        if isinstance(exception, cls):
            return exception
            
        message = str(exception)
        
        # カテゴリの推測
        if category is None:
            if isinstance(exception, (FileNotFoundError, IOError, PermissionError)):
                category = ErrorCategory.FILE_IO
            elif isinstance(exception, (ValueError, TypeError, KeyError)):
                category = ErrorCategory.DATA_PROCESSING
            else:
                category = ErrorCategory.OTHER
                
        return cls(
            message=message,
            severity=severity,
            category=category,
            original_exception=exception
        )
        
    def to_dict(self):
        """
        エラーを辞書に変換します。
        
        Returns:
            dict: エラー情報の辞書
        """
        return {
            "message": self.message,
            "severity": self.severity.name,
            "category": self.category.name,
            "has_recovery": bool(self.recovery_actions),
            "context": self.context,
            "timestamp": self.timestamp
        }
    
    def add_recovery_action(self, action_name, action_label, action_callback):
        """
        回復アクションを追加します。
        
        Args:
            action_name (str): アクション名（一意の識別子）
            action_label (str): ユーザー向けのラベル
            action_callback (callable): 実行するコールバック関数
        """
        self.recovery_actions[action_name] = (action_label, action_callback)
    
    def has_recovery_actions(self):
        """回復アクションが定義されているかどうかを返します。"""
        return len(self.recovery_actions) > 0
    
    def get_recovery_actions(self):
        """
        定義されている回復アクションを取得します。
        
        Returns:
            dict: {action_name: action_label}
        """
        return {name: label for name, (label, _) in self.recovery_actions.items()}
    
    def execute_recovery_action(self, action_name):
        """
        指定された回復アクションを実行します。
        
        Args:
            action_name (str): 実行するアクション名
            
        Returns:
            Any: アクションの実行結果
            
        Raises:
            KeyError: 指定されたアクション名が存在しない場合
        """
        if action_name not in self.recovery_actions:
            raise KeyError(f"Recovery action '{action_name}' not found")
        
        _, callback = self.recovery_actions[action_name]
        return callback()
    
    def add_context(self, key, value):
        """
        エラーコンテキストに情報を追加します。
        
        Args:
            key (str): コンテキストキー
            value (Any): コンテキスト値
        """
        self.context[key] = value
    
    def __str__(self):
        """エラーの文字列表現を返します。"""
        return f"{self.severity.name} - {self.category.name}: {self.message}"


class ErrorHandler:
    """
    アプリケーション全体のエラー処理を管理するクラス
    """
    def __init__(self, app_state, ui_controls=None):
        """
        ErrorHandlerを初期化します。
        
        Args:
            app_state (dict): アプリケーション状態
            ui_controls (dict, optional): UIコントロール
        """
        self.app_state = app_state
        self.ui_controls = ui_controls
        self.event_hub = app_state.get("event_hub")
        self.error_history = []
        self.max_history = 50
        self.error_counts = {
            severity: 0 for severity in ErrorSeverity
        }
        self.recovery_statistics = {
            action: 0 for action in RecoveryAction
        }
        self.initialized = True  # デフォルトで初期化済み
    
    def handle_error(self, error, raise_exception=False):
        """
        エラーを処理します。
        
        Args:
            error (AppError): 処理するエラー
            raise_exception (bool): 処理後に例外を再送出するかどうか
            
        Returns:
            bool: エラーが正常に処理されたかどうか
            
        Raises:
            AppError: raise_exception=Trueの場合、処理後に例外を再送出
        """
        # 一般的な例外をAppErrorに変換
        if not isinstance(error, AppError):
            error = self._convert_to_app_error(error)
        
        # エラー統計を更新
        self._update_statistics(error)
        
        # エラー履歴に追加
        self._add_to_history(error)
        
        # イベントを発行
        self._publish_error_event(error)
        
        # フィードバックマネージャーに通知
        self._notify_feedback_manager(error)
        
        # エラーをログに記録
        self._log_error(error)
        
        # エラーを処理済みとしてマーク
        error.handled = True
        
        # 例外を再送出するかどうか
        if raise_exception:
            raise error
        
        return True
    
    def _convert_to_app_error(self, exception):
        """
        一般的な例外をAppErrorに変換します。
        
        Args:
            exception (Exception): 変換する例外
            
        Returns:
            AppError: 変換されたAppError
        """
        if isinstance(exception, AppError):
            return exception
        
        # エラーのタイプに基づいてカテゴリを判断
        category = ErrorCategory.GENERAL_ERROR
        severity = ErrorSeverity.ERROR
        
        if isinstance(exception, (FileNotFoundError, PermissionError)):
            category = ErrorCategory.FILE_ERROR
        elif isinstance(exception, (ValueError, TypeError)):
            category = ErrorCategory.DATA_ERROR
        
        # メッセージを取得
        message = str(exception)
        
        # AppErrorを作成して返す
        return AppError(
            message=message,
            severity=severity,
            category=category,
            original_exception=exception,
            source="error_handler"
        )
    
    def _update_statistics(self, error):
        """
        エラー統計を更新します。
        
        Args:
            error (AppError): 更新するエラー
        """
        # 重大度カウントを更新
        self.error_counts[error.severity] = self.error_counts.get(error.severity, 0) + 1
    
    def _add_to_history(self, error):
        """
        エラーを履歴に追加します。
        
        Args:
            error (AppError): 追加するエラー
        """
        # 履歴に追加
        self.error_history.append(error)
        
        # 履歴サイズを制限
        if len(self.error_history) > self.max_history:
            self.error_history.pop(0)
    
    def _publish_error_event(self, error):
        """
        エラーイベントを発行します。
        
        Args:
            error (AppError): 発行するエラー
        """
        # イベントハブが存在する場合のみ
        if not self.event_hub:
            return
        
        try:
            from src.event_hub import EventType, PriorityLevel
            # エラーデータの準備
            error_data = {
                "source": error.source or "error_handler",
                "error": {
                    "message": error.message,
                    "severity": error.severity,
                    "category": error.category,
                    "details": error.details
                }
            }
            
            # 回復アクションがある場合は追加
            if error.has_recovery_actions():
                error_data["error"]["recovery_actions"] = error.get_recovery_actions()
            
            # エラーイベントを発行
            self.event_hub.publish(
                EventType.ERROR_OCCURRED,
                error_data,
                PriorityLevel.HIGH
            )
        except Exception as e:
            print(f"Failed to publish error event: {e}")
    
    def _notify_feedback_manager(self, error):
        """
        フィードバックマネージャーにエラーを通知します。
        
        Args:
            error (AppError): 通知するエラー
        """
        # フィードバックマネージャーが存在する場合のみ
        feedback_manager = self.app_state.get("feedback_manager")
        if not feedback_manager:
            return
        
        try:
            # エラー重大度に応じたトーストタイプ
            toast_type = "error"
            if error.severity == ErrorSeverity.WARNING:
                toast_type = "warning"
            elif error.severity == ErrorSeverity.INFO:
                toast_type = "info"
            
            # エラーメッセージの構築
            message = error.message
            if error.has_recovery_actions():
                recovery_options = ", ".join(error.get_recovery_actions().values())
                message += f"\n\n回復オプション: {recovery_options}"
            
            # トースト通知を表示
            feedback_manager.show_toast(message, toast_type)
        except Exception as e:
            print(f"Failed to notify feedback manager: {e}")
    
    def _log_error(self, error):
        """
        エラーをログに記録します。
        
        Args:
            error (AppError): 記録するエラー
        """
        # ログメッセージの構築
        log_message = f"[{error.severity.name}] {error.category.name}: {error.message}"
        
        # コンテキスト情報がある場合は追加
        if error.context:
            context_str = ", ".join([f"{k}={v}" for k, v in error.context.items()])
            log_message += f" - Context: {context_str}"
        
        # 元の例外がある場合は追加
        if error.original_exception:
            log_message += f" - Original: {error.original_exception}"
        
        # ログレベルに応じてログに記録
        if error.severity == ErrorSeverity.DEBUG:
            print(f"DEBUG: {log_message}")
        elif error.severity == ErrorSeverity.INFO:
            print(f"INFO: {log_message}")
        elif error.severity == ErrorSeverity.WARNING:
            print(f"WARNING: {log_message}")
        elif error.severity == ErrorSeverity.ERROR:
            print(f"ERROR: {log_message}")
        elif error.severity == ErrorSeverity.CRITICAL:
            print(f"CRITICAL: {log_message}")
    
    def get_error_statistics(self):
        """
        エラー統計を取得します。
        
        Returns:
            dict: エラー統計
        """
        return {
            "counts": {severity.name: count for severity, count in self.error_counts.items()},
            "recovery": {action.name: count for action, count in self.recovery_statistics.items()},
            "total": sum(self.error_counts.values())
        }
    
    def clear_error_history(self):
        """エラー履歴をクリアします。"""
        self.error_history = []
    
    def get_error_history(self, severity=None, category=None, limit=None):
        """
        エラー履歴を取得します。
        
        Args:
            severity (ErrorSeverity, optional): フィルタする重大度
            category (ErrorCategory, optional): フィルタするカテゴリ
            limit (int, optional): 取得する最大件数
            
        Returns:
            list: フィルタされたエラー履歴
        """
        filtered_history = self.error_history
        
        # 重大度でフィルタ
        if severity is not None:
            filtered_history = [error for error in filtered_history if error.severity == severity]
        
        # カテゴリでフィルタ
        if category is not None:
            filtered_history = [error for error in filtered_history if error.category == category]
        
        # 件数制限
        if limit is not None:
            filtered_history = filtered_history[-limit:]
        
        return filtered_history


def with_error_handling(error_handler_key="error_handler", severity=ErrorSeverity.ERROR, category=ErrorCategory.GENERAL_ERROR):
    """
    エラーハンドリングを適用するデコレータ
    
    例：
    @with_error_handling()
    def some_function(app_state, arg1, arg2):
        # 処理...
    
    Args:
        error_handler_key (str): app_stateでエラーハンドラーを取得するためのキー
        severity (ErrorSeverity): 発生したエラーの重大度
        category (ErrorCategory): 発生したエラーのカテゴリ
        
    Returns:
        callable: デコレートされた関数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 最初の引数がapp_stateと仮定
            app_state = args[0] if args else None
            if app_state is None or not isinstance(app_state, dict):
                # app_stateがない場合は通常の実行
                return func(*args, **kwargs)
            
            # エラーハンドラーを取得
            error_handler = app_state.get(error_handler_key)
            if error_handler is None:
                # エラーハンドラーがない場合は通常の実行
                return func(*args, **kwargs)
            
            try:
                # 関数を実行
                return func(*args, **kwargs)
            except AppError as e:
                # AppErrorはそのまま処理
                error_handler.handle_error(e)
                return None
            except Exception as e:
                # その他の例外はAppErrorに変換して処理
                app_error = AppError(
                    message=str(e),
                    severity=severity,
                    category=category,
                    source=func.__name__,
                    original_exception=e
                )
                error_handler.handle_error(app_error)
                return None
        
        return wrapper
    
    return decorator


# モジュールのインポート時にモッククラスをシステムに導入
import sys
from unittest.mock import patch, MagicMock

# 実際のモジュールが存在しない場合のために、モックモジュールを作成
if 'fledjson.error_handling' not in sys.modules:
    sys.modules['fledjson.error_handling'] = MagicMock()

# 実際のクラスをモックに置き換える
sys.modules['fledjson.error_handling'].ErrorSeverity = ErrorSeverity
sys.modules['fledjson.error_handling'].ErrorCategory = ErrorCategory
sys.modules['fledjson.error_handling'].RecoveryAction = RecoveryAction
sys.modules['fledjson.error_handling'].AppError = AppError
sys.modules['fledjson.error_handling'].ErrorHandler = ErrorHandler
sys.modules['fledjson.error_handling'].with_error_handling = with_error_handling