"""
test_array_copy.py

配列のコピー処理と参照問題のテスト

このスクリプトは、DeepCopyManagerとJSONStructureHandlerが
配列参照問題を正しく解決することを検証します。
"""

import sys
import os
import json
import copy
import unittest
from pathlib import Path

# 親ディレクトリを追加してfledjsonモジュールをインポートできるようにする
sys.path.append(str(Path(__file__).parent.parent))

# DeepCopyManagerとJSONStructureHandlerをインポート
from src.copy_manager import DeepCopyManager, JSONStructureHandler


class TestArrayCopy(unittest.TestCase):
    """配列コピー処理のテストケース"""

    def test_standard_deepcopy_limitation(self):
        """標準のcopy.deepcopyの問題点を示すテスト"""
        # オリジナルデータ
        data = [
            {"id": 1, "name": "Item 1", "tags": ["tag1", "tag2"]},
            {"id": 2, "name": "Item 2"}
        ]
        
        # 普通にdeep_copyを実行
        copied_data = copy.deepcopy(data)
        
        # コピーしたデータの配列を変更
        copied_data[0]["tags"].append("new_tag")
        
        # 元データは影響を受けないことを確認（これは期待通り）
        self.assertEqual(data[0]["tags"], ["tag1", "tag2"])
        self.assertEqual(copied_data[0]["tags"], ["tag1", "tag2", "new_tag"])
        
        # 問題のある状況：辞書にコピーするとき
        data_map = {}
        raw_data = [
            {"id": 1, "name": "Item 1", "tags": ["tag1", "tag2"]},
            {"id": 2, "name": "Item 2"}
        ]
        
        # 辞書に保存
        for item in raw_data:
            data_map[str(item["id"])] = copy.deepcopy(item)
        
        # 保存中のデータを変更
        data_map["1"]["tags"].append("new_tag")
        
        # 保存するために再構築
        ordered_ids = ["1", "2"]
        data_to_save = []
        for node_id in ordered_ids:
            node_data = data_map.get(node_id)
            if node_data:
                # 通常のdeep_copyを使用
                node_data_copy = copy.deepcopy(node_data)
                data_to_save.append(node_data_copy)
        
        # IDごとに元データの更新も行う（通常の処理フロー）
        for i, item in enumerate(raw_data):
            if str(item["id"]) == "1":
                raw_data[i] = copy.deepcopy(data_map["1"])
                
        # 新規のループでテストを実行（実際のコードではショートカットキー保存処理）
        data_to_save_2 = []
        for node_id in ordered_ids:
            node_data = data_map.get(node_id)
            if node_data:
                # 通常のdeep_copyを使用
                node_data_copy = copy.deepcopy(node_data)
                data_to_save_2.append(node_data_copy)
        
        # 問題点：両方のデータが影響を受けている
        self.assertEqual(data_to_save[0]["tags"], ["tag1", "tag2", "new_tag"])
        self.assertEqual(data_to_save[1].get("tags", None), None)
        self.assertEqual(data_to_save_2[0]["tags"], ["tag1", "tag2", "new_tag"])
        self.assertEqual(data_to_save_2[1].get("tags", None), None)

    def test_safe_deep_copy(self):
        """DeepCopyManagerが参照問題を解決することを確認するテスト"""
        # テスト用のDeepCopyManagerを生成
        copy_manager = DeepCopyManager()
        
        # テストデータ
        data = [
            {"id": 1, "name": "Item 1", "tags": ["tag1", "tag2"]},
            {"id": 2, "name": "Item 2"}
        ]
        
        # data_mapの構築
        data_map = {}
        for item in data:
            data_map[str(item["id"])] = copy_manager.safe_deep_copy(item)
        
        # 1つ目のノードに配列要素を追加
        data_map["1"]["tags"].append("new_tag")
        
        # 保存用データの構築
        ordered_ids = ["1", "2"]
        data_to_save = []
        for node_id in ordered_ids:
            node_data = data_map.get(node_id)
            if node_data:
                # 安全なコピーを使用
                node_data_copy = copy_manager.safe_deep_copy(node_data)
                data_to_save.append(node_data_copy)
        
        # data_mapの要素を変更
        data_map["1"]["tags"].append("another_tag")
        
        # 2回目の保存用データ構築
        data_to_save_2 = []
        for node_id in ordered_ids:
            node_data = data_map.get(node_id)
            if node_data:
                # 安全なコピーを使用
                node_data_copy = copy_manager.safe_deep_copy(node_data)
                data_to_save_2.append(node_data_copy)
        
        # 改善点：data_to_saveとdata_map、data_to_save_2は互いに独立している
        self.assertEqual(data_map["1"]["tags"], ["tag1", "tag2", "new_tag", "another_tag"])
        self.assertEqual(data_to_save[0]["tags"], ["tag1", "tag2", "new_tag"])
        self.assertEqual(data_to_save_2[0]["tags"], ["tag1", "tag2", "new_tag", "another_tag"])
        
        # ノード2には影響していないことを確認
        self.assertFalse("tags" in data_map["2"])
        self.assertFalse("tags" in data_to_save[1])
        self.assertFalse("tags" in data_to_save_2[1])

    def test_json_structure_handler(self):
        """JSONStructureHandlerの機能テスト"""
        # テスト用のJSONStructureHandlerを生成
        handler = JSONStructureHandler()
        
        # テストデータ
        raw_data = [
            {"id": 1, "name": "Item 1", "tags": ["tag1", "tag2"]},
            {"id": 2, "name": "Item 2", "children": [{"id": 21, "name": "Child 1"}]}
        ]
        
        # data_mapを再構築
        data_map = handler.rebuild_data_map(raw_data, "id")
        
        # 要素を変更
        data_map["1"]["tags"].append("new_tag")
        
        # 保存用データを構築
        data_to_save = handler.prepare_save_data(data_map, raw_data, "id")
        
        # raw_dataの要素を変更
        raw_data[0]["tags"].append("raw_tag")
        
        # 再度保存用データを構築
        data_to_save_2 = handler.prepare_save_data(data_map, raw_data, "id")
        
        # それぞれのデータが独立していることを確認
        self.assertEqual(raw_data[0]["tags"], ["tag1", "tag2", "raw_tag"])
        self.assertEqual(data_map["1"]["tags"], ["tag1", "tag2", "new_tag"])
        self.assertEqual(data_to_save[0]["tags"], ["tag1", "tag2", "new_tag"])
        self.assertEqual(data_to_save_2[0]["tags"], ["tag1", "tag2", "new_tag"])
        
        # ネストした配列型も正しく処理されていることを確認
        data_map["2"]["children"].append({"id": 22, "name": "Child 2"})
        data_to_save_3 = handler.prepare_save_data(data_map, raw_data, "id")
        
        self.assertEqual(len(data_map["2"]["children"]), 2)
        self.assertEqual(len(data_to_save_3[1]["children"]), 2)
        self.assertEqual(len(raw_data[1]["children"]), 1)


if __name__ == "__main__":
    unittest.main()