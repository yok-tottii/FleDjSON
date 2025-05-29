"""
test_complex_file.py
実際の複雑なJSONファイルで平坦化機能をテストする
"""
import unittest
import json
import os
import sys
from pathlib import Path

# プロジェクトのルートパスをsys.pathに追加してインポート可能にする
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.flatten_json import try_flatten_json, analyze_nested_structure

class TestComplexFile(unittest.TestCase):
    
    def setUp(self):
        # 複雑なネストされたJSONファイルのパス
        self.complex_file_path = os.path.join(
            project_root, "docs", "complex_nested_structure.json"
        )
        
        # JSONファイルを読み込む
        with open(self.complex_file_path, "r", encoding="utf-8") as f:
            self.complex_data = json.load(f)
    
    def test_analyze_complex_file(self):
        """複雑なファイルの構造分析をテスト"""
        analysis = analyze_nested_structure(self.complex_data)
        
        # 分析結果の検証
        self.assertEqual(analysis["format"], "object")
        self.assertTrue(analysis["has_nested_objects"])
        self.assertTrue(analysis["has_nested_arrays"])
        self.assertGreater(analysis["depth"], 0)
        self.assertGreater(analysis["estimated_node_count"], 5)
        
        print(f"分析結果: {analysis}")
    
    def test_flatten_complex_file(self):
        """複雑なファイルの平坦化をテスト"""
        flattened_data, was_flattened = try_flatten_json(self.complex_data)
        
        # 平坦化の結果検証
        self.assertTrue(was_flattened)
        self.assertIsInstance(flattened_data, list)
        self.assertGreater(len(flattened_data), 10)
        
        # デバッグ：すべてのオブジェクトのIDと型を出力
        print("\n--- 全ノードのID情報 ---")
        id_values = []
        for node in flattened_data:
            node_id = node.get("id")
            id_values.append(node_id)
            print(f"ID: {node_id} (型: {type(node_id)})")
        
        # ID情報の詳細デバッグ
        print("\n--- ID情報の分析 ---")
        print(f"部署IDを含むノード: {[nid for nid in id_values if isinstance(nid, str) and 'dept' in nid]}")
        
        # 主要なオブジェクトが存在することを確認（IDの前方一致で検索）
        org_obj = next((obj for obj in flattened_data if isinstance(obj.get("id"), str) and "org-" in obj.get("id")), None)
        self.assertIsNotNone(org_obj, "組織オブジェクトが見つかりません")
        
        # 部署オブジェクトの確認（パス名に 'departments' が含まれるものを検索）
        dept_obj = next((obj for obj in flattened_data if "_path" in obj and "departments" in obj["_path"]), None)
        self.assertIsNotNone(dept_obj, "部署オブジェクトが見つかりません")
        
        if dept_obj:
            print(f"\n--- 見つかった部署オブジェクト ---")
            print(f"ID: {dept_obj.get('id')}")
            print(f"パス: {dept_obj.get('_path')}")
            print(f"属性: {[k for k in dept_obj.keys()]}")
        
        # 様々なオブジェクトを検索してみる
        print("\n--- 様々な種類のオブジェクト ---")
        # 本部データ検索
        headquarters = next((obj for obj in flattened_data if "_path" in obj and "headquarters" in obj["_path"]), None)
        if headquarters:
            print(f"本部データ: ID={headquarters.get('id')}, パス={headquarters.get('_path')}")
            
        # 親子関係の確認
        if org_obj and "children" in org_obj:
            print(f"\n--- 組織の子ノード情報 ---")
            children_ids = org_obj.get("children", [])
            print(f"子ノードIDs: {children_ids}")
            
            # 子ノードの詳細
            for child_id in children_ids[:3]:  # 最初の3つのみ表示
                child_node = next((n for n in flattened_data if n.get("id") == child_id), None)
                if child_node:
                    print(f"子ノード {child_id}: {child_node.get('name', '名前なし')}")
        
        # 全ノードの情報出力
        print(f"\n全ノード数: {len(flattened_data)}")
        for i, node in enumerate(flattened_data[:5]):  # 最初の5ノードのみ表示
            print(f"ノード {i}: ID={node.get('id')}, 名前={node.get('name', '名前なし')}")
        
        # 子関係を持つノードの数
        nodes_with_children = [n for n in flattened_data if "children" in n]
        print(f"子ノードを持つノード数: {len(nodes_with_children)}")

if __name__ == "__main__":
    unittest.main()