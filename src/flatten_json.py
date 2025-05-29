"""
flatten_json.py
ネストされたJSON構造を平坦化する関数モジュール
"""
import json
from typing import Dict, List, Any, Tuple, Optional, Union

def flatten_nested_json(data: Union[Dict, List], id_key: str = "id", children_key: str = "children") -> List[Dict]:
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
                        flatten_object(value, f"{item[id_key]}.{key}", result, id_key, children_key, parent_id=item[id_key])
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
                                    flatten_object(sub_value, f"{child_id}.{sub_key}", result, id_key, children_key, parent_id=child_id)
                                elif isinstance(sub_value, list) and all(isinstance(i, dict) for i in sub_value):
                                    flatten_array(sub_value, f"{child_id}.{sub_key}", result, id_key, children_key, parent_id=child_id)
                        
                        # 親オブジェクトに子ID配列を追加
                        if children_ids:
                            item[children_key] = children_ids
            else:
                # 辞書型でない要素は無視
                continue
    # 単一の辞書型オブジェクトの場合
    elif isinstance(data, dict):
        # ルートオブジェクト
        root_obj = data.copy()
        if id_key not in root_obj:
            root_obj[id_key] = "root"
        result.append(root_obj)
        
        # 子要素を再帰的に処理
        for key, value in data.items():
            if isinstance(value, dict):
                flatten_object(value, f"root.{key}", result, id_key, children_key, parent_id="root")
            elif isinstance(value, list) and all(isinstance(i, dict) for i in value):
                children_ids = flatten_array(value, f"root.{key}", result, id_key, children_key, parent_id="root")
                if children_ids:
                    root_obj[children_key] = children_ids
    
    return result

def flatten_object(obj: Dict, path: str, result: List[Dict], id_key: str, children_key: str, parent_id: Optional[str] = None) -> str:
    """
    ネストされた辞書型オブジェクトを平坦化し、結果リストに追加する
    
    Args:
        obj: 平坦化する辞書型オブジェクト
        path: 現在のパス（IDとして使用）
        result: 結果を追加するリスト
        id_key: IDフィールドとして使用するキー名
        children_key: 子要素参照フィールドとして使用するキー名
        parent_id: 親オブジェクトのID（あれば）
    
    Returns:
        オブジェクトのID
    """
    obj_copy = obj.copy()
    
    # IDの設定
    if id_key in obj_copy and obj_copy[id_key]:
        # 元のIDがある場合はそれを保持するが、パスも記録しておく
        obj_id = str(obj_copy[id_key])
        obj_copy["_path"] = path  # 内部用にパスも保存
    else:
        # IDがない場合はパスをIDとして使用
        obj_copy[id_key] = path
        obj_id = path
    
    # 子要素を処理
    children_ids = []
    for key, value in obj.items():
        if isinstance(value, dict):
            child_id = flatten_object(value, f"{path}.{key}", result, id_key, children_key, parent_id=obj_id)
            children_ids.append(child_id)
        elif isinstance(value, list) and all(isinstance(i, dict) for i in value):
            child_ids = flatten_array(value, f"{path}.{key}", result, id_key, children_key, parent_id=obj_id)
            if child_ids:
                children_ids.extend(child_ids)
    
    # 子要素があれば子要素リンクを追加
    if children_ids:
        obj_copy[children_key] = children_ids
    
    # 結果リストに追加
    result.append(obj_copy)
    
    return obj_id

def flatten_array(arr: List[Dict], path: str, result: List[Dict], id_key: str, children_key: str, parent_id: Optional[str] = None) -> List[str]:
    """
    辞書型オブジェクトの配列を平坦化し、結果リストに追加する
    
    Args:
        arr: 平坦化する辞書型オブジェクトの配列
        path: 現在のパス
        result: 結果を追加するリスト
        id_key: IDフィールドとして使用するキー名
        children_key: 子要素参照フィールドとして使用するキー名
        parent_id: 親オブジェクトのID（あれば）
    
    Returns:
        配列内の各オブジェクトのIDのリスト
    """
    child_ids = []
    
    for i, item in enumerate(arr):
        if isinstance(item, dict):
            item_copy = item.copy()
            item_path = f"{path}[{i}]"
            
            # IDの設定
            if id_key in item_copy and item_copy[id_key]:
                # 元のIDがある場合はそれを保持するが、パスも記録しておく
                item_id = str(item_copy[id_key])
                item_copy["_path"] = item_path  # 内部用にパスも保存
            else:
                # IDがない場合はパスをIDとして使用
                item_copy[id_key] = item_path
                item_id = item_path
                
            child_ids.append(item_id)
            
            # 子要素を処理
            item_children_ids = []
            for key, value in item.items():
                if isinstance(value, dict):
                    child_id = flatten_object(value, f"{item_path}.{key}", result, id_key, children_key, parent_id=item_id)
                    item_children_ids.append(child_id)
                elif isinstance(value, list) and all(isinstance(x, dict) for x in value):
                    grand_child_ids = flatten_array(value, f"{item_path}.{key}", result, id_key, children_key, parent_id=item_id)
                    if grand_child_ids:
                        item_children_ids.extend(grand_child_ids)
            
            # 子要素があれば子要素リンクを追加
            if item_children_ids:
                item_copy[children_key] = item_children_ids
            
            # 結果リストに追加
            result.append(item_copy)
    
    return child_ids

def try_flatten_json(data: Any) -> Tuple[List[Dict], bool]:
    """
    データ形式を判断し、必要に応じて平坦化する。
    配列形式のJSONの場合はそのまま返し、オブジェクト形式の場合は平坦化を試みる。
    
    Args:
        data: 評価・変換するJSONデータ
    
    Returns:
        (変換後のデータ, 変換が行われたかどうか)
    """
    # データが配列で、各要素が辞書型の場合は既に適切な形式
    if isinstance(data, list) and all(isinstance(item, dict) for item in data if item is not None):
        # IDキーの存在確認
        sample_size = min(5, len(data))
        sample_items = data[:sample_size]
        
        # サンプルアイテムから一般的なIDキーを探す
        common_id_keys = ["id", "_id", "ID", "uuid", "key"]
        for key in common_id_keys:
            if all(key in item for item in sample_items if item is not None):
                # 全てのサンプルアイテムに共通のIDキーがあれば、既存フォーマットとみなす
                return data, False
        
        # IDキーが見つからなければ、平坦化処理を試行
        return flatten_nested_json(data), True
        
    # オブジェクト形式の場合は平坦化
    elif isinstance(data, dict):
        return flatten_nested_json(data), True
    
    # その他の形式（非サポート）
    return data, False

def analyze_nested_structure(data: Any) -> Dict:
    """
    ネストされたJSON構造を分析し、推定されるID/子要素キーなどの情報を返す
    
    Args:
        data: 分析するJSONデータ
    
    Returns:
        分析結果を含む辞書
    """
    result = {
        "format": "unknown",
        "id_keys": [],
        "children_keys": [],
        "has_nested_objects": False,
        "has_nested_arrays": False,
        "depth": 0,
        "estimated_node_count": 0
    }
    
    if isinstance(data, list):
        result["format"] = "array"
        result["estimated_node_count"] = len(data)
        
        # 最初の数アイテムをサンプリング
        sample_size = min(5, len(data))
        sample_items = data[:sample_size]
        
        # 共通フィールドを特定
        common_fields = set()
        id_candidates = ["id", "_id", "ID", "uuid", "key", "identifier"]
        children_candidates = ["children", "child", "childNodes", "items", "subitems", "nodes", "elements"]
        
        # 最初のアイテムのフィールドで初期化
        if sample_items and isinstance(sample_items[0], dict):
            common_fields = set(sample_items[0].keys())
            
            # 残りのアイテムで共通フィールドを絞り込む
            for item in sample_items[1:]:
                if isinstance(item, dict):
                    common_fields &= set(item.keys())
        
        # ID候補とchildren候補を特定
        for field in common_fields:
            if field.lower() in [k.lower() for k in id_candidates]:
                result["id_keys"].append(field)
            if field.lower() in [k.lower() for k in children_candidates]:
                result["children_keys"].append(field)
        
        # ネストの分析
        for item in sample_items:
            if isinstance(item, dict):
                for key, value in item.items():
                    if isinstance(value, dict):
                        result["has_nested_objects"] = True
                    elif isinstance(value, list) and any(isinstance(x, dict) for x in value):
                        result["has_nested_arrays"] = True
        
    elif isinstance(data, dict):
        result["format"] = "object"
        result["estimated_node_count"] = count_nested_objects(data)
        
        # オブジェクト内のネスト状況を分析
        stack = [(data, 0)]  # (object, depth)
        max_depth = 0
        
        while stack:
            obj, depth = stack.pop()
            max_depth = max(max_depth, depth)
            
            for key, value in obj.items():
                if isinstance(value, dict):
                    result["has_nested_objects"] = True
                    stack.append((value, depth + 1))
                elif isinstance(value, list) and any(isinstance(x, dict) for x in value):
                    result["has_nested_arrays"] = True
                    for item in value:
                        if isinstance(item, dict):
                            stack.append((item, depth + 1))
        
        result["depth"] = max_depth
    
    return result

def count_nested_objects(data: Any, count: int = 0) -> int:
    """
    ネストされたオブジェクトの総数をカウントする
    
    Args:
        data: カウント対象のデータ
        count: 現在のカウント値（再帰用）
    
    Returns:
        ネストされたオブジェクトの総数
    """
    if isinstance(data, dict):
        count += 1
        for key, value in data.items():
            if isinstance(value, dict):
                count = count_nested_objects(value, count)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        count = count_nested_objects(item, count)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                count = count_nested_objects(item, count)
    
    return count