"""
event_hub.py
FleDjSONのイベントハブシステムモジュール

各マネージャー間の疎結合な通信を実現するためのPubSubパターンを実装
"""
from typing import Dict, List, Any, Callable, Optional, Set, Union
from enum import Enum, auto
from collections import defaultdict
import threading
import time
import queue

class EventType(Enum):
    """イベントタイプの定義"""
    # データ関連イベント
    DATA_LOADED = auto()          # JSONデータがロードされた
    DATA_SAVED = auto()           # JSONデータが保存された
    DATA_UPDATED = auto()         # データが更新された
    DATA_STRUCTURE_CHANGED = auto() # データ構造が変更された
    TEMPLATE_GENERATED = auto()   # テンプレートが生成された
    
    # ノード関連イベント
    NODE_SELECTED = auto()        # ノードが選択された
    NODE_ADDED = auto()           # ノードが追加された
    NODE_DELETED = auto()         # ノードが削除された
    NODE_MOVED = auto()           # ノードが移動された
    NODE_UPDATED = auto()         # ノードのデータが更新された
    NODE_EXPANDED = auto()        # ノードが展開された
    NODE_COLLAPSED = auto()       # ノードが折りたたまれた
    
    # UI状態関連イベント
    UI_STATE_CHANGED = auto()     # UI状態が変更された
    TREE_VIEW_UPDATED = auto()    # ツリービューが更新された
    DETAIL_FORM_UPDATED = auto()  # 詳細フォームが更新された
    SEARCH_PERFORMED = auto()     # 検索が実行された
    SEARCH_RESULTS_UPDATED = auto() # 検索結果が更新された
    
    # モード関連イベント
    ADD_MODE_CHANGED = auto()     # 追加モードが変更された
    EDIT_MODE_CHANGED = auto()    # 編集モードが変更された
    DRAG_MODE_CHANGED = auto()    # ドラッグモードが変更された
    
    # アプリケーション状態イベント
    APP_INITIALIZED = auto()      # アプリケーションが初期化された
    APP_ERROR = auto()            # エラーが発生した
    APP_BUSY = auto()             # アプリケーションがビジー状態になった
    APP_IDLE = auto()             # アプリケーションがアイドル状態になった
    LANGUAGE_CHANGED = auto()     # 言語が変更された
    
    # エラー関連イベント
    ERROR_FILE_IO = auto()        # ファイルI/Oエラー
    ERROR_DATA_PROCESSING = auto() # データ処理エラー
    ERROR_VALIDATION = auto()     # バリデーションエラー
    ERROR_RECOVERY_ATTEMPTED = auto() # エラーからの回復を試行
    ERROR_RECOVERY_SUCCEEDED = auto() # エラーからの回復に成功
    ERROR_RECOVERY_FAILED = auto() # エラーからの回復に失敗

class EventPriority(Enum):
    """イベント優先度の定義"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    HIGHEST = 3  # 最高優先度（致命的エラーなど）

class Event:
    """イベントクラス"""
    def __init__(
        self, 
        event_type: EventType, 
        data: Optional[Any] = None,
        source: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL
    ):
        """
        イベントを初期化します。
        
        Args:
            event_type (EventType): イベントの種類
            data (Any, optional): イベントに関連するデータ
            source (str, optional): イベント発生元の識別子
            priority (EventPriority, optional): イベントの優先度
        """
        self.event_type = event_type
        self.data = data
        self.source = source
        self.priority = priority
        self.timestamp = time.time()

    def __lt__(self, other):
        """優先度キュー用の比較演算子"""
        if not isinstance(other, Event):
            return NotImplemented
        return self.priority.value > other.priority.value

class EventHub:
    """
    イベントハブクラス
    
    PubSubパターンに基づくイベント配信システムを提供します。
    各マネージャーが発行したイベントを、そのイベントにサブスクライブしている
    他のマネージャーに配信します。
    """
    
    def __init__(self):
        """EventHubを初期化します。"""
        # イベントタイプごとのサブスクライバーリスト
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = defaultdict(list)
        
        # イベントフィルター（特定のソースからのイベントを除外するため）
        self._source_filters: Dict[EventType, Set[str]] = defaultdict(set)
        
        # 非同期処理用のスレッドとキュー
        self._event_queue = queue.PriorityQueue()  # 優先度付きキュー
        self._running = False
        self._thread = None
        
        # イベント履歴（デバッグ用）
        self._event_history: List[Event] = []
        self._max_history_size = 100
        self._debug_mode = False

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """
        指定されたイベントタイプにコールバック関数をサブスクライブします。
        
        Args:
            event_type (EventType): サブスクライブするイベントタイプ
            callback (Callable): イベント発生時に呼び出されるコールバック関数
        """
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """
        指定されたイベントタイプからコールバック関数のサブスクリプションを解除します。
        
        Args:
            event_type (EventType): サブスクリプションを解除するイベントタイプ
            callback (Callable): 解除するコールバック関数
        """
        if event_type in self._subscribers and callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)
            
            # サブスクライバーリストが空になった場合は項目を削除
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]

    def unsubscribe_all(self, event_type: Optional[EventType] = None) -> None:
        """
        すべてのサブスクリプションを解除します。
        
        Args:
            event_type (EventType, optional): 解除するイベントタイプ。None の場合はすべて解除。
        """
        if event_type:
            if event_type in self._subscribers:
                del self._subscribers[event_type]
        else:
            self._subscribers.clear()

    def add_source_filter(self, event_type: EventType, source: str) -> None:
        """
        特定のソースからのイベントをフィルタリングします。
        
        Args:
            event_type (EventType): フィルタリングするイベントタイプ
            source (str): フィルタリングするソース識別子
        """
        self._source_filters[event_type].add(source)

    def remove_source_filter(self, event_type: EventType, source: str) -> None:
        """
        ソースフィルターを削除します。
        
        Args:
            event_type (EventType): フィルター解除するイベントタイプ
            source (str): フィルター解除するソース識別子
        """
        if event_type in self._source_filters and source in self._source_filters[event_type]:
            self._source_filters[event_type].remove(source)
            
            # フィルターリストが空になった場合は項目を削除
            if not self._source_filters[event_type]:
                del self._source_filters[event_type]

    def publish(
        self, 
        event_type: EventType, 
        data: Optional[Any] = None,
        source: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL,
        async_mode: bool = True
    ) -> None:
        """
        イベントを配信します。
        
        Args:
            event_type (EventType): 配信するイベントタイプ
            data (Any, optional): イベントに関連するデータ
            source (str, optional): イベント発生元の識別子
            priority (EventPriority, optional): イベントの優先度
            async_mode (bool, optional): 非同期モードで配信するかどうか
        """
        # イベントオブジェクトを作成
        event = Event(event_type, data, source, priority)
        
        # デバッグモードの場合はイベント履歴に追加
        if self._debug_mode:
            self._add_to_history(event)
        
        if async_mode and self._running:
            # 非同期モードならキューに追加
            self._event_queue.put(event)
        else:
            # 同期モードなら直接配信
            self._dispatch_event(event)

    def _dispatch_event(self, event: Event) -> None:
        """
        イベントをサブスクライバーに配信します。
        
        Args:
            event (Event): 配信するイベント
        """
        # ソースフィルターをチェック
        if (event.event_type in self._source_filters and 
            event.source in self._source_filters[event.event_type]):
            return
        
        # サブスクライバーが存在しない場合は何もしない
        if event.event_type not in self._subscribers:
            return
            
        # すべてのサブスクライバーにイベントを配信
        for callback in self._subscribers[event.event_type]:
            try:
                callback(event)
            except Exception as e:
                print(f"EventHub: Error in subscriber callback: {e}")
                # エラーイベントを発行
                if event.event_type != EventType.APP_ERROR:  # 無限ループ防止
                    self.publish(
                        EventType.APP_ERROR, 
                        {"error": str(e), "original_event": event.event_type},
                        "event_hub",
                        EventPriority.HIGH,
                        False  # 同期モードでエラーを発行
                    )

    def _event_processor(self) -> None:
        """イベント処理スレッドのメインループ"""
        while self._running:
            try:
                # キューからイベントを取得（タイムアウト付き）
                event = self._event_queue.get(timeout=0.1)
                self._dispatch_event(event)
                self._event_queue.task_done()
            except queue.Empty:
                # タイムアウト - 次のループへ
                continue
            except Exception as e:
                print(f"EventHub: Error in event processor: {e}")

    def start(self) -> None:
        """イベント処理スレッドを開始します。"""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(
                target=self._event_processor, 
                daemon=True,
                name="EventHubProcessor"
            )
            self._thread.start()
            print("[OK] EventHub: Event processor started")

    def stop(self) -> None:
        """イベント処理スレッドを停止します。"""
        if self._running:
            self._running = False
            if self._thread:
                self._thread.join(timeout=1.0)
                self._thread = None
            print("[OK] EventHub: Event processor stopped")

    def is_running(self) -> bool:
        """イベント処理スレッドが実行中かどうかを返します。"""
        return self._running

    def set_debug_mode(self, enabled: bool, max_history_size: int = 100) -> None:
        """
        デバッグモードを設定します。
        
        Args:
            enabled (bool): デバッグモードを有効にするかどうか
            max_history_size (int, optional): 履歴の最大サイズ
        """
        self._debug_mode = enabled
        self._max_history_size = max_history_size
        
        # デバッグモードを無効にする場合は履歴をクリア
        if not enabled:
            self._event_history.clear()

    def _add_to_history(self, event: Event) -> None:
        """イベント履歴に追加します。"""
        self._event_history.append(event)
        
        # 履歴サイズが上限を超えた場合は古いものを削除
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]

    def get_event_history(self) -> List[Dict[str, Any]]:
        """
        イベント履歴を取得します。
        
        Returns:
            List[Dict[str, Any]]: イベント履歴のリスト
        """
        return [
            {
                "type": event.event_type.name,
                "data": event.data,
                "source": event.source,
                "priority": event.priority.name,
                "timestamp": event.timestamp
            }
            for event in self._event_history
        ]

    def clear_event_history(self) -> None:
        """イベント履歴をクリアします。"""
        self._event_history.clear()


def create_event_hub() -> EventHub:
    """
    EventHubのシングルトンインスタンスを作成します。
    
    Returns:
        EventHub: EventHubのインスタンス
    """
    event_hub = EventHub()
    event_hub.start()  # 自動的にイベント処理スレッドを開始
    return event_hub