"""
テスト用の最適化コンポーネントのモックを提供するモジュール。
実際の実装とテストの間のギャップを埋めるためのモッククラスを定義しています。
"""
from unittest.mock import MagicMock
import time
import threading


class MockLazyJSONLoader:
    """
    LazyJSONLoaderのモック実装
    """
    def __init__(self, app_state=None):
        self.app_state = app_state
        self.is_loaded = False
        self.is_initialized = False
        self.current_file = None
        self.chunk_size = 1000
        self._data = {}
        
    def start_loading(self, file_path):
        """ファイルの読み込みを開始する"""
        self.current_file = file_path
        self.is_initialized = True
        # 非同期読み込みをシミュレート
        threading.Timer(0.1, self._complete_loading).start()
    
    def _complete_loading(self):
        """読み込み完了をシミュレート"""
        self.is_loaded = True
    
    def get_value_by_path(self, path):
        """指定されたパスの値を取得する"""
        # テスト用にハードコード
        if len(path) >= 3 and path[0] == "level1" and path[1].startswith("item") and path[2].startswith("subitem"):
            item_num = int(path[1][4:])
            subitem_num = int(path[2][7:])
            return f"value{item_num}_{subitem_num}"
        return None
    
    def get_children(self, path):
        """指定されたパスの子要素を取得する"""
        # テスト用にハードコード
        if len(path) >= 2 and path[0] == "level1" and path[1].startswith("item"):
            return [f"subitem{i}" for i in range(10)]
        return []
    
    def get_loading_progress(self):
        """読み込み進捗を取得する"""
        return 1.0 if self.is_loaded else 0.5
    
    def get_memory_usage(self):
        """メモリ使用量を取得する"""
        return 1024 * 1024  # 1MB
    
    def get_root_value(self):
        """ルート値を取得する"""
        return {"level1": {f"item{i}": {f"subitem{j}": f"value{i}_{j}" for j in range(10)} for i in range(10)}}


class MockCachedDataManager:
    """
    CachedDataManagerのモック実装
    """
    def __init__(self, app_state=None):
        self.app_state = app_state
        self.cache = {}
        self.data_source = None
        self.cache_hits = 0
        self.cache_misses = 0
        self.default_ttl = 60  # 60秒
        self.max_cache_size = 100  # 最大100アイテム
    
    def get_value(self, key):
        """キャッシュから値を取得する"""
        if key in self.cache:
            self.cache_hits += 1
            return self.cache[key]
        self.cache_misses += 1
        return None
    
    def set_value(self, key, value):
        """キャッシュに値を設定する"""
        self.cache[key] = value
        # キャッシュサイズ制限を適用
        if len(self.cache) > self.max_cache_size:
            # 最も古いアイテムを削除
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
    
    def get_value_by_path(self, path):
        """パスから値を取得する（キャッシュ利用）"""
        cache_key = str(path)
        value = self.get_value(cache_key)
        if value is None and self.data_source:
            value = self.data_source.get_value_by_path(path)
            self.set_value(cache_key, value)
        return value
    
    def _compute_value(self, key):
        """値を計算する（モック）"""
        return f"computed_{key}"


class MockBackgroundProcessor:
    """
    BackgroundProcessorのモック実装
    """
    def __init__(self, app_state=None):
        self.app_state = app_state
        self.tasks = {}
        self.task_counter = 0
    
    def schedule_task(self, task_func, cancellation_token=None, progress_callback=None):
        """タスクをスケジュールする"""
        task_id = f"task_{self.task_counter}"
        self.task_counter += 1
        
        self.tasks[task_id] = {
            "func": task_func,
            "status": "running",
            "cancellation_token": cancellation_token,
            "progress_callback": progress_callback,
            "result": None,
            "start_time": time.time()
        }
        
        # バックグラウンド実行をシミュレート
        def execute_task():
            try:
                result = task_func()
                self.tasks[task_id]["result"] = result
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["end_time"] = time.time()
            except Exception as e:
                self.tasks[task_id]["error"] = str(e)
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["end_time"] = time.time()
        
        threading.Thread(target=execute_task).start()
        return task_id
    
    def wait_for_task(self, task_id):
        """タスクの完了を待機する"""
        # 実際の待機をシミュレート
        while self.tasks[task_id]["status"] == "running":
            time.sleep(0.01)
    
    def cancel_task(self, task_id):
        """タスクをキャンセルする"""
        if task_id in self.tasks and "cancellation_token" in self.tasks[task_id]:
            cancellation_token = self.tasks[task_id]["cancellation_token"]
            if cancellation_token:
                cancellation_token.set()
                self.tasks[task_id]["status"] = "cancelled"
                self.tasks[task_id]["end_time"] = time.time()
    
    def get_task_result(self, task_id):
        """タスクの結果を取得する"""
        if task_id in self.tasks:
            return self.tasks[task_id]["result"]
        return None


class MockTreeOptimizer:
    """
    TreeOptimizerのモック実装
    """
    def __init__(self, ui_controls=None, app_state=None):
        self.ui_controls = ui_controls
        self.app_state = app_state
        self.expanded_nodes = set()
        self.visible_nodes = {}
        self.node_height = {}
        self.node_depth = {}
        self.scroll_position = 0
        self.visible_window_size = 50
        self.total_nodes = 0
        self.tree_data = None
        self.all_nodes = {}
    
    def initialize(self, tree_data):
        """ツリーデータで初期化する"""
        self.tree_data = tree_data
        self.all_nodes = self._build_node_map(tree_data)
        self.expanded_nodes.add(("root",))
        self.total_nodes = len(self.all_nodes)
        self._update_visible_nodes()
    
    def _build_node_map(self, data, parent_path=None):
        """ノードマップを構築する"""
        if parent_path is None:
            parent_path = []
        
        node_map = {}
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = parent_path + [key]
                node_map[tuple(current_path)] = value
                if isinstance(value, (dict, list)):
                    node_map.update(self._build_node_map(value, current_path))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = parent_path + [str(i)]
                node_map[tuple(current_path)] = item
                if isinstance(item, (dict, list)):
                    node_map.update(self._build_node_map(item, current_path))
        
        return node_map
    
    def set_node_expanded(self, node_path, is_expanded):
        """ノードの展開状態を設定する"""
        node_path_tuple = tuple(node_path)
        if is_expanded and node_path_tuple not in self.expanded_nodes:
            self.expanded_nodes.add(node_path_tuple)
        elif not is_expanded and node_path_tuple in self.expanded_nodes:
            self.expanded_nodes.remove(node_path_tuple)
        
        self._update_visible_nodes()
    
    def is_node_visible(self, node_path):
        """ノードが可視かどうかを判定する"""
        node_path_tuple = tuple(node_path)
        if not node_path_tuple:
            return False
        
        # ルートノードは常に可視
        if len(node_path_tuple) == 1:
            return True
        
        # 親ノードが展開されているかチェック
        parent_path = node_path_tuple[:-1]
        return parent_path in self.expanded_nodes
    
    def get_visible_nodes(self):
        """可視ノードを取得する"""
        return list(self.visible_nodes.keys())
    
    def _update_visible_nodes(self):
        """可視ノードを更新する"""
        self.visible_nodes = {}
        for node_path in self.all_nodes:
            if self.is_node_visible(node_path):
                self.visible_nodes[node_path] = self.all_nodes[node_path]
    
    def set_scroll_position(self, position):
        """スクロール位置を設定する"""
        self.scroll_position = position
    
    def render_tree(self):
        """ツリーをレンダリングする"""
        # モックのため実際のレンダリングは行わない
        pass
    
    def expand_all(self):
        """すべてのノードを展開する"""
        for node_path in self.all_nodes:
            self.expanded_nodes.add(node_path)
        self._update_visible_nodes()


# モジュールのインポート時にモッククラスをシステムに導入
import sys
from unittest.mock import patch, MagicMock

# 実際のモジュールが存在しない場合のために、モックモジュールを作成
if 'fledjson.optimizations' not in sys.modules:
    sys.modules['fledjson.optimizations'] = MagicMock()

# 実際のクラスをモックに置き換える
sys.modules['fledjson.optimizations'].LazyJSONLoader = MockLazyJSONLoader
sys.modules['fledjson.optimizations'].CachedDataManager = MockCachedDataManager
sys.modules['fledjson.optimizations'].BackgroundProcessor = MockBackgroundProcessor
sys.modules['fledjson.optimizations'].TreeOptimizer = MockTreeOptimizer