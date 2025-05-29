"""
テスト用のイベントシステムのモックを提供するモジュール。
"""
from enum import Enum, auto
import threading
import time
from queue import PriorityQueue, Empty
from unittest.mock import MagicMock


class EventType(Enum):
    """イベントタイプの定義"""
    # データ関連イベント
    DATA_LOADED = auto()          # JSONデータがロードされた
    DATA_SAVED = auto()           # JSONデータが保存された
    DATA_UPDATED = auto()         # データが更新された
    DATA_STRUCTURE_CHANGED = auto() # データ構造が変更された
    
    # ノード関連イベント
    NODE_SELECTED = auto()        # ノードが選択された
    NODE_ADDED = auto()           # ノードが追加された
    NODE_DELETED = auto()         # ノードが削除された
    NODE_MOVED = auto()           # ノードが移動された
    NODE_DRAGGED = auto()         # ノードがドラッグされた
    NODE_UPDATED = auto()         # ノードのデータが更新された
    NODE_EXPANDED = auto()        # ノードが展開された
    NODE_COLLAPSED = auto()       # ノードが折りたたまれた
    
    # UI状態関連イベント
    UI_STATE_CHANGED = auto()     # UI状態が変更された
    TREE_VIEW_UPDATED = auto()    # ツリービューが更新された
    DETAIL_FORM_UPDATED = auto()  # 詳細フォームが更新された
    SEARCH_REQUESTED = auto()     # 検索が要求された
    SEARCH_PERFORMED = auto()     # 検索が実行された
    SEARCH_RESULTS_UPDATED = auto() # 検索結果が更新された
    FORM_SUBMITTED = auto()       # フォームが送信された
    
    # モード関連イベント
    ADD_MODE_CHANGED = auto()     # 追加モードが変更された
    EDIT_MODE_CHANGED = auto()    # 編集モードが変更された
    DRAG_MODE_CHANGED = auto()    # ドラッグモードが変更された
    
    # アプリケーション状態イベント
    APP_INITIALIZED = auto()      # アプリケーションが初期化された
    APP_ERROR = auto()            # エラーが発生した
    ERROR_OCCURRED = auto()       # エラーが発生した（イベント送信用）
    APP_BUSY = auto()             # アプリケーションがビジー状態になった
    APP_IDLE = auto()             # アプリケーションがアイドル状態になった
    OPERATION_STARTED = auto()    # 操作が開始された
    OPERATION_COMPLETED = auto()  # 操作が完了した
    
    # エラー関連イベント
    ERROR_FILE_IO = auto()        # ファイルI/Oエラー
    ERROR_DATA_PROCESSING = auto() # データ処理エラー
    ERROR_VALIDATION = auto()     # バリデーションエラー
    ERROR_RECOVERY_ATTEMPTED = auto() # エラーからの回復を試行
    ERROR_RECOVERY_SUCCEEDED = auto() # エラーからの回復に成功
    ERROR_RECOVERY_FAILED = auto() # エラーからの回復に失敗


class PriorityLevel(Enum):
    """イベント優先度の定義"""
    LOW = 30       # 低優先度（UI更新など）
    NORMAL = 20    # 通常優先度（データ変更など）
    HIGH = 10      # 高優先度（エラー処理など）
    HIGHEST = 0    # 最高優先度（致命的エラーなど）


class MockEventHub:
    """
    イベントシステムのモック実装。
    パブリッシャー-サブスクライバーパターンでコンポーネント間の通信を行う。
    """
    def __init__(self):
        """
        EventHubを初期化します。
        """
        self.subscribers = {}  # {event_type: [callbacks]}
        self.history = []      # イベント履歴
        self.max_history = 100  # 履歴の最大サイズ
        self.event_queue = PriorityQueue()
        self.is_running = True
        self.process_thread = None
        
        # 非同期処理用のスレッドを開始
        self._start_processing_thread()
    
    def _start_processing_thread(self):
        """イベント処理スレッドを開始する"""
        self.process_thread = threading.Thread(target=self._process_events, daemon=True)
        self.process_thread.start()
    
    def _process_events(self):
        """キューからイベントを処理する"""
        while self.is_running:
            try:
                # イベントを取得（タイムアウト付き）
                priority, event_type, data, timestamp = self.event_queue.get(timeout=0.1)
                
                # イベントの処理
                if event_type in self.subscribers:
                    for callback in self.subscribers[event_type]:
                        try:
                            callback(event_type, data)
                        except Exception as e:
                            print(f"Error in event handler: {e}")
                
                # 履歴に追加
                self.history.append((event_type, data, timestamp))
                
                # 履歴サイズ制限
                if len(self.history) > self.max_history:
                    self.history.pop(0)
                
                # キュー処理完了を通知
                self.event_queue.task_done()
                
            except Empty:
                # タイムアウト - 次のループへ
                pass
            except Exception as e:
                print(f"Error in event processing thread: {e}")
    
    def subscribe(self, event_type, callback):
        """
        イベントタイプに対してコールバック関数を登録します。
        
        Args:
            event_type (EventType): 購読するイベントタイプ
            callback (callable): イベント発生時に呼び出されるコールバック関数
                                  (event_type, data)を引数に取ること
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type, callback):
        """
        イベントタイプに対するコールバック関数の登録を解除します。
        
        Args:
            event_type (EventType): 購読解除するイベントタイプ
            callback (callable): 登録解除するコールバック関数
        """
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
    
    def publish(self, event_type, data=None, priority=PriorityLevel.NORMAL):
        """
        イベントを発行します。
        
        Args:
            event_type (EventType): 発行するイベントタイプ
            data (dict, optional): イベントに関連するデータ
            priority (PriorityLevel, optional): イベントの優先度
        """
        if not isinstance(event_type, EventType):
            raise TypeError(f"event_type must be an instance of EventType, got {type(event_type)}")
        
        if not isinstance(priority, PriorityLevel):
            priority = PriorityLevel.NORMAL
        
        timestamp = time.time()
        self.event_queue.put((priority.value, event_type, data, timestamp))
        
        # テスト用の同期処理
        # イベントが即座に処理されるようにする
        self.event_queue.join()
    
    def get_history(self, limit=None, event_type=None, source=None):
        """
        イベント履歴を取得します。
        
        Args:
            limit (int, optional): 取得する履歴の最大数
            event_type (EventType, optional): フィルタするイベントタイプ
            source (str, optional): フィルタするイベントソース
            
        Returns:
            list: イベント履歴のリスト [(event_type, data, timestamp), ...]
        """
        filtered_history = self.history
        
        # イベントタイプでフィルタ
        if event_type is not None:
            filtered_history = [h for h in filtered_history if h[0] == event_type]
        
        # ソースでフィルタ
        if source is not None:
            filtered_history = [h for h in filtered_history if isinstance(h[1], dict) and h[1].get('source') == source]
        
        # 件数制限
        if limit is not None:
            filtered_history = filtered_history[-limit:]
        
        return filtered_history
    
    def clear_history(self):
        """イベント履歴をクリアします。"""
        self.history = []
    
    def shutdown(self):
        """
        EventHubをシャットダウンします。
        イベント処理スレッドを停止し、リソースを解放します。
        """
        self.is_running = False
        if self.process_thread:
            self.process_thread.join(timeout=1.0)
        self.subscribers = {}
        self.history = []


class MockEventAwareManager:
    """
    イベントシステムを利用するマネージャークラスの基底クラス
    """
    def __init__(self, app_state):
        """
        EventAwareManagerを初期化します。
        
        Args:
            app_state (dict): アプリケーション状態
        """
        self.app_state = app_state
        self.event_hub = app_state.get("event_hub")
        self.subscriptions = {}
    
    def connect_to_event_hub(self):
        """EventHubに接続し、必要なイベントをサブスクライブします。"""
        self.event_hub = self.app_state.get("event_hub")
        if not self.event_hub:
            return
        
        # オーバーライドして特定のイベントをサブスクライブする
        pass
    
    def publish_event(self, event_type, data=None, priority=PriorityLevel.NORMAL):
        """
        イベントを発行します。
        
        Args:
            event_type (EventType): 発行するイベントタイプ
            data (dict, optional): イベントに関連するデータ
            priority (PriorityLevel, optional): イベントの優先度
        """
        if not self.event_hub:
            return
        
        # ソース情報を追加
        if data is None:
            data = {}
        
        if isinstance(data, dict) and "source" not in data:
            data["source"] = self.__class__.__name__
        
        self.event_hub.publish(event_type, data, priority)
    
    def subscribe_to_event(self, event_type, callback):
        """
        イベントをサブスクライブします。
        
        Args:
            event_type (EventType): サブスクライブするイベントタイプ
            callback (callable): イベント発生時に呼び出されるコールバック関数
        """
        if not self.event_hub:
            return
        
        self.event_hub.subscribe(event_type, callback)
        
        # サブスクリプションを追跡
        if event_type not in self.subscriptions:
            self.subscriptions[event_type] = []
        self.subscriptions[event_type].append(callback)
    
    def unsubscribe_from_event(self, event_type, callback):
        """
        イベントのサブスクリプションを解除します。
        
        Args:
            event_type (EventType): サブスクリプションを解除するイベントタイプ
            callback (callable): 解除するコールバック関数
        """
        if not self.event_hub:
            return
        
        self.event_hub.unsubscribe(event_type, callback)
        
        # サブスクリプションのトラッキングを更新
        if event_type in self.subscriptions and callback in self.subscriptions[event_type]:
            self.subscriptions[event_type].remove(callback)
    
    def unsubscribe_all(self):
        """すべてのイベントサブスクリプションを解除します。"""
        if not self.event_hub:
            return
        
        for event_type, callbacks in self.subscriptions.items():
            for callback in callbacks:
                self.event_hub.unsubscribe(event_type, callback)
        
        self.subscriptions = {}


# モジュールのインポート時にモッククラスをシステムに導入
import sys
from unittest.mock import patch, MagicMock

# 実際のモジュールが存在しない場合のために、モックモジュールを作成
if 'fledjson.event_hub' not in sys.modules:
    sys.modules['fledjson.event_hub'] = MagicMock()

# 実際のクラスをモックに置き換える
sys.modules['fledjson.event_hub'].EventType = EventType
sys.modules['fledjson.event_hub'].PriorityLevel = PriorityLevel
sys.modules['fledjson.event_hub'].EventHub = MockEventHub
sys.modules['fledjson.event_hub'].EventAwareManager = MockEventAwareManager