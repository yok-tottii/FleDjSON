"""
optimizations.py
パフォーマンス最適化モジュール

大規模JSONデータの処理パフォーマンスを最適化するためのユーティリティ関数
および最適化されたデータ構造を提供します。
"""
from typing import Dict, List, Any, Optional, Set, Union, Tuple, Callable, Iterator
import json
import time
import gc
import itertools
import functools
import weakref
from collections import defaultdict
import threading
import queue
from translation import get_translation_system

# 翻訳システムを取得
translation_system = get_translation_system()
t = translation_system.t

class LazyJSONLoader:
    """
    大規模JSONファイルを遅延読み込みするためのクラス
    
    巨大なJSONファイルを一度にメモリに読み込まず、
    必要な部分だけを読み込むことでメモリ使用量を削減します。
    """
    
    def __init__(self, file_path: str):
        """
        LazyJSONLoaderを初期化します。
        
        Args:
            file_path (str): 読み込むJSONファイルのパス
        """
        self.file_path = file_path
        self._structure_cache = None
        self._data = None
        self._is_array = None
        self._length = None
        self._metadata = None
        
    def get_structure(self) -> Dict[str, Any]:
        """JSONの構造情報（型、サイズなど）を取得します。"""
        if self._structure_cache is not None:
            return self._structure_cache
            
        # ファイルの基本情報を取得
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                # 先頭の1000バイトだけを読み込んで構造を判断
                start_chunk = f.read(1000)
                
                # 先頭と末尾を確認して配列か辞書かを判断
                stripped = start_chunk.strip()
                is_array = stripped.startswith('[')
                is_object = stripped.startswith('{')
                
                # ファイルサイズを取得
                f.seek(0, 2)  # ファイル末尾に移動
                file_size = f.tell()
                
                # 要素数の概算（配列の場合）
                estimated_items = None
                if is_array:
                    # カンマの数から概算
                    comma_count = start_chunk.count(',')
                    if comma_count > 0:
                        bytes_per_item = len(start_chunk) / (comma_count + 1)
                        estimated_items = int(file_size / bytes_per_item)
                
                self._structure_cache = {
                    "type": "array" if is_array else "object" if is_object else "unknown",
                    "file_size": file_size,
                    "estimated_items": estimated_items,
                    "path": self.file_path
                }
                
                return self._structure_cache
                
        except Exception as e:
            return {
                "error": str(e),
                "path": self.file_path
            }
    
    def load_full(self) -> Any:
        """JSONデータ全体を読み込みます。"""
        if self._data is not None:
            return self._data
            
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
                self._is_array = isinstance(self._data, list)
                self._length = len(self._data) if self._is_array else None
                return self._data
        except Exception as e:
            raise IOError(t("error.json_load_failed").format(error=str(e)))
    
    def load_partial(self, start: int = 0, limit: int = 100) -> List[Any]:
        """
        配列型JSONの一部だけを読み込みます。
        
        Args:
            start (int): 開始インデックス
            limit (int): 読み込む要素数
            
        Returns:
            List[Any]: 指定範囲の要素リスト
        """
        # 構造を確認
        structure = self.get_structure()
        if structure.get("type") != "array":
            raise ValueError("部分読み込みは配列型JSONでのみ対応しています")
            
        try:
            # ストリーミング読み込み
            with open(self.file_path, 'r', encoding='utf-8') as f:
                # 配列の開始を確認
                char = f.read(1).strip()
                if char != '[':
                    raise ValueError("JSONファイルが配列で始まっていません")
                
                # 要素をスキップ
                skipped = 0
                depth = 0
                in_string = False
                escape_next = False
                
                while skipped < start:
                    char = f.read(1)
                    if not char:  # ファイル終端
                        raise IndexError("指定されたインデックスが範囲外です")
                    
                    # 文字列内かどうかを追跡
                    if char == '\\' and not escape_next:
                        escape_next = True
                    elif char == '"' and not escape_next:
                        in_string = not in_string
                    else:
                        escape_next = False
                    
                    # 文字列内でなければネストの深さを追跡
                    if not in_string:
                        if char == '{' or char == '[':
                            depth += 1
                        elif char == '}' or char == ']':
                            depth -= 1
                        elif char == ',' and depth == 1:
                            skipped += 1
                
                # 要素を読み込む
                result = []
                buffer = ""
                item_count = 0
                
                while item_count < limit:
                    char = f.read(1)
                    if not char:  # ファイル終端
                        break
                    
                    buffer += char
                    
                    # 文字列内かどうかを追跡
                    if char == '\\' and not escape_next:
                        escape_next = True
                    elif char == '"' and not escape_next:
                        in_string = not in_string
                    else:
                        escape_next = False
                    
                    # 文字列内でなければネストの深さを追跡
                    if not in_string:
                        if char == '{' or char == '[':
                            depth += 1
                        elif char == '}' or char == ']':
                            depth -= 1
                        elif char == ',' and depth == 1:
                            # 要素の区切り
                            try:
                                element = json.loads(buffer.rstrip(','))
                                result.append(element)
                                item_count += 1
                                buffer = ""
                            except json.JSONDecodeError:
                                buffer = buffer.rstrip(',')
                
                # 最後の要素を処理
                if buffer and item_count < limit:
                    if buffer.rstrip().endswith(']'):
                        buffer = buffer.rstrip().rstrip(']')
                    
                    if buffer:
                        try:
                            element = json.loads(buffer.rstrip(','))
                            result.append(element)
                        except json.JSONDecodeError:
                            pass
                
                return result
                
        except Exception as e:
            raise IOError(t("error.partial_load_failed").format(error=str(e)))
    
    def iter_array(self, chunk_size: int = 100) -> Iterator[Any]:
        """
        配列型JSONを反復処理するためのイテレータを返します。
        
        Args:
            chunk_size (int): 一度に読み込む要素数
            
        Returns:
            Iterator[Any]: JSONの要素を返すイテレータ
        """
        start = 0
        while True:
            chunk = self.load_partial(start, chunk_size)
            if not chunk:
                break
                
            yield from chunk
            start += len(chunk)
            
            # メモリ解放
            gc.collect()
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        JSONファイルのメタデータを取得します。
        
        Returns:
            Dict[str, Any]: メタデータ情報
        """
        if self._metadata is not None:
            return self._metadata
            
        structure = self.get_structure()
        try:
            # サンプリングしてメタデータを収集
            if structure.get("type") == "array":
                # 配列の冒頭、中間、末尾からサンプルを取得
                sample_size = 10
                start_samples = self.load_partial(0, sample_size)
                
                estimated_items = structure.get("estimated_items", 1000)
                mid_start = max(estimated_items // 2 - sample_size // 2, 0)
                mid_samples = []
                try:
                    mid_samples = self.load_partial(mid_start, sample_size)
                except:
                    pass
                
                # 冒頭データから型情報をサンプリング
                field_types = defaultdict(set)
                field_count = defaultdict(int)
                
                for sample in itertools.chain(start_samples, mid_samples):
                    if isinstance(sample, dict):
                        for key, value in sample.items():
                            field_count[key] += 1
                            field_types[key].add(type(value).__name__)
                
                self._metadata = {
                    "field_types": {k: list(v) for k, v in field_types.items()},
                    "field_frequency": {k: v / (len(start_samples) + len(mid_samples)) for k, v in field_count.items()},
                    "sample_size": len(start_samples) + len(mid_samples),
                    "common_fields": [k for k, v in field_count.items() if v > (len(start_samples) + len(mid_samples)) * 0.7]
                }
                
            elif structure.get("type") == "object":
                # オブジェクト全体を読み込んでキーを取得
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    # 先頭の10000バイトだけを読み込んでキーを抽出
                    start_chunk = f.read(10000)
                    # 簡易的な解析（完全ではない）
                    keys = [k.strip('"\'') for k in re.findall(r'"([^"]+)"\s*:', start_chunk)]
                    
                    self._metadata = {
                        "top_level_keys": keys,
                        "approximate": True
                    }
            
            return self._metadata
                
        except Exception as e:
            return {
                "error": str(e),
                "path": self.file_path
            }

class CachedDataManager:
    """
    キャッシュを活用して効率的にデータを管理するクラス
    
    頻繁にアクセスされるデータをキャッシュすることで、
    パフォーマンスを向上させます。
    """
    
    def __init__(self, cache_size: int = 1000):
        """
        CachedDataManagerを初期化します。
        
        Args:
            cache_size (int): キャッシュするアイテム数の上限
        """
        self.cache_size = cache_size
        self._cache = {}
        self._access_count = defaultdict(int)
        self._lock = threading.RLock()
    
    def get(self, key: str, load_func: Callable[[], Any]) -> Any:
        """
        キーに対応するデータをキャッシュから取得します。
        キャッシュになければload_funcを使って取得しキャッシュします。
        
        Args:
            key (str): データのキー
            load_func (Callable[[], Any]): キャッシュミス時に呼び出される関数
            
        Returns:
            Any: キーに対応するデータ
        """
        with self._lock:
            if key in self._cache:
                self._access_count[key] += 1
                return self._cache[key]
                
            # キャッシュにない場合はロード
            value = load_func()
            
            # キャッシュが上限に達していたら、最もアクセス頻度の低いアイテムを削除
            if len(self._cache) >= self.cache_size:
                min_key = min(self._access_count, key=self._access_count.get)
                del self._cache[min_key]
                del self._access_count[min_key]
            
            # 新しいアイテムをキャッシュ
            self._cache[key] = value
            self._access_count[key] = 1
            
            return value
    
    def invalidate(self, key: str) -> None:
        """
        指定されたキーのキャッシュを無効化します。
        
        Args:
            key (str): 無効化するキー
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._access_count[key]
    
    def clear(self) -> None:
        """キャッシュをすべてクリアします。"""
        with self._lock:
            self._cache.clear()
            self._access_count.clear()

class BackgroundProcessor:
    """
    バックグラウンドスレッドで時間のかかる処理を実行するクラス
    
    UIのレスポンシブ性を維持するために、重い処理を
    バックグラウンドスレッドで実行します。
    """
    
    def __init__(self):
        """BackgroundProcessorを初期化します。"""
        self._queue = queue.Queue()
        self._thread = None
        self._running = False
        self._callbacks = {}
    
    def start(self) -> None:
        """バックグラウンドプロセッサを開始します。"""
        if self._thread is not None and self._thread.is_alive():
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """バックグラウンドプロセッサを停止します。"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
    
    def _worker(self) -> None:
        """ワーカースレッドのメインループ"""
        while self._running:
            try:
                # キューからタスクを取得（タイムアウト付き）
                task_id, func, args, kwargs = self._queue.get(timeout=0.1)
                
                try:
                    # タスクを実行
                    result = func(*args, **kwargs)
                    
                    # 結果をコールバックに通知
                    if task_id in self._callbacks:
                        callback, on_error = self._callbacks[task_id]
                        callback(result)
                        del self._callbacks[task_id]
                        
                except Exception as e:
                    # エラーハンドリング
                    if task_id in self._callbacks:
                        _, on_error = self._callbacks[task_id]
                        if on_error:
                            on_error(e)
                        del self._callbacks[task_id]
                        
                self._queue.task_done()
                
            except queue.Empty:
                # タイムアウト - 次のループへ
                continue
    
    def submit(
        self, 
        func: Callable, 
        callback: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        *args, **kwargs
    ) -> str:
        """
        関数をバックグラウンドで実行するためにキューに追加します。
        
        Args:
            func (Callable): 実行する関数
            callback (Callable, optional): 関数が完了したときに呼び出されるコールバック
            on_error (Callable, optional): エラー発生時に呼び出されるコールバック
            *args, **kwargs: 関数に渡される引数
            
        Returns:
            str: タスクID
        """
        task_id = str(time.time()) + str(hash(func))
        
        if callback or on_error:
            self._callbacks[task_id] = (callback, on_error)
            
        self._queue.put((task_id, func, args, kwargs))
        
        # プロセッサが実行中でなければ開始
        if not self._running:
            self.start()
            
        return task_id

class TreeOptimizer:
    """
    ツリービューの描画を最適化するクラス
    
    ノードの展開・折りたたみ状態を追跡し、
    必要な部分だけを更新することでパフォーマンスを向上させます。
    """
    
    def __init__(self, ui_controls, app_state):
        """
        TreeOptimizerを初期化します。
        
        Args:
            ui_controls: UIコントロールの辞書
            app_state: アプリケーションの状態
        """
        self.ui_controls = ui_controls
        self.app_state = app_state
        self.expanded_nodes = weakref.WeakSet()
        self.visible_nodes = set()
        self.node_heights = {}
        self.node_depths = {}
        self.viewport_start = 0
        self.viewport_end = 0
        self.total_node_count = 0
    
    def initialize(self, root_ids, all_nodes):
        """
        ツリー構造を初期化します。
        
        Args:
            root_ids (List): ルートノードのIDリスト
            all_nodes (Dict): すべてのノードのマップ
        """
        self.root_ids = root_ids
        self.all_nodes = all_nodes
        self.expanded_nodes = set(root_ids)  # 文字列は弱参照できないため通常のsetを使用
        self.total_node_count = len(all_nodes)
        
        # ノードの深さを計算
        self._calculate_node_depths()
        
        # 最初は可視ノードを計算
        self._update_visible_nodes()
    
    def _calculate_node_depths(self):
        """すべてのノードの深さを計算します。"""
        self.node_depths = {}
        
        def calc_depth(node_id, depth):
            self.node_depths[node_id] = depth
            
            # 子ノードの深さを再帰的に計算
            children = self.app_state.get("children_map", {}).get(node_id, [])
            for child_id in children:
                calc_depth(child_id, depth + 1)
        
        # ルートノードから開始
        for root_id in self.root_ids:
            calc_depth(root_id, 0)
    
    def _update_visible_nodes(self):
        """現在表示されるべきノードを計算します。"""
        self.visible_nodes = set()
        
        def add_visible(node_id):
            self.visible_nodes.add(node_id)
            
            # ノードが展開されている場合、子ノードも可視
            if node_id in self.expanded_nodes:
                children = self.app_state.get("children_map", {}).get(node_id, [])
                for child_id in children:
                    add_visible(child_id)
        
        # ルートノードから開始
        for root_id in self.root_ids:
            add_visible(root_id)
    
    def expand_node(self, node_id):
        """
        ノードを展開します。
        
        Args:
            node_id: 展開するノードのID
            
        Returns:
            bool: 更新が必要な場合はTrue
        """
        if node_id in self.expanded_nodes:
            return False
            
        self.expanded_nodes.add(node_id)
        self._update_visible_nodes()
        return True
    
    def collapse_node(self, node_id):
        """
        ノードを折りたたみます。
        
        Args:
            node_id: 折りたたむノードのID
            
        Returns:
            bool: 更新が必要な場合はTrue
        """
        if node_id not in self.expanded_nodes:
            return False
            
        self.expanded_nodes.remove(node_id)
        self._update_visible_nodes()
        return True
    
    def is_node_expanded(self, node_id):
        """ノードが展開されているかどうかを返します。"""
        return node_id in self.expanded_nodes
    
    def is_node_visible(self, node_id):
        """ノードが現在表示されるべきかどうかを返します。"""
        return node_id in self.visible_nodes
    
    def set_viewport(self, start_index, end_index):
        """
        現在のビューポートの範囲を設定します。
        
        Args:
            start_index (int): 最初のインデックス
            end_index (int): 最後のインデックス
        """
        self.viewport_start = max(0, start_index)
        self.viewport_end = min(self.total_node_count, end_index)
    
    def get_viewport_nodes(self):
        """
        現在のビューポートに表示するノードを返します。
        
        Returns:
            List: 表示するノードのIDリスト
        """
        visible_list = sorted(
            self.visible_nodes, 
            key=lambda node_id: (self.node_depths.get(node_id, 0), node_id)
        )
        
        return visible_list[self.viewport_start:self.viewport_end]
    
    def optimize_tree_update(self, force_update=False):
        """
        ツリービューの更新を最適化します。
        
        Args:
            force_update (bool): 強制的に全体を更新するかどうか
            
        Returns:
            bool: 更新が実行された場合はTrue
        """
        if force_update:
            self._update_visible_nodes()
            return True
            
        # 可視ノードを更新
        self._update_visible_nodes()
        
        return True


def memoize(max_size=128, expiration=600):
    """
    関数の結果をキャッシュするデコレータ
    
    Args:
        max_size (int): キャッシュするアイテム数の上限
        expiration (int): キャッシュの有効期間（秒）
    """
    cache = {}
    timestamps = {}
    lock = threading.RLock()
    
    def decorating_function(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(sorted(kwargs.items()))
            
            with lock:
                # 有効期限切れのキャッシュをクリア
                current_time = time.time()
                expired_keys = [k for k, t in timestamps.items() if current_time - t > expiration]
                for k in expired_keys:
                    cache.pop(k, None)
                    timestamps.pop(k, None)
                
                # キャッシュがあればそれを返す
                if key in cache:
                    timestamps[key] = current_time
                    return cache[key]
                
                # キャッシュがなければ関数を実行
                result = func(*args, **kwargs)
                
                # キャッシュが上限に達していたら、最も古いアイテムを削除
                if len(cache) >= max_size:
                    oldest_key = min(timestamps, key=timestamps.get)
                    cache.pop(oldest_key, None)
                    timestamps.pop(oldest_key, None)
                
                # 結果をキャッシュ
                cache[key] = result
                timestamps[key] = current_time
                
                return result
                
        return wrapper
        
    return decorating_function


# 性能測定用のデコレータ
def performance_log(label="Function"):
    """
    関数の実行時間を計測するデコレータ
    
    Args:
        label (str): ログに表示するラベル
    """
    def decorating_function(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            print(f"[TIMER] {label} took {end_time - start_time:.4f} seconds")
            return result
        return wrapper
    return decorating_function