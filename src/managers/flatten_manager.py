"""
flatten_manager.py
ネストされたJSON構造の平坦化を担当するマネージャークラス

FleDjSONのJSON構造変換を担当し、ネストされたJSONを平坦な配列形式に変換します。
"""
import json
from typing import Dict, List, Any, Tuple, Optional, Union

# EventAwareManagerを継承
try:
    from .event_aware_manager import EventAwareManager
except ImportError:
    # フォールバック用の基底クラス
    class EventAwareManager:
        def __init__(self, app_state, ui_controls, page=None, event_hub=None):
            self.app_state = app_state
            self.ui_controls = ui_controls
            self.page = page
            self.event_hub = event_hub


class FlattenManager(EventAwareManager):
    """
    JSON構造の平坦化を担当するマネージャークラス
    
    ネストされたJSONオブジェクトを、FleDjSONが期待する平坦な配列形式に変換します。
    
    Attributes:
        app_state (Dict): アプリケーションの状態を保持する辞書
        ui_controls (Dict): UIコントロールを保持する辞書
        page (ft.Page): Fletページオブジェクト
        event_hub: イベントハブインスタンス
    """
    
    def __init__(self, app_state: Dict[str, Any], ui_controls: Dict[str, Any], page=None, event_hub=None):
        """
        FlattenManagerを初期化します
        
        Args:
            app_state: アプリケーション状態辞書
            ui_controls: UIコントロール辞書
            page: Fletページオブジェクト（オプション）
            event_hub: イベントハブ（オプション）
        """
        super().__init__(app_state, ui_controls, page, event_hub)
        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] FlattenManager initialized")

    def flatten_nested_json(self, data: Union[Dict, List], id_key: str = "id", children_key: str = "children") -> List[Dict]:
        """
        ネストされた辞書型JSONオブジェクトを、このアプリケーションが期待する平坦な配列形式に変換する
        
        Args:
            data: 変換対象のネストされたJSON（辞書または配列）
            id_key: IDフィールドとして使用するキー名
            children_key: 子要素参照フィールドとして使用するキー名
        
        Returns:
            平坦化されたオブジェクト配列
        """
        result = []
        
        # データが既にリスト形式の場合は、そのまま処理
        if isinstance(data, list):
            # 各アイテムを処理（それぞれが辞書型オブジェクトであることを期待）
            for item in data:
                if isinstance(item, dict):
                    # アイテムにIDキーがなければ追加
                    if id_key not in item:
                        item[id_key] = f"auto_{len(result)}"
                    
                    result.append(item.copy())
                    
                    # ネストされた子オブジェクトがあれば再帰的に処理
                    for key, value in item.items():
                        if isinstance(value, dict):
                            self._flatten_object(value, f"{item[id_key]}.{key}", result, id_key, children_key, parent_id=item[id_key])
                        elif isinstance(value, list) and all(isinstance(i, dict) for i in value):
                            # 配列内の各辞書を処理
                            children_ids = []
                            for i, child in enumerate(value):
                                child_id = f"{item[id_key]}.{key}[{i}]"
                                child_copy = child.copy()
                                if id_key not in child_copy:
                                    child_copy[id_key] = child_id
                                children_ids.append(child_copy[id_key])
                                result.append(child_copy)
                                
                                # さらにネストされた構造があれば再帰的に処理
                                for sub_key, sub_value in child.items():
                                    if isinstance(sub_value, dict):
                                        self._flatten_object(sub_value, f"{child_copy[id_key]}.{sub_key}", result, id_key, children_key, parent_id=child_copy[id_key])
                                    elif isinstance(sub_value, list) and all(isinstance(si, dict) for si in sub_value):
                                        # さらにネストされた配列も処理
                                        for j, sub_item in enumerate(sub_value):
                                            sub_item_id = f"{child_copy[id_key]}.{sub_key}[{j}]"
                                            sub_item_copy = sub_item.copy()
                                            if id_key not in sub_item_copy:
                                                sub_item_copy[id_key] = sub_item_id
                                            result.append(sub_item_copy)
                            
                            # 元のアイテムに子要素のIDのリストを設定
                            if children_ids:
                                item[children_key] = children_ids
            
        else:
            # データが単体の辞書オブジェクトの場合
            result = self._flatten_single_object(data, id_key, children_key)
        
        return result

    def _flatten_object(self, obj: Dict, obj_id: str, result: List[Dict], id_key: str, children_key: str, parent_id: Optional[str] = None):
        """
        単一のネストされたオブジェクトを平坦化する内部関数
        
        Args:
            obj: 平坦化するオブジェクト
            obj_id: オブジェクトに割り当てるID
            result: 結果リスト（変更される）
            id_key: IDフィールドとして使用するキー名
            children_key: 子要素参照フィールドとして使用するキー名
            parent_id: 親要素のID（オプション）
        """
        flat_obj = obj.copy()
        flat_obj[id_key] = obj_id
        
        if parent_id:
            flat_obj["parent_id"] = parent_id
        
        children_ids = []
        
        # ネストされた構造を探す
        for key, value in list(flat_obj.items()):
            if isinstance(value, dict):
                # ネストされたオブジェクトを見つけた場合、それを別のアイテムとして処理
                child_id = f"{obj_id}.{key}"
                self._flatten_object(value, child_id, result, id_key, children_key, parent_id=obj_id)
                children_ids.append(child_id)
                # 元のオブジェクトからは削除
                del flat_obj[key]
                
            elif isinstance(value, list) and all(isinstance(i, dict) for i in value):
                # 辞書の配列を見つけた場合
                for i, item in enumerate(value):
                    child_id = f"{obj_id}.{key}[{i}]"
                    self._flatten_object(item, child_id, result, id_key, children_key, parent_id=obj_id)
                    children_ids.append(child_id)
                # 元のオブジェクトからは削除
                del flat_obj[key]
        
        # 子要素がある場合は参照を追加
        if children_ids:
            flat_obj[children_key] = children_ids
        
        result.append(flat_obj)

    def _flatten_single_object(self, data: Dict, id_key: str = "id", children_key: str = "children") -> List[Dict]:
        """
        単一のJSONオブジェクトを平坦化する
        
        Args:
            data: 平坦化するJSONオブジェクト
            id_key: IDフィールドとして使用するキー名
            children_key: 子要素参照フィールドとして使用するキー名
        
        Returns:
            平坦化されたオブジェクト配列
        """
        result = []
        
        if not isinstance(data, dict):
            return result
        
        # ルートオブジェクトにIDがない場合は追加
        root_data = data.copy()
        if id_key not in root_data:
            root_data[id_key] = "root"
        
        # ルートオブジェクトから開始して再帰的に平坦化
        self._flatten_object(root_data, root_data[id_key], result, id_key, children_key)
        
        return result

    def try_flatten_json(self, data: Any) -> Tuple[List[Dict], bool]:
        """
        JSONデータの平坦化を試行し、成功の可否も返す
        
        Args:
            data: 平坦化を試行するデータ
        
        Returns:
            (平坦化されたデータ, 平坦化が実際に必要だったかのフラグ)
        """
        try:
            # データが既に平坦な配列形式の場合
            if isinstance(data, list) and all(
                isinstance(item, dict) and not any(
                    isinstance(v, (dict, list)) for v in item.values()
                    if not isinstance(v, str)  # 文字列は除外
                ) for item in data if isinstance(item, dict)
            ):
                return data, False
            
            # 平坦化を実行
            flattened = self.flatten_nested_json(data)
            
            # 平坦化が何らかの変更を行ったかチェック
            if isinstance(data, list) and len(data) == len(flattened):
                # 簡単な比較（完全な比較は重いので）
                was_nested = any(
                    any(isinstance(v, (dict, list)) for v in item.values() if not isinstance(v, str))
                    for item in data if isinstance(item, dict)
                )
                return flattened, was_nested
            
            return flattened, True
            
        except Exception as e:
            print(f"[ERROR] 平坦化に失敗しました: {e}")
            # エラーの場合は元のデータを返す
            return data if isinstance(data, list) else [data] if data else [], False

    def is_nested_structure(self, data: Any) -> bool:
        """
        データがネストされた構造かどうかを判定する
        
        Args:
            data: 判定対象のデータ
        
        Returns:
            ネストされた構造の場合True
        """
        if isinstance(data, dict):
            return any(isinstance(v, (dict, list)) for v in data.values() if not isinstance(v, str))
        elif isinstance(data, list):
            return any(
                isinstance(item, dict) and any(
                    isinstance(v, (dict, list)) for v in item.values() if not isinstance(v, str)
                ) for item in data if isinstance(item, dict)
            )
        return False

    def estimate_flattened_size(self, data: Any) -> int:
        """
        平坦化後のおおよそのサイズを推定する
        
        Args:
            data: サイズを推定するデータ
        
        Returns:
            推定されるサイズ
        """
        if isinstance(data, list):
            total = 0
            for item in data:
                if isinstance(item, dict):
                    total += self._count_nested_objects(item)
            return total
        elif isinstance(data, dict):
            return self._count_nested_objects(data)
        return 0

    def _count_nested_objects(self, obj: Dict, count: int = 1) -> int:
        """
        ネストされたオブジェクトの数を再帰的にカウントする
        
        Args:
            obj: カウント対象のオブジェクト
            count: 現在のカウント
        
        Returns:
            ネストされたオブジェクトの総数
        """
        for value in obj.values():
            if isinstance(value, dict):
                count += self._count_nested_objects(value, 1)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        count += self._count_nested_objects(item, 1)
        return count


def create_flatten_manager(app_state: Dict[str, Any], ui_controls: Dict[str, Any], page=None, event_hub=None) -> FlattenManager:
    """FlattenManagerのインスタンスを作成する工場関数"""
    flatten_manager = FlattenManager(app_state, ui_controls, page, event_hub)
    app_state["flatten_manager"] = flatten_manager
    return flatten_manager