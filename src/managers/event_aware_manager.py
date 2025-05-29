"""
event_aware_manager.py
EventHubに対応したマネージャー基本クラス

イベント処理機能を持つマネージャークラスの基底クラスを定義します。
"""
from typing import Dict, Any, Optional, Callable
from event_hub import EventHub, EventType, Event, EventPriority

class EventAwareManager:
    """
    EventHubに対応したマネージャーの基底クラス
    
    すべてのマネージャークラスが継承し、EventHubとの連携機能を提供します。
    """
    
    def __init__(
        self,
        app_state: Dict[str, Any],
        ui_controls: Dict[str, Any],
        page,
        manager_name: str,
        event_hub: Optional[EventHub] = None
    ):
        """
        EventAwareManagerを初期化します。
        
        Args:
            app_state (Dict[str, Any]): アプリケーションの状態
            ui_controls (Dict[str, Any]): UIコントロール
            page: アプリケーションのページ
            manager_name (str): マネージャーの名前（イベントソース識別用）
            event_hub (EventHub, optional): イベントハブのインスタンス
        """
        self.app_state = app_state
        self.ui_controls = ui_controls
        self.page = page
        self.manager_name = manager_name
        self.event_hub = event_hub
        
        # サブスクライブしたイベントタイプを追跡
        self._subscribed_events = set()
        
    def set_event_hub(self, event_hub: EventHub) -> None:
        """
        EventHubを設定します。
        
        Args:
            event_hub (EventHub): イベントハブのインスタンス
        """
        # 既存のサブスクリプションがあれば解除
        if self.event_hub:
            for event_type in self._subscribed_events:
                self.event_hub.unsubscribe(event_type, self._event_handler)
            self._subscribed_events.clear()
        
        self.event_hub = event_hub
        
        # サブスクリプションを再設定
        if self.event_hub:
            self._setup_event_subscriptions()
            
    def _setup_event_subscriptions(self) -> None:
        """
        サブスクライブするイベントタイプを設定します。
        サブクラスでオーバーライドして使用します。
        """
        pass
    
    def subscribe_to_event(self, event_type: EventType, handler: Optional[Callable[[Event], None]] = None) -> None:
        """
        イベントタイプにサブスクライブします。
        
        Args:
            event_type (EventType): サブスクライブするイベントタイプ
            handler (Callable, optional): 個別のハンドラー。指定しない場合は共通ハンドラーを使用
        """
        if not self.event_hub:
            return
            
        if handler:
            self.event_hub.subscribe(event_type, handler)
        else:
            self.event_hub.subscribe(event_type, self._event_handler)
            
        self._subscribed_events.add(event_type)
    
    def unsubscribe_from_event(self, event_type: EventType, handler: Optional[Callable[[Event], None]] = None) -> None:
        """
        イベントタイプからサブスクリプションを解除します。
        
        Args:
            event_type (EventType): 解除するイベントタイプ
            handler (Callable, optional): 個別のハンドラー。指定しない場合は共通ハンドラーを使用
        """
        if not self.event_hub:
            return
            
        if handler:
            self.event_hub.unsubscribe(event_type, handler)
        else:
            self.event_hub.unsubscribe(event_type, self._event_handler)
            
        if event_type in self._subscribed_events:
            self._subscribed_events.remove(event_type)
    
    def publish_event(
        self, 
        event_type: EventType, 
        data: Optional[Any] = None,
        priority: EventPriority = EventPriority.NORMAL,
        async_mode: bool = True
    ) -> None:
        """
        イベントを発行します。
        
        Args:
            event_type (EventType): 発行するイベントタイプ
            data (Any, optional): イベントに関連するデータ
            priority (EventPriority, optional): イベントの優先度
            async_mode (bool, optional): 非同期モードで発行するかどうか
        """
        if self.event_hub:
            self.event_hub.publish(
                event_type=event_type,
                data=data,
                source=self.manager_name,
                priority=priority,
                async_mode=async_mode
            )
    
    def _event_handler(self, event: Event) -> None:
        """
        共通イベントハンドラー。
        サブクラスでオーバーライドして使用します。
        
        Args:
            event (Event): 受信したイベント
        """
        # イベントタイプに応じたメソッドを呼び出し
        handler_method_name = f"_handle_{event.event_type.name.lower()}"
        handler = getattr(self, handler_method_name, None)
        
        if handler and callable(handler):
            try:
                handler(event)
            except Exception as e:
                print(f"Error in {self.manager_name} handling event {event.event_type.name}: {e}")
                
    def cleanup(self) -> None:
        """
        マネージャーの終了処理を行います。
        サブスクリプションを解除します。
        """
        if self.event_hub:
            for event_type in self._subscribed_events:
                self.event_hub.unsubscribe(event_type, self._event_handler)
            self._subscribed_events.clear()