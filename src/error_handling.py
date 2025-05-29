"""
error_handling.py
エラー処理モジュール

FleDjSONのエラー処理と回復メカニズムを提供します。
エラーのログ記録、ユーザー通知、エラー発生時の回復処理を統合的に扱います。
"""
import logging
import functools
import traceback
import time
import json
import os
from enum import Enum, auto
from typing import Dict, Any, Optional, Callable, List, Tuple, Union, Set
import flet as ft
from flet import Colors, Text

# FeedbackManagerとEventHubの循環インポートを避けるため必要な場合にだけインポート
# from src.feedback import FeedbackManager 
# from src.event_hub import EventHub, EventType, Event, EventPriority


class ErrorSeverity(Enum):
    """エラーの重大度を表す列挙型"""
    DEBUG = auto()      # 開発者向けデバッグ情報
    INFO = auto()       # 情報提供的なエラー
    WARNING = auto()    # 警告（操作は継続可能）
    ERROR = auto()      # エラー（操作は中断されるが、アプリは継続可能）
    CRITICAL = auto()   # 致命的なエラー（アプリケーション全体に影響）


class ErrorCategory(Enum):
    """エラーのカテゴリを表す列挙型"""
    FILE_IO = auto()        # ファイル読み込み・書き込み関連
    DATA_PROCESSING = auto()  # データ処理関連
    UI = auto()             # UI関連
    VALIDATION = auto()     # バリデーション関連
    NETWORK = auto()        # ネットワーク関連
    SYSTEM = auto()         # システム関連
    OTHER = auto()          # その他


class RecoveryAction(Enum):
    """エラーからの回復アクションを表す列挙型"""
    RETRY = auto()          # 操作を再試行
    IGNORE = auto()         # エラーを無視して続行
    ROLLBACK = auto()       # 変更を元に戻す
    ALTERNATIVE = auto()    # 代替手段を試す
    CANCEL = auto()         # 操作をキャンセル
    ABORT = auto()          # アプリケーションを終了


class AppError(Exception):
    """アプリケーション固有のエラークラス

    基本的な例外情報に加えて、エラーの重大度、カテゴリ、回復方法などの
    アプリケーション固有のコンテキスト情報を保持します。
    """
    
    def __init__(
        self, 
        message: str, 
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: ErrorCategory = ErrorCategory.OTHER,
        recovery_actions: List[RecoveryAction] = None,
        original_exception: Optional[Exception] = None,
        context: Dict[str, Any] = None
    ):
        """AppErrorを初期化します。

        Args:
            message (str): エラーメッセージ
            severity (ErrorSeverity, optional): エラーの重大度
            category (ErrorCategory, optional): エラーのカテゴリ
            recovery_actions (List[RecoveryAction], optional): 有効な回復アクション
            original_exception (Exception, optional): 元の例外
            context (Dict[str, Any], optional): 追加のコンテキスト情報
        """
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.category = category
        self.recovery_actions = recovery_actions or []
        self.original_exception = original_exception
        self.context = context or {}
        self.timestamp = time.time()
        self.traceback = traceback.format_exc() if original_exception else None
    
    def __str__(self) -> str:
        """エラーの文字列表現を返します。"""
        return f"{self.severity.name} [{self.category.name}]: {self.message}"
    
    def to_dict(self) -> Dict[str, Any]:
        """エラー情報を辞書として返します。"""
        recovery_actions = [action.name for action in self.recovery_actions] if self.recovery_actions else []
        
        return {
            "message": self.message,
            "severity": self.severity.name,
            "category": self.category.name,
            "recovery_actions": recovery_actions,
            "original_exception": str(self.original_exception) if self.original_exception else None,
            "context": self.context,
            "timestamp": self.timestamp,
            "traceback": self.traceback
        }
    
    @classmethod
    def from_exception(
        cls, 
        exception: Exception, 
        category: ErrorCategory = ErrorCategory.OTHER,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Dict[str, Any] = None
    ) -> 'AppError':
        """通常の例外からAppErrorを作成します。

        Args:
            exception (Exception): 元の例外
            category (ErrorCategory, optional): エラーのカテゴリ
            severity (ErrorSeverity, optional): エラーの重大度
            context (Dict[str, Any], optional): 追加のコンテキスト情報

        Returns:
            AppError: 作成されたAppErrorインスタンス
        """
        message = str(exception)
        
        # 例外の型に基づいてカテゴリを推測
        if isinstance(exception, (FileNotFoundError, PermissionError, IOError)):
            category = ErrorCategory.FILE_IO
        elif isinstance(exception, (json.JSONDecodeError, TypeError, ValueError)):
            category = ErrorCategory.DATA_PROCESSING
        elif isinstance(exception, (ConnectionError, TimeoutError)):
            category = ErrorCategory.NETWORK
        
        return cls(
            message=message,
            severity=severity,
            category=category,
            original_exception=exception,
            context=context
        )


class ErrorHandler:
    """エラー処理を一元管理するクラス

    アプリケーション全体のエラー処理を統一的に扱い、
    ログ記録、ユーザー通知、エラー回復などの機能を提供します。
    """
    
    def __init__(self, app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None):
        """ErrorHandlerを初期化します。

        Args:
            app_state (Dict[str, Any]): アプリケーションの状態
            ui_controls (Dict[str, Any]): UIコントロール
            page (ft.Page, optional): Fletページオブジェクト
        """
        self.app_state = app_state
        self.ui_controls = ui_controls
        self.page = page or app_state.get("page")
        
        # ロガーの設定
        self.logger = logging.getLogger("fledjson")
        self.configure_logger()
        
        # エラー履歴
        self.error_history: List[AppError] = []
        self.max_history_size = 100
        
        # エラーカウンター（カテゴリ別）
        self.error_counts: Dict[ErrorCategory, int] = {category: 0 for category in ErrorCategory}
        
        # 回復アクションのコールバック
        self.recovery_callbacks: Dict[RecoveryAction, Callable] = {}
        
        # FeedbackManagerへの参照（遅延取得）
        self._feedback_manager = None
        
        # EventHubへの参照（遅延取得）
        self._event_hub = None
        
        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] ErrorHandler initialized.")
    
    def configure_logger(self):
        """ロガーを設定します。"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, "fledjson.log")
        
        # ハンドラー設定
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        console_handler = logging.StreamHandler()
        
        # フォーマッター設定
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # ロガー設定
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # 既存のハンドラーを重複して追加しないようにする
        self.logger.propagate = False
    
    @property
    def feedback_manager(self):
        """FeedbackManagerへの参照を取得します。"""
        if self._feedback_manager is None:
            self._feedback_manager = self.app_state.get("feedback_manager")
        return self._feedback_manager
    
    @property
    def event_hub(self):
        """EventHubへの参照を取得します。"""
        if self._event_hub is None:
            self._event_hub = self.app_state.get("event_hub")
        return self._event_hub
    
    def handle_error(
        self, 
        error: Union[Exception, AppError],
        operation_id: Optional[str] = None,
        show_ui: bool = True,
        context: Dict[str, Any] = None,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None
    ) -> AppError:
        """エラーを処理します。

        Args:
            error (Union[Exception, AppError]): 処理するエラー
            operation_id (str, optional): 関連する操作ID（FeedbackManager用）
            show_ui (bool): UIにエラーを表示するかどうか
            context (Dict[str, Any], optional): 追加のコンテキスト情報
            category (ErrorCategory, optional): エラーのカテゴリ（通常の例外の場合）
            severity (ErrorSeverity, optional): エラーの重大度（通常の例外の場合）

        Returns:
            AppError: 処理されたAppErrorインスタンス
        """
        # AppError以外の例外をAppErrorに変換
        if not isinstance(error, AppError):
            app_error = AppError.from_exception(
                error, 
                category=category or ErrorCategory.OTHER,
                severity=severity or ErrorSeverity.ERROR,
                context=context
            )
        else:
            app_error = error
            # コンテキストを更新（存在する場合）
            if context:
                app_error.context.update(context)
        
        # エラーカウンターを更新
        self.error_counts[app_error.category] = self.error_counts.get(app_error.category, 0) + 1
        
        # エラー履歴に追加
        self.error_history.append(app_error)
        if len(self.error_history) > self.max_history_size:
            self.error_history.pop(0)  # 古いエラーを削除
        
        # ログに記録
        self._log_error(app_error)
        
        # イベントを発行（EventHubが利用可能な場合）
        self._publish_error_event(app_error)
        
        # UIに表示（必要な場合）
        if show_ui:
            self._show_error_ui(app_error, operation_id)
        
        return app_error
    
    def _log_error(self, error: AppError):
        """エラーをログに記録します。

        Args:
            error (AppError): 記録するエラー
        """
        # 重大度に応じたログレベルを選択
        log_level = {
            ErrorSeverity.DEBUG: logging.DEBUG,
            ErrorSeverity.INFO: logging.INFO,
            ErrorSeverity.WARNING: logging.WARNING,
            ErrorSeverity.ERROR: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
        }.get(error.severity, logging.ERROR)
        
        # 基本的なエラーメッセージをログに記録
        self.logger.log(log_level, f"{error.category.name}: {error.message}")
        
        # 詳細情報があれば記録
        if error.traceback and log_level >= logging.ERROR:
            self.logger.log(log_level, f"詳細:\n{error.traceback}")
        
        # コンテキスト情報があれば記録
        if error.context and log_level >= logging.DEBUG:
            context_str = json.dumps(error.context, ensure_ascii=False, default=str)
            self.logger.log(logging.DEBUG, f"コンテキスト: {context_str}")
    
    def _publish_error_event(self, error: AppError):
        """エラーイベントを発行します。

        Args:
            error (AppError): 発行するエラー
        """
        if not self.event_hub:
            return
        
        try:
            from event_hub import EventType, EventPriority
            
            # 重大度に応じた優先度を設定
            priority_map = {
                ErrorSeverity.DEBUG: EventPriority.LOW,
                ErrorSeverity.INFO: EventPriority.LOW,
                ErrorSeverity.WARNING: EventPriority.NORMAL,
                ErrorSeverity.ERROR: EventPriority.HIGH,
                ErrorSeverity.CRITICAL: EventPriority.HIGHEST,
            }
            priority = priority_map.get(error.severity, EventPriority.NORMAL)
            
            # イベントを発行
            self.event_hub.publish(
                EventType.APP_ERROR,
                data=error.to_dict(),
                source="error_handler",
                priority=priority,
                async_mode=error.severity != ErrorSeverity.CRITICAL  # 致命的エラーは同期的に処理
            )
        except (ImportError, AttributeError, Exception) as e:
            # イベント発行に失敗した場合はログに記録
            self.logger.error(f"エラーイベントの発行に失敗しました: {e}")
    
    def _show_error_ui(self, error: AppError, operation_id: Optional[str] = None):
        """UIにエラーを表示します。

        Args:
            error (AppError): 表示するエラー
            operation_id (str, optional): 関連する操作ID
        """
        # FeedbackManagerが利用可能ならそちらを使用
        if self.feedback_manager and operation_id:
            message = error.message
            if error.severity == ErrorSeverity.DEBUG:
                message = f"[DEBUG] {message}"
            elif error.severity == ErrorSeverity.CRITICAL:
                message = f"[重大] {message}"
            
            self.feedback_manager.error_operation(operation_id, message)
            return
        
        # FeedbackManagerが利用できない場合はSnackBarを使用
        if self.page:
            # 重大度に応じた色を設定
            color_map = {
                ErrorSeverity.DEBUG: Colors.BLUE,
                ErrorSeverity.INFO: Colors.BLUE_GREY,
                ErrorSeverity.WARNING: Colors.ORANGE,
                ErrorSeverity.ERROR: Colors.RED,
                ErrorSeverity.CRITICAL: Colors.RED_900,
            }
            bg_color = color_map.get(error.severity, Colors.RED)
            
            # 回復アクションがある場合はボタンを表示
            action_text = "OK"
            if error.recovery_actions and RecoveryAction.RETRY in error.recovery_actions:
                action_text = "再試行"
            
            # スナックバーを表示
            self.page.snack_bar = ft.SnackBar(
                content=Text(error.message),
                action=action_text,
                bgcolor=bg_color,
                open=True
            )
            self.page.update()
    
    def register_recovery_callback(self, action: RecoveryAction, callback: Callable):
        """回復アクションのコールバックを登録します。

        Args:
            action (RecoveryAction): 回復アクション
            callback (Callable): コールバック関数
        """
        self.recovery_callbacks[action] = callback
    
    def execute_recovery_action(self, error: AppError, action: RecoveryAction) -> bool:
        """回復アクションを実行します。

        Args:
            error (AppError): 対象のエラー
            action (RecoveryAction): 実行する回復アクション

        Returns:
            bool: 回復アクションが正常に実行された場合はTrue
        """
        # エラーが指定されたアクションをサポートしているか確認
        if action not in error.recovery_actions:
            self.logger.warning(f"エラーは回復アクション {action.name} をサポートしていません")
            return False
        
        # コールバックが登録されているか確認
        callback = self.recovery_callbacks.get(action)
        if not callback:
            self.logger.warning(f"回復アクション {action.name} のコールバックが登録されていません")
            return False
        
        try:
            # コールバックを実行
            result = callback(error)
            self.logger.info(f"回復アクション {action.name} が実行されました")
            return result
        except Exception as e:
            self.logger.error(f"回復アクション {action.name} の実行中にエラーが発生しました: {e}")
            return False
    
    def get_error_stats(self) -> Dict[str, Any]:
        """エラー統計情報を取得します。

        Returns:
            Dict[str, Any]: エラー統計情報
        """
        total_errors = sum(self.error_counts.values())
        recent_errors = self.error_history[-10:] if self.error_history else []
        
        stats = {
            "total_errors": total_errors,
            "error_counts_by_category": {category.name: count for category, count in self.error_counts.items()},
            "recent_errors": [error.to_dict() for error in recent_errors],
            "critical_errors": sum(1 for error in self.error_history if error.severity == ErrorSeverity.CRITICAL)
        }
        
        return stats
    
    def clear_error_history(self):
        """エラー履歴をクリアします。"""
        self.error_history.clear()
        self.error_counts = {category: 0 for category in ErrorCategory}
        self.logger.info("エラー履歴がクリアされました")


def with_error_handling(
    category: ErrorCategory = ErrorCategory.OTHER,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    recovery_actions: List[RecoveryAction] = None,
    show_ui: bool = True
):
    """エラー処理を行うデコレータ

    Args:
        category (ErrorCategory, optional): エラーのカテゴリ
        severity (ErrorSeverity, optional): エラーの重大度
        recovery_actions (List[RecoveryAction], optional): 有効な回復アクション
        show_ui (bool, optional): UIにエラーを表示するかどうか

    Returns:
        Callable: デコレータ関数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 第一引数がself（クラスメソッド）の場合、そこからErrorHandlerを取得
            self_arg = args[0] if args else None
            app_state = getattr(self_arg, 'app_state', None) if self_arg else None
            
            if not app_state or 'error_handler' not in app_state:
                # ErrorHandlerが利用できない場合は元の関数をそのまま実行
                return func(*args, **kwargs)
            
            error_handler = app_state['error_handler']
            operation_id = kwargs.pop('operation_id', None)
            
            try:
                # 元の関数を実行
                return func(*args, **kwargs)
            except Exception as e:
                # エラーコンテキストを収集
                context = {
                    "function": func.__name__,
                    "args": [str(arg) for arg in args[1:]] if len(args) > 1 else [],
                    "kwargs": {k: str(v) for k, v in kwargs.items() if k != 'password'}
                }
                
                # AppErrorを作成
                app_error = AppError(
                    message=str(e),
                    severity=severity,
                    category=category,
                    recovery_actions=recovery_actions,
                    original_exception=e,
                    context=context
                )
                
                # エラーを処理
                error_handler.handle_error(app_error, operation_id, show_ui)
                
                # 例外を再発生（呼び出し元でもキャッチできるようにする）
                raise
                
        return wrapper
    return decorator


def create_error_handler(app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None) -> ErrorHandler:
    """ErrorHandlerのインスタンスを作成する工場関数"""
    error_handler = ErrorHandler(app_state, ui_controls, page)
    app_state["error_handler"] = error_handler
    return error_handler