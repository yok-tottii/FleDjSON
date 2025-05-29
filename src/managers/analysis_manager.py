"""
analysis_manager.py
JSON構造解析・自動推定関連のマネージャークラス

FleDjSONのJSON解析エンジンを提供する
JSONデータの構造を解析し、データパターンを検出して型や意味を推論する
"""
import json
import os
import re
from collections import defaultdict, Counter
from typing import Any, Dict, List, Tuple, Set, Optional, Union
import flet as ft
from translation import t


class AnalysisManager:
    """
    JSON構造の解析と推論を行うマネージャークラス
    
    JSONデータの構造を解析し、各フィールドの型、出現率、一意性などを推定する
    型推論、ID検出、階層構造分析などの機能を提供する
    
    Attributes:
        app_state (Dict): アプリケーションの状態を保持する辞書
        ui_controls (Dict): UIコントロールを保持する辞書
        page (ft.Page): Fletページオブジェクト
    """
    
    def __init__(self, app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None):
        """
        AnalysisManagerを初期化します。

        Args:
            app_state (Dict): アプリケーションの状態を保持する辞書
            ui_controls (Dict): UIコントロールを保持する辞書
            page (ft.Page, optional): Fletページオブジェクト
        """
        self.app_state = app_state
        self.ui_controls = ui_controls
        self.page = page or app_state.get("page")
        
        # 詳細解析結果を保持するディクショナリ
        self.analysis_cache = {}
        
        # 型推論用パターン辞書
        self.field_type_patterns = {
            'id': r'(^|_)(id|uuid|guid)($|_)',
            'string': r'(^|_)(name|title|label|text|description|caption|message|content)($|_)',
            'number': r'(^|_)(count|number|value|amount|price|score|rating|age|quantity|order)($|_)',
            'boolean': r'(^|_)(is|has|can|should|enabled|active|visible|completed|selected|success)($|_)',
            'date': r'(^|_)(date|time|created|updated|modified|timestamp)($|_)',
            'url': r'(^|_)(url|link|href|path|route)($|_)',
            'email': r'(^|_)(email|mail)($|_)',
            'phone': r'(^|_)(phone|tel|fax|mobile|cell)($|_)',
            'list': r'(^|_)(list|array|items|elements|collection|group|tags)($|_\w*s$)',
            'object': r'(^|_)(data|info|details|settings|config|options|params|properties)($|_)',
        }
        
        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] AnalysisManager initialized.")
    
    def analyze_json_structure(self, file_path: Optional[str] = None, data: Optional[List[Dict]] = None, 
                              full_scan: bool = False, sample_limit: Optional[int] = None) -> Dict:
        """
        JSONデータの構造を解析し、各フィールドの型、出現率、一意性などを推定する
        
        Args:
            file_path: 解析対象のJSONファイルパス（dataパラメータが指定されない場合に使用）
            data: 解析対象のJSONデータ（dict型のリスト）
            full_scan: 全件解析モードを指定するフラグ（Trueの場合はsample_limitを無視）
            sample_limit: 解析するサンプル数の上限（Noneまたはfull_scan=Trueの場合は全件解析）
        
        Returns:
            解析結果を含む辞書
        """
        # ファイルパスが指定された場合は、ファイルからデータを読み込む
        if file_path and not data:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                return {
                    "error": t("error.file_load_failed").format(error=str(e)),
                    "field_details": [],
                    "heuristic_suggestions": {},
                    "id_info": {},
                    "file_path": file_path,
                    "comprehensive_template_data": {}
                }
        
        if not data:
            return {
                "error": "データがありません",
                "field_details": [],
                "heuristic_suggestions": {},
                "id_info": {},
                "file_path": file_path,
                "comprehensive_template_data": {}
            }
        
        # 単一オブジェクトの場合はリストに変換
        if isinstance(data, dict):
            data = [data]
            print("[UPDATE] 単一オブジェクトをリスト形式に変換しました")
        elif not isinstance(data, list):
            return {
                "error": "データ形式が不正です（リストまたはオブジェクトである必要があります）",
                "field_details": [],
                "heuristic_suggestions": {},
                "id_info": {},
                "file_path": file_path,
                "comprehensive_template_data": {}
            }
        
        # サンプリング処理
        total_count = len(data)
        
        # full_scanフラグがTrueの場合は全件解析
        if full_scan:
            sample_data = data
            sample_count = total_count
        elif sample_limit and total_count > sample_limit:
            sample_data = data[:sample_limit]
            sample_count = sample_limit
        else:
            sample_data = data
            sample_count = total_count
        
        # フィールド解析
        field_details = self.analyze_fields(sample_data, sample_count)
        
        # ヒューリスティックによるフィールド意味推定
        heuristic_suggestions = self.suggest_field_roles(field_details, sample_data)
        
        # ID情報の追加
        id_info = {}
        
        # heuristic_suggestionsからidentiferを取得
        if "identifier" in heuristic_suggestions:
            id_field = heuristic_suggestions["identifier"]
            id_info = {
                "field": id_field,
                "auto_increment": self.is_auto_increment_id(sample_data, id_field),
                "format": self.guess_id_format(sample_data, id_field)
            }
        
        # 包括的なテンプレートデータを生成
        comprehensive_template_data = self.generate_comprehensive_template(data, field_details)
        
        # DataManagerが期待する形式に変換
        result = {
            "total_records": total_count,
            "analyzed_records": sample_count,
            "field_details": field_details,
            "heuristic_suggestions": heuristic_suggestions,
            "id_info": id_info,
            "file_path": file_path,
            "comprehensive_template_data": comprehensive_template_data,
            # DataManagerが期待するキー形式を追加
            "id_key": heuristic_suggestions.get("identifier"),
            "label_key": heuristic_suggestions.get("label"),
            "children_key": heuristic_suggestions.get("children") or heuristic_suggestions.get("children_link")
        }
        
        return result
    
    def analyze_fields(self, data: List[Dict], sample_count: int, path_prefix: str = "", 
                      max_depth: int = 3, sample_limit: int = 10) -> List[Dict]:
        """
        サンプルデータの各フィールドを再帰的に解析する
        
        Args:
            data: 解析対象のデータ
            sample_count: サンプル総数
            path_prefix: 現在の階層までのパス（再帰呼び出し時に使用）
            max_depth: 再帰解析の最大深さ
            sample_limit: リスト内のアイテム分析に使用するサンプル数の上限
        
        Returns:
            フィールド詳細情報のリスト
        """
        if not data or max_depth <= 0:
            return []
        
        fields_info = {}
        all_values = defaultdict(list)
        
        # 全サンプルのフィールドと値を収集
        for item in data:
            if not isinstance(item, dict):
                continue
                
            for field_name, field_value in item.items():
                full_path = f"{path_prefix}.{field_name}" if path_prefix else field_name
                all_values[full_path].append(field_value)
        
        field_details = []
        
        # フィールドごとに解析
        for field_path, values in all_values.items():
            field_name = field_path.split(".")[-1] if "." in field_path else field_path
            
            # 出現数と出現率を計算
            occurrence = len(values)
            occurrence_rate = occurrence / sample_count * 100
            
            # 値の型を解析
            types_counter = Counter()
            for value in values:
                type_name = self.get_detailed_type_name(value)
                types_counter[type_name] += 1
            
            # 出現頻度順にソート
            types = [(t, c) for t, c in types_counter.most_common()]
            
            # 一意性を確認
            unique_values = set()
            is_unique = True
            for value in values:
                # リストや辞書は一意性判定から除外
                if isinstance(value, (list, dict)):
                    is_unique = False
                    break
                    
                # 基本型の場合は一意性をチェック
                try:
                    if value in unique_values:
                        is_unique = False
                        break
                    unique_values.add(value)
                except:
                    # ハッシュ不可能な値の場合は一意性なしとみなす
                    is_unique = False
                    break
            
            # フィールド情報を格納
            field_info = {
                "name": field_path,
                "display_name": field_name,
                "occurrence": occurrence,
                "occurrence_rate": occurrence_rate,
                "types": types,
                "is_unique": is_unique,
                "examples": values[:3]  # 最初の3つの値を例として保存
            }
            
            field_details.append(field_info)
            
            # 再帰解析（ネストされた構造があれば）
            if max_depth > 1:
                # dictの子フィールドを解析
                dict_values = [v for v in values if isinstance(v, dict)]
                if dict_values:
                    child_details = self.analyze_fields(dict_values, occurrence, field_path, max_depth - 1, sample_limit)
                    field_details.extend(child_details)
                
                # リストの子要素を解析（最大sample_limit件まで）
                list_values = [v for v in values if isinstance(v, list)]
                if list_values:
                    # リスト内の先頭sample_limit件から中身の型を推定
                    flattened_items = []
                    for lst in list_values[:3]:  # 最初の3つのリストからサンプリング
                        if lst and len(lst) > 0:
                            for item in lst[:sample_limit]:  # 各リストから最大sample_limit件までサンプリング
                                if isinstance(item, dict):
                                    flattened_items.append(item)
                    
                    if flattened_items:
                        list_item_details = self.analyze_fields(flattened_items, len(flattened_items),
                                                          f"{field_path}[]", max_depth - 1, sample_limit)
                        field_details.extend(list_item_details)
        
        return field_details
    
    def suggest_field_roles(self, field_details: List[Dict], sample_data: List[Dict]) -> Dict:
        """
        フィールド解析結果から、識別子、ラベル、子リンクなどの候補を推定する
        
        Args:
            field_details: フィールド詳細情報リスト
            sample_data: サンプルデータ
        
        Returns:
            各役割に対する候補フィールド名
        """
        # スコア計算用の関数
        def calculate_id_score(field: Dict) -> float:
            score = 0.0
            
            # 一意性があればスコア加点
            if field.get("is_unique", False):
                score += 3.0
            
            # 名前による評価 - 多言語対応
            name = field["name"].lower()
            field_original = field["name"]  # 元のフィールド名（日本語対応）
            
            # 英語IDキーワード
            if name == "id":
                score += 3.0
            elif "_id" in name or name.endswith("id"):
                score += 2.0
            elif "uuid" in name or "guid" in name:
                score += 2.5
            elif name in ["key", "identifier", "code", "number", "index"]:
                score += 2.0
            
            # 日本語IDキーワード
            ja_id_keywords = ["識別子", "番号", "コード", "ID", "ＩＤ", "キー", "番号"]
            for keyword in ja_id_keywords:
                if keyword in field_original:
                    score += 3.0
                    break
            
            # 構造的特徴による評価
            structure_score = self._evaluate_field_as_identifier(field)
            score += structure_score
            
            # 出現率が高いほど加点
            occurrence_rate = field.get("occurrence_rate", 0)
            score += min(occurrence_rate / 100, 1.0) * 2.0
            
            return score
        
        def calculate_label_score(field: Dict) -> float:
            score = 0.0
            
            # ラベル候補のフィールド名 - 多言語対応
            name = field["name"].lower()
            field_original = field["name"]  # 元のフィールド名（日本語対応）
            
            # 英語キーワード
            en_label_keywords = ["name", "title", "label", "text", "caption", "heading", "subject", "description"]
            for keyword in en_label_keywords:
                if name == keyword:
                    score += 3.0
                    break
                elif keyword in name:
                    score += 1.5
                    break
            
            # 日本語キーワード
            ja_label_keywords = ["名前", "タイトル", "見出し", "件名", "表題", "氏名", "名称", "ラベル"]
            for keyword in ja_label_keywords:
                if keyword in field_original:
                    score += 3.0
                    break
            
            # 構造的特徴による評価
            structure_score = self._evaluate_field_as_display_label(field)
            score += structure_score
            
            # 文字列型であることが重要
            for type_name, count in field.get("types", []):
                if type_name == "string":
                    score += 1.5
                    break
            
            # 出現率が高いほど加点
            occurrence_rate = field.get("occurrence_rate", 0)
            score += min(occurrence_rate / 100, 1.0) * 1.5
            
            return score
        
        def calculate_children_score(field: Dict) -> float:
            score = 0.0
            
            # 名前が子リンクを示唆 - 多言語対応
            name = field["name"].lower()
            field_original = field["name"]  # 元のフィールド名（日本語対応）
            
            # 英語子リンクキーワード
            en_children_keywords = [
                "children", "child", "next", "sub", "items",
                "nodes", "elements", "members", "parts", "components",
                "descendants", "childnodes", "subitems", "subelements"
            ]
            en_link_keywords = [
                "ids", "links", "refs", "references", "targets",
                "destinations", "pointers", "connections", "relations"
            ]
            
            for keyword in en_children_keywords:
                if name == keyword or name.startswith(keyword):
                    score += 2.0
                    break
                elif keyword in name:
                    score += 1.0
                    break
            
            for keyword in en_link_keywords:
                if name.endswith(keyword):
                    score += 1.5
                    break
                elif keyword in name:
                    score += 0.8
                    break
            
            # 日本語子リンクキーワード
            ja_children_keywords = ["子", "子供", "下位", "項目", "要素", "構成要素", "メンバー"]
            ja_link_keywords = ["リンク", "参照", "関連", "接続", "紐付け"]
            
            for keyword in ja_children_keywords:
                if keyword in field_original:
                    score += 2.0
                    break
            
            for keyword in ja_link_keywords:
                if keyword in field_original:
                    score += 1.5
                    break
            
            # 構造的特徴による評価
            structure_score = self._evaluate_field_as_children_link(field)
            score += structure_score
            
            # 配列型であることが重要
            for type_name, count in field.get("types", []):
                if type_name.startswith("list"):
                    score += 1.5
                    break
            
            # 出現率が高いほど加点
            occurrence_rate = field.get("occurrence_rate", 0)
            score += min(occurrence_rate / 100, 1.0) * 1.0
            
            return score
        
        # 各フィールドのスコアを計算
        id_candidates = [(field["name"], calculate_id_score(field)) for field in field_details if field["name"].count(".") == 0]
        label_candidates = [(field["name"], calculate_label_score(field)) for field in field_details if field["name"].count(".") == 0]
        children_candidates = [(field["name"], calculate_children_score(field)) for field in field_details if field["name"].count(".") == 0]
        
        # スコアの高い順にソート
        id_candidates.sort(key=lambda x: x[1], reverse=True)
        label_candidates.sort(key=lambda x: x[1], reverse=True)
        children_candidates.sort(key=lambda x: x[1], reverse=True)
        
        suggestions = {}
        
        # 各役割に対して最も高いスコアを持つフィールド名を採用
        if id_candidates and id_candidates[0][1] >= 3.0:  # 最低スコアの閾値
            suggestions["identifier"] = id_candidates[0][0]
        
        if label_candidates and label_candidates[0][1] >= 2.0:  # 最低スコアの閾値
            suggestions["label"] = label_candidates[0][0]
        
        if children_candidates and children_candidates[0][1] >= 2.5:  # 最低スコアの閾値
            suggestions["children_link"] = children_candidates[0][0]
        
        return suggestions
    
    def get_detailed_type_name(self, value: Any) -> str:
        """
        値の詳細な型名を取得する
        
        Args:
            value: 型名を取得する値
        
        Returns:
            型名（例: "int", "string", "list[int]" など）
        """
        if value is None:
            return "null"
        
        if isinstance(value, bool):
            return "bool"
        
        if isinstance(value, int):
            return "int"
        
        if isinstance(value, float):
            return "float"
        
        if isinstance(value, str):
            return "string"
        
        if isinstance(value, list):
            if not value:
                return "list[]"  # 空リスト
            
            # リスト内の全ての要素の型をチェック
            element_types = Counter()
            for item in value[:10]:  # 最初の10要素のみサンプリング
                element_types[self.get_detailed_type_name(item)] += 1
            
            # 最も多い型を採用
            if element_types:
                dominant_type = element_types.most_common(1)[0][0]
                return f"list[{dominant_type}]"
            else:
                return "list[]"
        
        if isinstance(value, dict):
            return "dict"
        
        return "unknown"
    
    def is_auto_increment_id(self, data: List[Dict], id_field: str) -> bool:
        """
        IDフィールドが自動インクリメント形式かどうかを判定する
        
        Args:
            data: 分析対象のデータリスト
            id_field: IDフィールド名
        
        Returns:
            自動インクリメント形式と判定された場合はTrue
        """
        # 数値型IDを持つ要素だけを抽出
        numeric_ids = []
        for item in data:
            if id_field in item and isinstance(item[id_field], (int, float)):
                numeric_ids.append(item[id_field])
        
        # 数値型IDが少なすぎる場合は判定不能
        if len(numeric_ids) < 3:
            return False
        
        # IDをソート
        sorted_ids = sorted(numeric_ids)
        
        # 連続する数値かどうかを確認
        # 少なくとも80%のIDが連続していれば自動インクリメントと判定
        consecutive_count = 0
        for i in range(len(sorted_ids) - 1):
            if sorted_ids[i + 1] - sorted_ids[i] == 1:
                consecutive_count += 1
        
        consecutive_rate = consecutive_count / (len(sorted_ids) - 1) if len(sorted_ids) > 1 else 0
        return consecutive_rate >= 0.8
    
    def guess_id_format(self, data: List[Dict], id_field: str) -> str:
        """
        IDフィールドのフォーマットを推測する
        
        Args:
            data: 分析対象のデータリスト
            id_field: IDフィールド名
        
        Returns:
            推測されたIDフォーマット ("numeric", "uuid", "string", "mixed")
        """
        # サンプルIDを収集
        id_samples = []
        for item in data:
            if id_field in item and item[id_field] is not None:
                id_samples.append(item[id_field])
        
        if not id_samples:
            return "unknown"
        
        # 型ごとにカウント
        type_counts = Counter(type(id_val).__name__ for id_val in id_samples)
        
        # 最も多い型を取得
        if type_counts:
            most_common_type = type_counts.most_common(1)[0][0]
            
            # 型に基づいて詳細なフォーマットを判定
            if most_common_type == "int" or most_common_type == "float":
                return "numeric"
            elif most_common_type == "str":
                # 文字列型の場合、UUIDパターンを確認
                uuid_pattern = re.compile(
                    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 
                    re.IGNORECASE
                )
                
                # 最初の10件のみチェック
                sample_size = min(10, len(id_samples))
                uuid_matches = 0
                
                for id_val in id_samples[:sample_size]:
                    if isinstance(id_val, str) and uuid_pattern.match(id_val):
                        uuid_matches += 1
                
                # 80%以上がUUIDパターンに一致すればUUID形式と判定
                if uuid_matches / sample_size >= 0.8:
                    return "uuid"
                else:
                    return "string"
            else:
                return "mixed"
        
        return "unknown"
    
    def _evaluate_field_as_identifier(self, field: Dict) -> float:
        """
        構造的特徴に基づいてフィールドがIDとして適切かを評価
        
        Args:
            field: フィールド詳細情報
            
        Returns:
            IDらしさスコア（0.0-2.0）
        """
        score = 0.0
        
        # フィールド名の短さ（IDは短い傾向）
        name_len = len(field["name"])
        if name_len <= 5:
            score += 1.0
        elif name_len <= 10:
            score += 0.5
        
        # 型の評価
        types = field.get("types", [])
        for type_name, count in types:
            if type_name in ["int", "float"]:
                score += 0.8
            elif type_name == "string":
                score += 0.6
        
        # 値の範囲やパターン（数値の場合）
        if field.get("is_numeric", False):
            value_range = field.get("value_range", {})
            if value_range.get("min", 0) >= 0 and value_range.get("max", 0) < 1000000:
                score += 0.5  # 合理的な範囲内の数値
        
        return min(score, 2.0)
    
    def _evaluate_field_as_display_label(self, field: Dict) -> float:
        """
        構造的特徴に基づいてフィールドが表示ラベルとして適切かを評価
        
        Args:
            field: フィールド詳細情報
            
        Returns:
            表示ラベルらしさスコア（0.0-2.0）
        """
        score = 0.0
        
        # 文字列型であることが重要
        types = field.get("types", [])
        for type_name, count in types:
            if type_name == "string":
                score += 1.0
                break
        
        # フィールド名の長さ（表示名は適度な長さ）
        name_len = len(field["name"])
        if 3 <= name_len <= 15:
            score += 0.5
        elif 16 <= name_len <= 25:
            score += 0.3
        
        # 値の文字数（短すぎず長すぎない文字列が表示名として適切）
        avg_length = field.get("average_length", 0)
        if isinstance(avg_length, (int, float)):
            if 2 <= avg_length <= 50:
                score += 0.5
            elif 51 <= avg_length <= 100:
                score += 0.3
        
        return min(score, 2.0)
    
    def _evaluate_field_as_children_link(self, field: Dict) -> float:
        """
        構造的特徴に基づいてフィールドが子リンクとして適切かを評価  
        
        Args:
            field: フィールド詳細情報
            
        Returns:
            子リンクらしさスコア（0.0-2.0）
        """
        score = 0.0
        
        # 配列型であることが重要
        types = field.get("types", [])
        for type_name, count in types:
            if type_name.startswith("list"):
                score += 1.0
                # リスト要素の型を確認
                if "dict" in type_name:
                    score += 0.5  # オブジェクトの配列
                elif "string" in type_name or "int" in type_name:
                    score += 0.3  # ID参照の配列
                break
        
        # フィールド名の複数形の検出
        name = field["name"].lower()
        if name.endswith('s') or name.endswith('ies') or name.endswith('list'):
            score += 0.5
        
        # 配列サイズの評価（子リンクは通常複数要素）
        avg_length = field.get("average_length", 0)
        if isinstance(avg_length, (int, float)) and avg_length > 1:
            score += 0.5
        
        return min(score, 2.0)

    def generate_comprehensive_template(self, data: List[Dict], field_details: List[Dict]) -> Dict:
        """
        包括的なテンプレートデータを生成する

        データの構造を分析し、フィールドの役割や型、パターンなどの詳細な情報を含む
        テンプレートを生成する

        Args:
            data: 分析対象のデータリスト
            field_details: フィールド詳細情報リスト

        Returns:
            包括的なテンプレートデータを含む辞書
        """
        # オブジェクトの標準的なテンプレートを生成
        template = {}
        pattern_details = {}
        field_purposes = {}
        field_order = []

        # 全データからフィールドの出現頻度を集計
        field_freq = defaultdict(int)
        for item in data:
            if isinstance(item, dict):
                for key in item.keys():
                    field_freq[key] += 1
                    if key not in field_order:
                        field_order.append(key)

        # 頻度の高い順にソート
        common_fields = sorted(field_freq.items(), key=lambda x: x[1], reverse=True)

        # テンプレートと各フィールドの目的を構築
        for field_name, frequency in common_fields:
            # フィールドの型を特定
            field_type = self._determine_field_type(field_name, data)
            
            # テンプレート値を型に基づいて設定
            if field_type == "int":
                template[field_name] = 0
            elif field_type == "float":
                template[field_name] = 0.0
            elif field_type == "bool":
                template[field_name] = False
            elif field_type == "string":
                template[field_name] = ""
            elif field_type == "list":
                # リストのサンプルアイテムを取得
                list_items = [item[field_name] for item in data if isinstance(item, dict) and field_name in item and isinstance(item[field_name], list)]
                if list_items:
                    # リスト内の最初の要素から型を決定
                    sample_items = []
                    for lst in list_items:
                        if lst:  # 空でないリスト
                            sample_items.extend(lst[:2])  # 各リストから最大2アイテムを取得
                            if len(sample_items) >= 5:  # 最大5アイテムまで
                                break
                    
                    if sample_items:
                        item_type = self._determine_list_item_type(sample_items)
                        if item_type == "dict":
                            # 辞書の場合、辞書のテンプレートを作成
                            dict_template = {}
                            for sample in sample_items:
                                if isinstance(sample, dict):
                                    for k, v in sample.items():
                                        if k not in dict_template:
                                            if isinstance(v, dict):
                                                dict_template[k] = {}
                                            elif isinstance(v, list):
                                                dict_template[k] = []
                                            else:
                                                dict_template[k] = self._get_default_value_for_type(type(v))
                                    if dict_template:  # 少なくとも1つのフィールドがあればテンプレート完成
                                        break
                            template[field_name] = [dict_template] if dict_template else []
                            
                            # パターン詳細にも記録
                            pattern_key = f"[0].{field_name}" if field_name not in ["next", "children"] else field_name
                            pattern_details[pattern_key] = dict_template
                            
                            # 入れ子パターンも検出
                            for sample in sample_items:
                                if isinstance(sample, dict):
                                    for k, v in sample.items():
                                        if isinstance(v, list) and v and isinstance(v[0], dict):
                                            nested_key = f"[0].{field_name}[item].{k}"
                                            nested_template = {}
                                            for nested_sample in v[:2]:  # 最大2アイテムをサンプリング
                                                if isinstance(nested_sample, dict):
                                                    for nk, nv in nested_sample.items():
                                                        if nk not in nested_template:
                                                            nested_template[nk] = self._get_default_value_for_type(type(nv))
                                            if nested_template:
                                                pattern_details[nested_key] = nested_template
                        else:
                            # 単純型の場合
                            default_value = self._get_default_value_for_type_name(item_type)
                            template[field_name] = [default_value]
                    else:
                        template[field_name] = []
                else:
                    template[field_name] = []
            elif field_type == "dict":
                # 辞書のサンプルを取得
                dict_items = [item[field_name] for item in data if isinstance(item, dict) and field_name in item and isinstance(item[field_name], dict)]
                if dict_items:
                    # 複数の辞書からマージしたテンプレートを作成
                    dict_template = {}
                    for d in dict_items[:5]:  # 最大5アイテムをサンプリング
                        for k, v in d.items():
                            if k not in dict_template:
                                if isinstance(v, dict):
                                    dict_template[k] = {}
                                elif isinstance(v, list):
                                    dict_template[k] = []
                                else:
                                    dict_template[k] = self._get_default_value_for_type(type(v))
                    template[field_name] = dict_template
                    
                    # パターン詳細にも記録
                    pattern_key = f"[0].{field_name}"
                    pattern_details[pattern_key] = dict_template
                else:
                    template[field_name] = {}
            else:
                template[field_name] = None
            
            # フィールドの目的を特定
            purpose = self._determine_field_purpose(field_name)
            if purpose:
                field_purposes[field_name] = purpose

        return {
            "template": template,
            "field_purposes": field_purposes,
            "pattern_details": pattern_details,
            "field_order": field_order
        }
    
    def _determine_field_type(self, field_name: str, data: List[Dict]) -> str:
        """
        フィールド名とデータからフィールドの型を決定する

        Args:
            field_name: フィールド名
            data: データリスト

        Returns:
            型名（"string", "int", "float", "bool", "list", "dict", "null"）
        """
        # サンプルを収集
        samples = []
        for item in data:
            if isinstance(item, dict) and field_name in item:
                samples.append(item[field_name])
                if len(samples) >= 10:  # 最大10サンプル
                    break
        
        if not samples:
            # フィールド名からのパターンマッチングで型を推測
            field_name_lower = field_name.lower()
            for type_name, pattern in self.field_type_patterns.items():
                if re.search(pattern, field_name_lower):
                    if type_name == 'id':
                        return 'string'  # IDは通常文字列
                    elif type_name == 'list':
                        return 'list'
                    elif type_name == 'object':
                        return 'dict'
                    else:
                        return type_name
            return 'string'  # デフォルトは文字列
        
        # 型カウント
        type_counts = Counter()
        for value in samples:
            if isinstance(value, bool):
                type_counts['bool'] += 1
            elif isinstance(value, int):
                type_counts['int'] += 1
            elif isinstance(value, float):
                type_counts['float'] += 1
            elif isinstance(value, str):
                type_counts['string'] += 1
            elif isinstance(value, list):
                type_counts['list'] += 1
            elif isinstance(value, dict):
                type_counts['dict'] += 1
            elif value is None:
                type_counts['null'] += 1
            else:
                type_counts['unknown'] += 1
        
        # 最も多い型を選択
        if type_counts:
            return type_counts.most_common(1)[0][0]
        
        return 'string'  # デフォルトは文字列
    
    def _determine_list_item_type(self, samples: List[Any]) -> str:
        """
        リストアイテムの型を決定する

        Args:
            samples: サンプルアイテムのリスト

        Returns:
            型名（"string", "int", "float", "bool", "dict", "null"）
        """
        type_counts = Counter()
        for value in samples:
            if isinstance(value, bool):
                type_counts['bool'] += 1
            elif isinstance(value, int):
                type_counts['int'] += 1
            elif isinstance(value, float):
                type_counts['float'] += 1
            elif isinstance(value, str):
                type_counts['string'] += 1
            elif isinstance(value, dict):
                type_counts['dict'] += 1
            elif value is None:
                type_counts['null'] += 1
            else:
                type_counts['unknown'] += 1
        
        # 最も多い型を選択
        if type_counts:
            return type_counts.most_common(1)[0][0]
        
        return 'string'  # デフォルトは文字列
    
    def _get_default_value_for_type(self, type_obj: type) -> Any:
        """
        型に基づいてデフォルト値を返す

        Args:
            type_obj: 型オブジェクト

        Returns:
            デフォルト値
        """
        if type_obj == bool:
            return False
        elif type_obj == int:
            return 0
        elif type_obj == float:
            return 0.0
        elif type_obj == str:
            return ""
        elif type_obj == list:
            return []
        elif type_obj == dict:
            return {}
        else:
            return None
    
    def _get_default_value_for_type_name(self, type_name: str) -> Any:
        """
        型名に基づいてデフォルト値を返す

        Args:
            type_name: 型名

        Returns:
            デフォルト値
        """
        if type_name == 'bool':
            return False
        elif type_name == 'int':
            return 0
        elif type_name == 'float':
            return 0.0
        elif type_name == 'string':
            return ""
        elif type_name == 'list':
            return []
        elif type_name == 'dict':
            return {}
        else:
            return None
    
    def _determine_field_purpose(self, field_name: str) -> Optional[str]:
        """
        フィールド名からフィールドの目的を推測する

        Args:
            field_name: フィールド名

        Returns:
            目的識別子またはNone
        """
        field_name_lower = field_name.lower()
        
        # ID関連フィールド
        if re.search(r'(^|_)(id|uuid|guid)($|_)', field_name_lower):
            return "identifier"
        
        # ラベル関連フィールド
        if re.search(r'(^|_)(name|title|label|text|caption|heading|subject)($|_)', field_name_lower):
            return "label"
        
        # 説明関連フィールド
        if re.search(r'(^|_)(description|content|message|detail|summary|info)($|_)', field_name_lower):
            return "description"
        
        # 子関連フィールド
        if re.search(r'(^|_)(children|child|next|sub|items|elements|members)($|_)', field_name_lower):
            return "children"
        
        # 親関連フィールド
        if re.search(r'(^|_)(parent|owner|container|group|category)($|_)', field_name_lower):
            return "parent"
        
        # 順序関連フィールド
        if re.search(r'(^|_)(order|index|position|rank|sequence|priority)($|_)', field_name_lower):
            return "order"
        
        # 日時関連フィールド
        if re.search(r'(^|_)(date|time|created|updated|modified|timestamp)($|_)', field_name_lower):
            return "datetime"
        
        # 状態関連フィールド
        if re.search(r'(^|_)(status|state|condition|phase|stage)($|_)', field_name_lower):
            return "status"
        
        # タイプ関連フィールド
        if re.search(r'(^|_)(type|category|class|kind|genre|form)($|_)', field_name_lower):
            return "type"
        
        # フラグ関連フィールド
        if re.search(r'(^|_)(is|has|can|should|flag|enabled|active)($|_)', field_name_lower):
            return "flag"
        
        return None

    def infer_empty_array_type(self, field_name: str, parent_path: str = "", data: Optional[List[Dict]] = None) -> Dict:
        """
        空配列のデータ型を推論する

        Args:
            field_name: 配列のフィールド名
            parent_path: 親パスの文字列
            data: 推論に使用するデータ（Noneの場合はapp_stateから取得）

        Returns:
            推論された型情報を含む辞書
        """
        full_path = f"{parent_path}.{field_name}" if parent_path else field_name
        
        if data is None:
            data = self.app_state.get("raw_data", [])
        
        # 結果格納用辞書
        result = {
            "item_type": "unknown",
            "template": None,
            "confidence": 0.0
        }
        
        # 1. フィールド名に基づく推論
        field_name_lower = field_name.lower()
        
        # 特定パターンの検出
        if field_name_lower == 'next' or field_name_lower.endswith('next'):
            # 'next'パターン（オブジェクト配列）
            result["item_type"] = "dict"
            result["template"] = {
                "id": "",
                "text": "",
                "description": "",
                "answer": "",
                "next": []
            }
            result["confidence"] = 0.8
        elif re.search(r'(^|_)(nextids|ids|links|refs)($|_)', field_name_lower):
            # IDリストパターン
            result["item_type"] = "string"
            result["template"] = ""
            result["confidence"] = 0.7
        elif re.search(r'(^|_)(tags|labels|categories)($|_)', field_name_lower):
            # 文字列配列パターン
            result["item_type"] = "string"
            result["template"] = ""
            result["confidence"] = 0.7
        elif re.search(r'(^|_)(values|scores|amounts|numbers)($|_)', field_name_lower):
            # 数値配列パターン
            result["item_type"] = "number"
            result["template"] = 0
            result["confidence"] = 0.6
        
        # 2. 同名の非空配列を他のノードから探して推論
        if result["confidence"] < 0.8:
            similar_arrays = []
            for item in data:
                if isinstance(item, dict) and field_name in item and isinstance(item[field_name], list) and item[field_name]:
                    similar_arrays.append(item[field_name])
            
            if similar_arrays:
                # サンプルアイテムを抽出
                sample_items = []
                for arr in similar_arrays[:3]:  # 最大3つの配列
                    sample_items.extend(arr[:3])  # 各配列から最大3アイテム
                
                # 型分布を取得
                if sample_items:
                    item_type = self._determine_list_item_type(sample_items)
                    if item_type == "dict":
                        # 辞書オブジェクトの場合、テンプレートを作成
                        template = {}
                        for sample in sample_items:
                            if isinstance(sample, dict):
                                for k, v in sample.items():
                                    if k not in template:
                                        template[k] = self._get_default_value_for_type(type(v))
                        if template:
                            result["item_type"] = "dict"
                            result["template"] = template
                            result["confidence"] = 0.9
                    else:
                        # 単純型の場合
                        result["item_type"] = item_type
                        result["template"] = self._get_default_value_for_type_name(item_type)
                        result["confidence"] = 0.9
        
        # 3. 同様の配列構造を横断的に探索して推論
        if result["confidence"] < 0.7 and parent_path:
            # 親パスと同レベルの他のノードを探す
            parent_pattern = re.escape(parent_path) + r"\.\w+"
            similar_fields = []
            for field_detail in self.app_state.get("field_details", []):
                field_path = field_detail.get("name", "")
                if re.match(parent_pattern, field_path) and field_path.endswith(field_name):
                    similar_fields.append(field_detail)
            
            # 同様のフィールドから型情報を取得
            if similar_fields:
                for field in similar_fields:
                    types = field.get("types", [])
                    if types and types[0][0].startswith("list["):
                        item_type = types[0][0].replace("list[", "").replace("]", "")
                        if item_type == "dict":
                            # 辞書型の場合、詳細を取得
                            examples = field.get("examples", [])
                            if examples:
                                sample_items = []
                                for example in examples:
                                    if isinstance(example, list) and example:
                                        sample_items.extend(example[:3])
                                
                                if sample_items:
                                    template = {}
                                    for sample in sample_items:
                                        if isinstance(sample, dict):
                                            for k, v in sample.items():
                                                if k not in template:
                                                    template[k] = self._get_default_value_for_type(type(v))
                                    if template:
                                        result["item_type"] = "dict"
                                        result["template"] = template
                                        result["confidence"] = 0.8
                        else:
                            # 単純型の場合
                            result["item_type"] = item_type
                            result["template"] = self._get_default_value_for_type_name(item_type)
                            result["confidence"] = 0.8
                        break
        
        # 4. 最後の手段：包括的テンプレートから推論
        if result["confidence"] < 0.6:
            comprehensive_data = self.app_state.get("comprehensive_template_data", {})
            if comprehensive_data:
                pattern_details = comprehensive_data.get("pattern_details", {})
                if pattern_details:
                    # フィールドパスに基づくパターン検索
                    for pattern_key, pattern_value in pattern_details.items():
                        if pattern_key.endswith(field_name) or pattern_key.endswith(f"[0].{field_name}"):
                            if isinstance(pattern_value, dict):
                                result["item_type"] = "dict"
                                result["template"] = pattern_value
                                result["confidence"] = 0.7
                                break
                
                if result["confidence"] < 0.6:
                    # テンプレートから直接検索
                    template = comprehensive_data.get("template", {})
                    if field_name in template and isinstance(template[field_name], list) and template[field_name]:
                        sample_item = template[field_name][0]
                        if isinstance(sample_item, dict):
                            result["item_type"] = "dict"
                            result["template"] = sample_item
                            result["confidence"] = 0.7
                        else:
                            result["item_type"] = self._determine_field_type("", [{"": sample_item}])
                            result["template"] = sample_item
                            result["confidence"] = 0.7
        
        # 結果が不明な場合、デフォルト値を設定
        if result["confidence"] < 0.5:
            result["item_type"] = "string"
            result["template"] = ""
            result["confidence"] = 0.3
            
        return result
    
    def detect_reference_field_patterns(self, data: Optional[List[Dict]] = None) -> Dict[str, Dict]:
        """
        データから参照フィールドのパターンを検出する

        Args:
            data: 解析対象のデータ（Noneの場合はapp_stateから取得）

        Returns:
            検出されたパターンの辞書
            {
                "child_ref_fields": {"field_name": {"type": "list_id|obj_list", "confidence": 0.8}},
                "parent_ref_fields": {"field_name": {"type": "id|obj", "confidence": 0.8}}
            }
        """
        if data is None:
            data = self.app_state.get("raw_data", [])
        
        if not data:
            return {"child_ref_fields": {}, "parent_ref_fields": {}}
        
        # 各フィールドの出現回数をカウント
        field_counts = defaultdict(int)
        field_types = {}
        
        # フィールドの値タイプを集計
        for item in data:
            if isinstance(item, dict):
                for field, value in item.items():
                    field_counts[field] += 1
                    
                    # 値の型を分類
                    if isinstance(value, list):
                        if value and all(isinstance(v, dict) for v in value):
                            field_types[field] = field_types.get(field, []) + ["obj_list"]
                        elif value and all(isinstance(v, (str, int)) for v in value):
                            field_types[field] = field_types.get(field, []) + ["list_id"]
                        else:
                            field_types[field] = field_types.get(field, []) + ["list_other"]
                    elif isinstance(value, dict):
                        field_types[field] = field_types.get(field, []) + ["obj"]
                    elif isinstance(value, (str, int)) and field.lower().endswith('id'):
                        field_types[field] = field_types.get(field, []) + ["id"]
                    else:
                        field_types[field] = field_types.get(field, []) + ["other"]
        
        # フィールド名パターン
        child_ref_patterns = [
            r'(^|_)(children|child|kids|next|sub|items|elements|members|parts)($|_)',
            r'(^|_)(nodes|branches|descendants|subdocuments|subfiles)($|_)',
            r'(^|_)(contents|sections|chapters|components|modules)($|_)'
        ]
        
        parent_ref_patterns = [
            r'(^|_)(parent|owner|container|source|root|origin)($|_)',
            r'(^|_)(target|destination|reference|pointer|link)($|_)',
            r'(^|_)(belongs\w*to|related\w*to|associated\w*with)($|_)'
        ]
        
        id_link_patterns = [
            r'(^|_)(ids?|uuids?|guids?)($|_)',
            r'(^|_)(refs?|references?|links?)($|_)'
        ]
        
        # パターンに基づいて子参照フィールドを特定
        child_ref_fields = {}
        parent_ref_fields = {}
        
        for field, count in field_counts.items():
            field_lower = field.lower()
            
            # 使用率が低いフィールドはスキップ
            usage_rate = count / len(data)
            if usage_rate < 0.2:  # 20%未満の利用率ならスキップ
                continue
            
            # 現在のフィールドの型カウント
            type_counter = Counter(field_types.get(field, []))
            dominant_type = type_counter.most_common(1)[0][0] if type_counter else None
            
            # 子参照フィールドの判定
            if dominant_type in ["obj_list", "list_id"]:
                confidence = 0.0
                
                # フィールド名が子参照パターンにマッチする場合
                for pattern in child_ref_patterns:
                    if re.search(pattern, field_lower):
                        confidence += 0.3
                        break
                
                # IDリストの場合、ID参照パターンもチェック
                if dominant_type == "list_id":
                    for pattern in id_link_patterns:
                        if re.search(pattern, field_lower):
                            confidence += 0.3
                            break
                
                # 使用率に基づく信頼度加算
                confidence += min(usage_rate, 0.8) * 0.2
                
                # フィールド名が複数形か
                if field_lower.endswith('s') and not field_lower.endswith('status'):
                    confidence += 0.1
                
                # 信頼度が閾値を超えれば登録
                if confidence >= 0.3:
                    child_ref_fields[field] = {
                        "type": dominant_type,
                        "confidence": confidence
                    }
            
            # 親参照フィールドの判定
            elif dominant_type in ["id", "obj"]:
                confidence = 0.0
                
                # フィールド名が親参照パターンにマッチする場合
                for pattern in parent_ref_patterns:
                    if re.search(pattern, field_lower):
                        confidence += 0.3
                        break
                
                # ID参照の場合、IDパターンもチェック
                if dominant_type == "id":
                    for pattern in id_link_patterns:
                        if re.search(pattern, field_lower):
                            confidence += 0.2
                            break
                
                # 使用率に基づく信頼度加算
                confidence += min(usage_rate, 0.8) * 0.2
                
                # フィールド名が単数形か
                if not field_lower.endswith('s'):
                    confidence += 0.1
                
                # 信頼度が閾値を超えれば登録
                if confidence >= 0.3:
                    parent_ref_fields[field] = {
                        "type": dominant_type,
                        "confidence": confidence
                    }
        
        return {
            "child_ref_fields": child_ref_fields,
            "parent_ref_fields": parent_ref_fields
        }
    
    def on_load_file_result(self, e: ft.FilePickerResultEvent):
        """
        ファイル選択ダイアログの結果を処理する
        
        Args:
            e: ファイル選択結果イベント
        """
        # UIマネージャーの取得
        ui_manager = self.app_state.get('ui_manager')
        ui_state_manager = self.app_state.get('ui_state_manager')
        
        # ファイルが選択されなかった場合は何もしない
        if not e.files or len(e.files) == 0:
            if self.page:
                try:
                    from notification_system import NotificationSystem
                    notification_system = NotificationSystem(self.page)
                    notification_system.show_warning(t("notification.file_load_cancelled"))
                except Exception as notif_ex:
                    print(f"代替通知システムエラー: {notif_ex}")
                    try:
                        self.page.snack_bar = ft.SnackBar(content=ft.Text(t("notification.file_load_cancelled")), open=True)
                        self.page.update()
                    except:
                        print("[WARNING] 全ての通知方法が失敗しました")
            return

        file_path = e.files[0].path
        self.app_state["file_path"] = file_path
        
        try:
            # ファイル読み込み
            with open(file_path, 'rb') as f:
                file_data = f.read()
                
            # JSONデータ解析
            json_str = file_data.decode('utf-8')
            raw_data = json.loads(json_str)
            
            # JSONデータを解析
            analysis_results = self.analyze_json_structure(data=raw_data)
            
            if "error" in analysis_results:
                if self.page:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(t("error.analysis_failed").format(error=analysis_results['error'])), 
                        open=True,
                        bgcolor=ft.Colors.RED_ACCENT_700
                    )
                    self.page.update()
                return
            
            # 状態更新
            self.app_state["analysis_results"] = analysis_results
            self.app_state["raw_data"] = raw_data
            self.app_state["data_map"] = {}
            self.app_state["children_map"] = {}
            self.app_state["root_ids"] = []
            self.app_state["selected_node_id"] = None
            self.app_state["edit_buffer"] = {}
            self.app_state["is_dirty"] = False
            
            # データマップとツリー構造を構築
            data_manager = self.app_state.get('data_manager')
            if data_manager:
                data_manager.build_data_map_and_tree()
            
            # UIの更新
            if ui_manager:
                ui_manager.update_tree_view()
            
            if ui_controls.get("detail_form_column"):
                ui_controls["detail_form_column"].controls = [ft.Text(t("ui.select_node"))]
                ui_controls["detail_form_column"].update()
            
            # ファイル名表示
            if ui_controls.get("file_name_text"):
                ui_controls["file_name_text"].value = os.path.basename(file_path)
                ui_controls["file_name_text"].update()
            
            # UI状態を更新
            if ui_state_manager:
                ui_state_manager.set_file_loaded(file_path)
            
            # 成功メッセージ
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(t("notification.file_loaded").format(filename=os.path.basename(file_path))), 
                    open=True,
                    bgcolor=ft.Colors.GREEN_ACCENT_700
                )
                self.page.update()
            print(f"[FILE] Loaded file: {file_path}")
            
        except Exception as ex:
            error_message = t("error.file_loading_error").format(error=str(ex))
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(error_message), 
                    open=True,
                    bgcolor=ft.Colors.RED_ACCENT_700
                )
                self.page.update()
            print(f"[ERROR] Error loading file: {ex}")
            import traceback
            traceback.print_exc()


def create_analysis_manager(app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None) -> AnalysisManager:
    """AnalysisManagerのインスタンスを作成する工場関数"""
    analysis_manager = AnalysisManager(app_state, ui_controls, page)
    app_state["analysis_manager"] = analysis_manager
    return analysis_manager