"""
event_integration.py
EventHubとマネージャー間の連携を行うユーティリティ

既存のマネージャークラスとEventHubを連携させるための機能を提供します。
"""
from typing import Dict, Any, Optional, List
import flet as ft
from event_hub import EventHub, EventType, Event, EventPriority
from managers.event_aware_manager import EventAwareManager

def connect_managers_with_event_hub(
    managers: Dict[str, Any], 
    event_hub: EventHub
) -> None:
    """
    すべてのマネージャーをEventHubと接続します。
    
    Args:
        managers (Dict[str, Any]): マネージャーのディクショナリ
        event_hub (EventHub): EventHubのインスタンス
    """
    for manager_name, manager in managers.items():
        # EventAwareManagerを継承したマネージャーの場合
        if isinstance(manager, EventAwareManager):
            manager.set_event_hub(event_hub)
            print(f"[OK] {manager_name} connected to EventHub")
        else:
            print(f"[WARNING] {manager_name} is not event-aware, skipping connection")

def create_proxy_handlers(
    manager: Any,
    manager_name: str,
    event_hub: EventHub
) -> Dict[str, Any]:
    """
    既存のマネージャーメソッドをイベント発行するプロキシハンドラーに変換します。
    これにより、既存のコードを変更せずにイベント連携が可能になります。
    
    Args:
        manager: 対象のマネージャー
        manager_name (str): マネージャー名
        event_hub (EventHub): EventHubインスタンス
        
    Returns:
        Dict[str, Any]: プロキシハンドラーのディクショナリ
    """
    proxy_handlers = {}
    
    # --- データマネージャーのプロキシハンドラー ---
    if manager_name == "data_manager":
        # load_json_fileのプロキシ
        original_load = getattr(manager, "load_json_file", None)
        if original_load and callable(original_load):
            def load_json_file_proxy(file_path):
                result = original_load(file_path)
                event_hub.publish(
                    EventType.DATA_LOADED, 
                    {"file_path": file_path}, 
                    manager_name
                )
                return result
            proxy_handlers["load_json_file"] = load_json_file_proxy
            
        # save_json_fileのプロキシ
        original_save = getattr(manager, "save_json_file", None)
        if original_save and callable(original_save):
            def save_json_file_proxy(file_path):
                result = original_save(file_path)
                event_hub.publish(
                    EventType.DATA_SAVED, 
                    {"file_path": file_path}, 
                    manager_name
                )
                return result
            proxy_handlers["save_json_file"] = save_json_file_proxy
            
        # update_dataのプロキシ
        original_update = getattr(manager, "update_data", None)
        if original_update and callable(original_update):
            def update_data_proxy(key_path, new_value):
                result = original_update(key_path, new_value)
                event_hub.publish(
                    EventType.DATA_UPDATED, 
                    {"key_path": key_path, "new_value": new_value}, 
                    manager_name
                )
                return result
            proxy_handlers["update_data"] = update_data_proxy
    
    # --- UIStateマネージャーのプロキシハンドラー ---
    elif manager_name == "ui_state_manager":
        # select_nodeのプロキシ
        original_select = getattr(manager, "select_node", None)
        if original_select and callable(original_select):
            def select_node_proxy(node_id):
                result = original_select(node_id)
                event_hub.publish(
                    EventType.NODE_SELECTED, 
                    {"node_id": node_id}, 
                    manager_name
                )
                return result
            proxy_handlers["select_node"] = select_node_proxy
            
        # set_add_modeのプロキシ
        original_set_add = getattr(manager, "set_add_mode", None)
        if original_set_add and callable(original_set_add):
            def set_add_mode_proxy(enabled):
                result = original_set_add(enabled)
                event_hub.publish(
                    EventType.ADD_MODE_CHANGED, 
                    {"enabled": enabled}, 
                    manager_name
                )
                return result
            proxy_handlers["set_add_mode"] = set_add_mode_proxy
    
    # --- 他のマネージャーに対しても同様にプロキシハンドラーを定義 ---
    # ...
    
    return proxy_handlers

def apply_proxy_handlers(manager: Any, proxy_handlers: Dict[str, Any]) -> None:
    """
    マネージャーにプロキシハンドラーを適用します。
    
    Args:
        manager: 対象のマネージャー
        proxy_handlers (Dict[str, Any]): プロキシハンドラーのディクショナリ
    """
    for method_name, proxy_handler in proxy_handlers.items():
        if hasattr(manager, method_name):
            setattr(manager, method_name, proxy_handler)

def setup_event_integration(
    app_instance: Any,
    managers: Dict[str, Any]
) -> EventHub:
    """
    アプリケーション全体のイベント統合をセットアップします。
    
    Args:
        app_instance: FlexiJSONEditorAppインスタンス
        managers (Dict[str, Any]): マネージャーのディクショナリ
        
    Returns:
        EventHub: 設定されたEventHubインスタンス
    """
    # EventHubの作成
    event_hub = create_event_hub()
    
    # アプリ状態にEventHubを保存
    app_instance.app_state["event_hub"] = event_hub
    
    # EventAwareManagerを継承したマネージャーとの連携
    connect_managers_with_event_hub(managers, event_hub)
    
    # 既存のマネージャー用のプロキシハンドラーを作成・適用
    for manager_name, manager in managers.items():
        if not isinstance(manager, EventAwareManager):
            proxy_handlers = create_proxy_handlers(manager, manager_name, event_hub)
            apply_proxy_handlers(manager, proxy_handlers)
    
    # ErrorHandlerにイベントリスナーを設定
    error_handler = managers.get("error_handler")
    if error_handler:
        setup_error_event_listeners(error_handler, event_hub)
    
    # アプリケーション初期化イベントを発行
    event_hub.publish(
        EventType.APP_INITIALIZED,
        {"app_version": "1.0.0"},
        "app",
        EventPriority.HIGH,
        async_mode=False  # 初期化イベントは同期処理
    )
    
    return event_hub

# ErrorHandlerとイベントシステムの連携
def setup_error_event_listeners(error_handler, event_hub: EventHub) -> None:
    """
    ErrorHandlerとEventHubの連携を設定します。
    
    Args:
        error_handler: ErrorHandlerインスタンス
        event_hub (EventHub): EventHubインスタンス
    """
    # APP_ERROR イベントをErrorHandlerで処理するリスナー
    def on_app_error_event(event: Event):
        if event.source == "error_handler":
            return  # 自分が発行したイベントは処理しない（無限ループ防止）
        
        error_data = event.data or {}
        message = error_data.get("error", "アプリケーションエラーが発生しました")
        
        # エラーコンテキスト
        context = error_data.copy()
        if "error" in context:
            del context["error"]
        
        # ErrorHandlerでログに記録
        try:
            from error_handling import AppError, ErrorSeverity, ErrorCategory
            
            app_error = AppError(
                message=message,
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.OTHER,
                context=context
            )
            
            # ログのみ記録（UI表示なし）
            error_handler.handle_error(app_error, show_ui=False)
            
            # エラーログに詳細情報を記録
            if hasattr(error_handler, 'logger'):
                error_handler.logger.error(
                    f"APP_ERROR イベント: {message} (ソース: {event.source})"
                )
        except (ImportError, Exception) as e:
            print(f"エラーイベントのロギングに失敗: {e}")
    
    # 各種エラー関連イベント用のリスナー設定
    event_hub.subscribe(EventType.APP_ERROR, on_app_error_event)
    event_hub.subscribe(EventType.ERROR_FILE_IO, lambda e: _handle_specific_error(e, error_handler, "FILE_IO"))
    event_hub.subscribe(EventType.ERROR_DATA_PROCESSING, lambda e: _handle_specific_error(e, error_handler, "DATA_PROCESSING"))
    event_hub.subscribe(EventType.ERROR_VALIDATION, lambda e: _handle_specific_error(e, error_handler, "VALIDATION"))
    
    # 回復関連イベントのリスナー
    event_hub.subscribe(EventType.ERROR_RECOVERY_ATTEMPTED, lambda e: _log_recovery_event(e, error_handler, "attempted"))
    event_hub.subscribe(EventType.ERROR_RECOVERY_SUCCEEDED, lambda e: _log_recovery_event(e, error_handler, "succeeded"))
    event_hub.subscribe(EventType.ERROR_RECOVERY_FAILED, lambda e: _log_recovery_event(e, error_handler, "failed"))
    
    print("[OK] ErrorHandler connected to EventHub")

def _handle_specific_error(event: Event, error_handler, category_name: str):
    """特定タイプのエラーイベントを処理"""
    if event.source == "error_handler":
        return  # 自分が発行したイベントは処理しない
    
    error_data = event.data or {}
    message = error_data.get("message", f"{category_name}エラーが発生しました")
    
    # エラーをログに記録
    if hasattr(error_handler, 'logger'):
        error_handler.logger.error(
            f"{category_name} エラーイベント: {message} (ソース: {event.source})"
        )

def _log_recovery_event(event: Event, error_handler, status: str):
    """回復関連イベントの処理"""
    error_data = event.data or {}
    message = error_data.get("message", f"エラー回復が{status}されました")
    
    # 回復情報をログに記録
    if hasattr(error_handler, 'logger'):
        log_level = {
            "attempted": "info",
            "succeeded": "info",
            "failed": "warning"
        }.get(status, "info")
        
        getattr(error_handler.logger, log_level)(
            f"エラー回復[{status}]: {message} (ソース: {event.source})"
        )

# イベントハブの作成用のファクトリ関数をインポート
from event_hub import create_event_hub