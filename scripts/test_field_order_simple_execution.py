"""
フィールド順序保持の修正をテストする簡略化されたスクリプト
"""
import os
import sys
import json
import re
from pathlib import Path

# プロジェクトルートへのパスを追加
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 入力順序追跡用の変数
_key_input_order = {}
_input_counter = 0

def _get_key_input_order(key_path):
    """キーパスの入力順序を取得する"""
    if key_path in _key_input_order:
        return _key_input_order[key_path]
    
    # 親パスの入力順序を取得
    parts = key_path.split('.')
    for i in range(len(parts) - 1, 0, -1):
        parent_path = '.'.join(parts[:i])
        if parent_path in _key_input_order:
            return _key_input_order[parent_path] + 0.1
    
    # 配列インデックスの処理
    array_match = re.match(r'^(.+)\[\d+\]$', key_path)
    if array_match:
        array_path = array_match.group(1)
        if array_path in _key_input_order:
            return _key_input_order[array_path] + 0.1
    
    return float('inf')  # 無限大を返して最後にソートされるようにする

def _get_parent_order(key_path):
    """キーパスの親の入力順序を取得する"""
    parts = key_path.split('.')
    array_match = re.match(r'^(.+)\[\d+\]$', key_path)
    
    # 配列の場合
    if array_match and not '.' in key_path:
        base = array_match.group(1)
        if base in _key_input_order:
            return _key_input_order[base]
    
    # 通常の階層構造
    if len(parts) > 1:
        parent = parts[0]
        if parent in _key_input_order:
            return _key_input_order[parent]
    
    return float('inf')

def track_key(key_path):
    """キーの入力順序を記録する"""
    global _input_counter
    _input_counter += 1
    _key_input_order[key_path] = _input_counter
    print(f"記録: {key_path} = {_input_counter}")
    
    # 自動的に親パスも記録
    parts = key_path.split('.')
    if len(parts) > 1:
        parent = parts[0]
        if parent not in _key_input_order:
            _input_counter += 1
            _key_input_order[parent] = _input_counter
            print(f"親自動記録: {parent} = {_input_counter}")
    
    # 配列親パスも記録
    array_match = re.match(r'^(.+)\[\d+\]$', key_path)
    if array_match:
        array_parent = array_match.group(1)
        if array_parent not in _key_input_order:
            _input_counter += 1
            _key_input_order[array_parent] = _input_counter
            print(f"配列親自動記録: {array_parent} = {_input_counter}")

def simulate_order_preservation():
    """
    form_handlersとform_managerで実装されている順序保持ロジックをシミュレート
    """
    print("\n修正後の実装をシミュレート\n")
    
    # 入力順序: id, name, profile, tags, contact (意図的にIDから始めて階層は後ろにする)
    inputs = [
        "id",
        "name", 
        "profile.bio", 
        "profile.age", 
        "tags[0]", 
        "tags[1]", 
        "contact.email", 
        "contact.phone"
    ]
    
    # 入力順序の記録
    print("===== キー入力順序の記録 =====")
    for key in inputs:
        track_key(key)
    
    # 記録された順序の確認
    print("\n===== 記録された入力順序 =====")
    for key, order in _key_input_order.items():
        print(f"{key}: {order}")
    
    # ソート
    print("\n===== 修正後のソート (ID優先 + 入力順) =====")
    
    # キーを階層ごとにグループ化
    root_keys = [k for k in inputs if '.' not in k and '[' not in k]
    nested_keys = [k for k in inputs if '.' in k or '[' in k]
    
    # ルートキーは入力順序だけでソート
    sorted_root_keys = sorted(root_keys, key=lambda x: _get_key_input_order(x))
    
    # ネストされたキーは親の入力順に従ってソートしつつ、同じ親を持つキー同士では階層の浅いものを優先
    sorted_nested_keys = sorted(nested_keys, 
                               key=lambda x: (_get_parent_order(x), x.count('.'), _get_key_input_order(x)))
    
    # 両方を組み合わせる
    sorted_keys = sorted_root_keys + sorted_nested_keys
    
    # IDキーは常に最初に処理する
    id_key = "id"
    if id_key in sorted_keys:
        sorted_keys.remove(id_key)
        sorted_keys.insert(0, id_key)
    
    # 結果表示
    for key in sorted_keys:
        print(key)
    
    # 実際のJSONデータでテスト
    print("\n===== 実際のJSONデータでの順序テスト =====")
    
    # シミュレートするedit_buffer
    edit_buffer = {}
    
    # バッファにデータを入力順に追加
    for key in inputs:
        edit_buffer[key] = f"値 {key}"
    
    # 新規ノード作成をシミュレート
    node_data = {"id": "test_id"} # IDは最初に設定
    
    # ソートしたキーでノードデータを構築
    for key_path in sorted_keys:
        if key_path == "id": # IDは既に設定済み
            continue
            
        # キーパスからノードデータを構築
        if '.' in key_path:
            parts = key_path.split('.')
            parent = parts[0]
            child = parts[1]
            if parent not in node_data:
                node_data[parent] = {}
            node_data[parent][child] = edit_buffer[key_path]
        elif '[' in key_path:
            match = re.match(r'^(.+)\[(\d+)\]$', key_path)
            if match:
                array_name = match.group(1)
                index = int(match.group(2))
                if array_name not in node_data:
                    node_data[array_name] = []
                # 配列の長さを確保
                while len(node_data[array_name]) <= index:
                    node_data[array_name].append(None)
                node_data[array_name][index] = edit_buffer[key_path]
        else:
            node_data[key_path] = edit_buffer[key_path]
    
    # 結果のJSONを表示
    formatted_json = json.dumps(node_data, indent=2, ensure_ascii=False)
    print(f"結果のJSONデータ（ID優先）:\n{formatted_json}")
    
    # 修正が正しく適用されていることを確認
    print("\n===== 修正の確認 =====")
    # 1. IDが最初に来ているか
    first_key = list(node_data.keys())[0]
    if first_key == "id":
        print("✓ IDフィールドが最初に配置されています")
    else:
        print("✗ IDフィールドが最初に配置されていません")
    
    # 2. 子要素が入力順に保存されているか
    if "profile" in node_data and isinstance(node_data["profile"], dict):
        profile_keys = list(node_data["profile"].keys())
        expected_profile_keys = ["bio", "age"]
        if profile_keys == expected_profile_keys:
            print("✓ profileの子要素が入力順に保存されています")
        else:
            print(f"✗ profileの子要素の順序が正しくありません: {profile_keys}")
    
    # 3. ルート要素が入力順に保存されているか（ただしIDは除く）
    root_keys = list(node_data.keys())
    expected_root_keys = ["id", "name", "profile", "tags", "contact"]
    if root_keys == expected_root_keys:
        print("✓ ルート要素が入力順に保存されています")
    else:
        print(f"✗ ルート要素の順序が正しくありません: {root_keys}")
    
    print("\n===== テスト完了 =====")
    return formatted_json

if __name__ == "__main__":
    print("フィールド順序保持の修正テスト")
    simulate_order_preservation()