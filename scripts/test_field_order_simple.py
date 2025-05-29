"""
シンプルなフィールド順序保持テスト
"""
import json
import re

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

def main():
    """メイン処理"""
    print("フィールド順序保持のシンプルテスト\n")
    
    # テストデータの入力（入力順序）
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
    
    # キーのソート
    print("\n===== 改良前のソート (階層優先) =====")
    original_sort = sorted(inputs, key=lambda x: (x.count('.'), x.count('['), x))
    for key in original_sort:
        print(key)
    
    # 改良版ソート（入力順序優先、階層も考慮）
    print("\n===== 改良版ソート (入力順優先) =====")
    
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
    
    # 実際の辞書データでのテスト
    print("\n===== 実際のJSONデータでの順序テスト =====")
    
    # テストデータ作成
    test_data = {}
    for key in inputs:
        # ネストされたキーを処理
        if '.' in key:
            parts = key.split('.')
            parent = parts[0]
            child = parts[1]
            if parent not in test_data:
                test_data[parent] = {}
            test_data[parent][child] = f"値 {key}"
        # 配列を処理
        elif '[' in key:
            match = re.match(r'^(.+)\[(\d+)\]$', key)
            if match:
                array_name = match.group(1)
                index = int(match.group(2))
                if array_name not in test_data:
                    test_data[array_name] = []
                # 配列の長さを確保
                while len(test_data[array_name]) <= index:
                    test_data[array_name].append(None)
                test_data[array_name][index] = f"値 {key}"
        else:
            test_data[key] = f"値 {key}"
    
    # JSONとして表示
    formatted_json = json.dumps(test_data, indent=2, ensure_ascii=False)
    print(formatted_json)
    
    print("\n===== テスト完了 =====")

if __name__ == "__main__":
    main()