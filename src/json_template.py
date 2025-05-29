"""
json_template.py
JSONテンプレート生成とパターン検出モジュール

特定の構造に依存せず、パターン認識と型推論に基づいてJSONデータのテンプレートを
動的に生成・適用する機能を提供します。
"""
from typing import Dict, List, Any, Optional, Set, Union, Tuple, Callable
from collections import defaultdict, Counter
import json
import re
import copy
from enum import Enum, auto
import statistics
from datetime import datetime

# EventHubとの連携用
try:
    from event_hub import EventType, EventPriority
except ImportError:
    # EventHubが利用できない場合のダミークラス
    class EventType(Enum):
        TEMPLATE_GENERATED = auto()
        TEMPLATE_APPLIED = auto()
        
    class EventPriority(Enum):
        NORMAL = auto()

class FieldType(Enum):
    """フィールドの型を表す列挙型"""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"
    DATE = "date"
    ID = "id"
    REFERENCE = "reference"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    ADDRESS = "address"
    COORDINATES = "coordinates"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    COLOR = "color"
    UNKNOWN = "unknown"

class FieldRole(Enum):
    """フィールドの役割を表す列挙型"""
    ID = "id"
    PARENT_ID = "parent_id"
    LABEL = "label"
    NAME = "name"
    TITLE = "title"
    DESCRIPTION = "description"
    DATE = "date"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    AUTHOR = "author"
    STATUS = "status"
    TYPE = "type"
    CATEGORY = "category"
    TAG = "tag"
    PRICE = "price"
    QUANTITY = "quantity"
    CHILDREN = "children"
    METADATA = "metadata"
    CONFIG = "config"
    SETTINGS = "settings"
    ATTRIBUTES = "attributes"
    PROPERTIES = "properties"
    UNKNOWN = "unknown"

class FieldImportance(Enum):
    """フィールドの重要度を表す列挙型"""
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"
    SYSTEM = "system"
    DEPRECATED = "deprecated"

class JSONTemplate:
    """
    JSONテンプレート生成と適用を行うクラス
    
    特定の構造に依存せず、データパターンを検出し、動的にテンプレートを生成・適用します。
    """
    
    def __init__(self, event_hub=None):
        """
        JSONTemplateクラスを初期化します。
        
        Args:
            event_hub: イベントハブ（オプション）
        """
        self.event_hub = event_hub
        
        # 型推論のためのパターン定義
        self._type_patterns = {
            # ID系のパターン
            "id": re.compile(r'^(?:id|_id|uid|uuid|guid)$', re.IGNORECASE),
            # Email系のパターン
            "email": re.compile(r'^(?:.*?email.*?)$', re.IGNORECASE),
            # URL系のパターン
            "url": re.compile(r'^(?:url|link|website|site)$', re.IGNORECASE),
            # 日付系のパターン
            "date": re.compile(r'^(?:date|time|created_at|updated_at|timestamp|created|updated|createdAt|updatedAt)$', re.IGNORECASE),
            # 電話番号系のパターン
            "phone": re.compile(r'^(?:phone|tel|telephone|mobile|cell|fax)$', re.IGNORECASE),
            # 住所系のパターン
            "address": re.compile(r'^(?:address|location|addr)$', re.IGNORECASE),
            # 座標系のパターン
            "coordinates": re.compile(r'^(?:coordinates|coords|position|lat|lng|latitude|longitude)$', re.IGNORECASE),
            # 金額系のパターン
            "currency": re.compile(r'^(?:price|cost|amount|fee|salary|budget|revenue|income|expense)$', re.IGNORECASE),
            # パーセント系のパターン
            "percentage": re.compile(r'^(?:percent|percentage|ratio|rate)$', re.IGNORECASE),
            # 色系のパターン
            "color": re.compile(r'^(?:color|colour)$', re.IGNORECASE),
            # 名前系のパターン
            "name": re.compile(r'^(?:name|title|label)$', re.IGNORECASE),
            # 説明系のパターン
            "description": re.compile(r'^(?:description|desc|summary|details|text|comment)$', re.IGNORECASE),
            # 子要素系のパターン
            "children": re.compile(r'^(?:children|child|kids|items|elements|nodes|subordinates)$', re.IGNORECASE),
            # 親参照系のパターン
            "parent": re.compile(r'^(?:parent|parent_id|parentId|owner|owner_id|ownerId)$', re.IGNORECASE),
            # 状態系のパターン
            "status": re.compile(r'^(?:status|state|condition)$', re.IGNORECASE),
            # タイプ系のパターン
            "type": re.compile(r'^(?:type|category|kind|class)$', re.IGNORECASE),
        }
        
        # 日付文字列検出用のパターン
        self._date_patterns = [
            # ISO 8601 / RFC 3339フォーマット
            re.compile(r'^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$'),
            # 日付のみのフォーマット
            re.compile(r'^\d{4}/\d{2}/\d{2}$'),
            re.compile(r'^\d{2}/\d{2}/\d{4}$'),
            re.compile(r'^\d{2}-\d{2}-\d{4}$'),
            # Unix タイムスタンプ（数値）
            re.compile(r'^\d{10,13}$'),
        ]
        
        # 値に基づく型推論用のパターン
        self._value_patterns = {
            # Email
            "email": re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            # URL
            "url": re.compile(r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'),
            # 電話番号
            "phone": re.compile(r'^(?:\+\d{1,3}[-\s]?)?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}$'),
            # 16進数カラーコード
            "color": re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$'),
        }
    
    def analyze_json_structure(self, data: Union[List, Dict]) -> Dict[str, Any]:
        """
        JSONデータの構造を分析します。
        
        Args:
            data: 分析するJSONデータ（リストまたは辞書）
            
        Returns:
            Dict[str, Any]: 分析結果
        """
        if not data:
            return {"type": FieldType.UNKNOWN.value, "fields": {}}
        
        # リストの場合、最初の数件を分析
        if isinstance(data, list):
            return self._analyze_array(data)
        
        # 辞書の場合、各フィールドを分析
        if isinstance(data, dict):
            return self._analyze_object(data)
        
        # その他の型（プリミティブ値）の場合
        return {"type": self._get_primitive_type(data), "value": data}
    
    def _analyze_object(self, obj: Dict) -> Dict[str, Any]:
        """辞書（オブジェクト）の構造を分析します。"""
        result = {
            "type": FieldType.OBJECT.value,
            "fields": {},
            "field_counts": {},
            "field_roles": {},
            "field_types": {},
            "field_importance": {},
        }
        
        # IDフィールドの候補を探す
        id_field = self._find_id_field(obj)
        if id_field:
            result["id_field"] = id_field
        
        # 子要素フィールドの候補を探す
        children_field = self._find_children_field(obj)
        if children_field:
            result["children_field"] = children_field
        
        # ラベルフィールドの候補を探す
        label_field = self._find_label_field(obj)
        if label_field:
            result["label_field"] = label_field
        
        # 各フィールドの分析
        for key, value in obj.items():
            field_info = {}
            
            # フィールドの型を判定
            if isinstance(value, dict):
                field_info = self._analyze_object(value)
            elif isinstance(value, list):
                field_info = self._analyze_array(value)
            else:
                field_type = self._get_primitive_type(value)
                field_info = {
                    "type": field_type,
                    "value": value
                }
            
            # フィールドの役割を推測
            field_role = self._infer_field_role(key, value)
            field_info["role"] = field_role.value
            result["field_roles"][key] = field_role.value
            
            # フィールドの重要度を推測
            field_importance = self._infer_field_importance(key, value, field_role)
            field_info["importance"] = field_importance.value
            result["field_importance"][key] = field_importance.value
            
            # 結果に追加
            result["fields"][key] = field_info
            result["field_types"][key] = field_info["type"]
            result["field_counts"][key] = 1
        
        return result
    
    def _analyze_array(self, arr: List) -> Dict[str, Any]:
        """配列の構造を分析します。"""
        result = {
            "type": FieldType.ARRAY.value,
            "item_types": [],
            "sample_size": min(len(arr), 10),  # 最大10件をサンプルとして分析
            "common_fields": {},
            "field_counts": defaultdict(int),
            "field_types": defaultdict(list),
            "field_roles": {},
            "field_importance": {},
        }
        
        if not arr:
            return result
        
        # すべての要素が同じ型か確認
        first_item_type = type(arr[0])
        homogeneous = all(isinstance(item, first_item_type) for item in arr)
        result["homogeneous"] = homogeneous
        
        # サンプル要素の分析
        samples = arr[:result["sample_size"]]
        
        # 各サンプルの型を記録
        for item in samples:
            if isinstance(item, dict):
                item_type = FieldType.OBJECT.value
                
                # オブジェクトの場合、フィールドの出現回数をカウント
                for key, value in item.items():
                    result["field_counts"][key] += 1
                    
                    # フィールドの型を記録
                    if isinstance(value, dict):
                        result["field_types"][key].append(FieldType.OBJECT.value)
                    elif isinstance(value, list):
                        result["field_types"][key].append(FieldType.ARRAY.value)
                    else:
                        result["field_types"][key].append(self._get_primitive_type(value))
                        
                    # フィールドの役割を推測（最初の要素でのみ）
                    if key not in result["field_roles"]:
                        field_role = self._infer_field_role(key, value)
                        result["field_roles"][key] = field_role.value
                        
                    # フィールドの重要度を推測（最初の要素でのみ）
                    if key not in result["field_importance"]:
                        field_importance = self._infer_field_importance(key, value, field_role)
                        result["field_importance"][key] = field_importance.value
                
            elif isinstance(item, list):
                item_type = FieldType.ARRAY.value
            else:
                item_type = self._get_primitive_type(item)
                
            result["item_types"].append(item_type)
        
        # 共通フィールドの抽出（オブジェクトの配列の場合）
        if homogeneous and samples and isinstance(samples[0], dict):
            # すべてのサンプルに共通するフィールドを抽出
            common_keys = set(samples[0].keys())
            for item in samples[1:]:
                common_keys &= set(item.keys())
            
            # 共通フィールドが存在する場合、その情報を記録
            if common_keys:
                # 各共通フィールドの型を決定（最も頻度の高い型）
                for key in common_keys:
                    types = result["field_types"][key]
                    if types:
                        # 最も多い型を選定
                        most_common_type = max(set(types), key=types.count)
                        
                        # 共通フィールド情報を記録
                        result["common_fields"][key] = {
                            "type": most_common_type,
                            "role": result["field_roles"].get(key, FieldRole.UNKNOWN.value),
                            "importance": result["field_importance"].get(key, FieldImportance.OPTIONAL.value),
                        }
            
            # IDフィールドの候補を探す
            for item in samples:
                id_field = self._find_id_field(item)
                if id_field:
                    result["id_field"] = id_field
                    break
            
            # ラベルフィールドの候補を探す
            for item in samples:
                label_field = self._find_label_field(item)
                if label_field:
                    result["label_field"] = label_field
                    break
            
        return result
    
    def _get_primitive_type(self, value: Any) -> str:
        """プリミティブ値の型を取得します。"""
        if value is None:
            return FieldType.NULL.value
        
        if isinstance(value, bool):
            return FieldType.BOOLEAN.value
        
        if isinstance(value, (int, float)):
            return FieldType.NUMBER.value
        
        if isinstance(value, str):
            # 日付文字列かどうかをチェック
            for pattern in self._date_patterns:
                if pattern.match(value):
                    return FieldType.DATE.value
            
            # その他の型パターンをチェック
            for type_name, pattern in self._value_patterns.items():
                if pattern.match(value):
                    return getattr(FieldType, type_name.upper()).value
            
            # デフォルトは文字列型
            return FieldType.STRING.value
        
        # その他の型（プリミティブではない）
        return FieldType.UNKNOWN.value
    
    def _find_id_field(self, obj: Dict) -> Optional[str]:
        """IDフィールドの候補を探します。"""
        # IDパターンに一致するフィールド名を探す
        for key in obj.keys():
            if self._type_patterns["id"].match(key):
                return key
        
        # '_id'や'id'に近い名前のフィールドを探す
        candidates = []
        for key in obj.keys():
            if 'id' in key.lower():
                candidates.append(key)
        
        # 候補がある場合、最も短いものを返す（シンプルな名前が優先）
        if candidates:
            return min(candidates, key=len)
        
        return None
    
    def _find_children_field(self, obj: Dict) -> Optional[str]:
        """子要素フィールドの候補を探します。"""
        # 子要素パターンに一致するフィールドを探す
        for key, value in obj.items():
            if isinstance(value, list) and self._type_patterns["children"].match(key):
                return key
        
        # 配列型のフィールドを探す（最初の配列型フィールドを候補とする）
        for key, value in obj.items():
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
                return key
        
        return None
    
    def _find_label_field(self, obj: Dict) -> Optional[str]:
        """ラベルフィールドの候補を探します。"""
        # 名前パターンに一致するフィールドを探す
        for key in obj.keys():
            if self._type_patterns["name"].match(key):
                return key
        
        # title, label, nameのいずれかに一致するフィールドを探す
        label_candidates = ["title", "label", "name", "text", "description"]
        for candidate in label_candidates:
            if candidate in obj:
                return candidate
        
        # 文字列型のフィールドを探す（最初の文字列型フィールドを候補とする）
        for key, value in obj.items():
            if isinstance(value, str) and len(value) < 100:  # 長すぎる文字列は除外
                return key
        
        return None
    
    def _infer_field_role(self, key: str, value: Any) -> FieldRole:
        """フィールドの役割を推測します。"""
        key_lower = key.lower()
        
        # IDフィールド
        if self._type_patterns["id"].match(key_lower):
            return FieldRole.ID
        
        # 親参照フィールド
        if self._type_patterns["parent"].match(key_lower):
            return FieldRole.PARENT_ID
        
        # 名前/ラベルフィールド
        if self._type_patterns["name"].match(key_lower):
            return FieldRole.NAME
        
        # タイトルフィールド
        if key_lower == "title":
            return FieldRole.TITLE
        
        # 説明フィールド
        if self._type_patterns["description"].match(key_lower):
            return FieldRole.DESCRIPTION
        
        # 日付フィールド
        if self._type_patterns["date"].match(key_lower):
            if "created" in key_lower:
                return FieldRole.CREATED_AT
            if "updated" in key_lower:
                return FieldRole.UPDATED_AT
            return FieldRole.DATE
        
        # 著者フィールド
        if key_lower in ["author", "creator", "owner", "user"]:
            return FieldRole.AUTHOR
        
        # 状態フィールド
        if self._type_patterns["status"].match(key_lower):
            return FieldRole.STATUS
        
        # タイプフィールド
        if self._type_patterns["type"].match(key_lower):
            return FieldRole.TYPE
        
        # カテゴリフィールド
        if key_lower in ["category", "group", "section"]:
            return FieldRole.CATEGORY
        
        # タグフィールド
        if key_lower in ["tag", "tags", "keywords"]:
            return FieldRole.TAG
        
        # 価格フィールド
        if self._type_patterns["currency"].match(key_lower):
            return FieldRole.PRICE
        
        # 数量フィールド
        if key_lower in ["quantity", "count", "amount", "number"]:
            return FieldRole.QUANTITY
        
        # 子要素フィールド
        if self._type_patterns["children"].match(key_lower):
            return FieldRole.CHILDREN
        
        # メタデータフィールド
        if key_lower in ["metadata", "meta", "info"]:
            return FieldRole.METADATA
        
        # 設定フィールド
        if key_lower in ["config", "configuration", "settings", "options"]:
            return FieldRole.CONFIG
        
        # 属性フィールド
        if key_lower in ["attributes", "attrs", "properties", "props"]:
            return FieldRole.ATTRIBUTES
        
        # デフォルト
        return FieldRole.UNKNOWN
    
    def _infer_field_importance(self, key: str, value: Any, role: FieldRole) -> FieldImportance:
        """フィールドの重要度を推測します。"""
        # IDフィールドは必須
        if role == FieldRole.ID:
            return FieldImportance.REQUIRED
        
        # 名前/ラベルフィールドは推奨
        if role in [FieldRole.NAME, FieldRole.TITLE, FieldRole.LABEL]:
            return FieldImportance.RECOMMENDED
        
        # システムフィールド
        if role in [FieldRole.CREATED_AT, FieldRole.UPDATED_AT]:
            return FieldImportance.SYSTEM
        
        # 重要そうなフィールド
        if role in [FieldRole.TYPE, FieldRole.STATUS, FieldRole.CATEGORY]:
            return FieldImportance.RECOMMENDED
        
        # NULL値のフィールドはオプション
        if value is None:
            return FieldImportance.OPTIONAL
        
        # デフォルト
        return FieldImportance.OPTIONAL
    
    def generate_template(self, data: Union[List, Dict]) -> Dict[str, Any]:
        """
        JSONデータからテンプレートを生成します。
        
        Args:
            data: テンプレートを生成するJSONデータ
            
        Returns:
            Dict[str, Any]: 生成されたテンプレート
        """
        # データ構造の分析
        analysis = self.analyze_json_structure(data)
        
        # テンプレートの生成
        template = self._build_template_from_analysis(analysis)
        
        # イベントハブが利用可能な場合、イベントを発行
        if self.event_hub:
            self.event_hub.publish(
                EventType.TEMPLATE_GENERATED,
                {
                    "template": template,
                    "source_data_type": type(data).__name__
                },
                "json_template",
                EventPriority.NORMAL
            )
        
        return template
    
    def _build_template_from_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """分析結果からテンプレートを構築します。"""
        template = {
            "type": analysis["type"],
            "fields": {},
            "sample_data": {}
        }
        
        # IDフィールド、子要素フィールド、ラベルフィールドの情報を追加
        for special_field in ["id_field", "children_field", "label_field"]:
            if special_field in analysis:
                template[special_field] = analysis[special_field]
        
        # オブジェクト型の場合
        if analysis["type"] == FieldType.OBJECT.value:
            # 各フィールドのテンプレートを構築
            for field_name, field_info in analysis["fields"].items():
                field_template = {
                    "type": field_info["type"],
                    "role": field_info.get("role", FieldRole.UNKNOWN.value),
                    "importance": field_info.get("importance", FieldImportance.OPTIONAL.value)
                }
                
                # 配列型またはオブジェクト型の場合、再帰的にテンプレートを構築
                if field_info["type"] in [FieldType.OBJECT.value, FieldType.ARRAY.value]:
                    field_template.update(self._build_template_from_analysis(field_info))
                
                template["fields"][field_name] = field_template
                
                # サンプルデータの保存（プリミティブ値のみ）
                if "value" in field_info:
                    template["sample_data"][field_name] = field_info["value"]
        
        # 配列型の場合
        elif analysis["type"] == FieldType.ARRAY.value:
            template["item_types"] = analysis.get("item_types", [])
            template["homogeneous"] = analysis.get("homogeneous", True)
            
            # 共通フィールドが存在する場合
            if "common_fields" in analysis and analysis["common_fields"]:
                template["common_fields"] = {}
                
                for field_name, field_info in analysis["common_fields"].items():
                    template["common_fields"][field_name] = {
                        "type": field_info["type"],
                        "role": field_info.get("role", FieldRole.UNKNOWN.value),
                        "importance": field_info.get("importance", FieldImportance.OPTIONAL.value)
                    }
        
        return template
    
    def apply_template(self, template: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        テンプレートをデータに適用し、不足フィールドを補完します。
        
        Args:
            template: 適用するテンプレート
            data: 適用先のデータ
            
        Returns:
            Dict[str, Any]: テンプレートが適用されたデータ
        """
        if not template or not data:
            return data
        
        # データのコピーを作成
        result = copy.deepcopy(data)
        
        # テンプレートがオブジェクト型の場合
        if template["type"] == FieldType.OBJECT.value:
            # 必須フィールドの補完
            for field_name, field_info in template["fields"].items():
                if field_info.get("importance") == FieldImportance.REQUIRED.value and field_name not in result:
                    # サンプルデータがある場合はそれを使用
                    if "sample_data" in template and field_name in template["sample_data"]:
                        result[field_name] = template["sample_data"][field_name]
                    else:
                        # サンプルデータがない場合はデフォルト値を生成
                        result[field_name] = self._generate_default_value(field_info["type"])
            
            # 再帰的に子オブジェクトにテンプレートを適用
            for field_name, field_value in result.items():
                if field_name in template["fields"]:
                    field_template = template["fields"][field_name]
                    
                    if field_template["type"] == FieldType.OBJECT.value and isinstance(field_value, dict):
                        result[field_name] = self.apply_template(field_template, field_value)
                    elif field_template["type"] == FieldType.ARRAY.value and isinstance(field_value, list):
                        # 配列の各要素にテンプレートを適用
                        if "common_fields" in field_template and field_template["common_fields"]:
                            result[field_name] = [
                                self.apply_template({"type": FieldType.OBJECT.value, "fields": field_template["common_fields"]}, item)
                                if isinstance(item, dict) else item
                                for item in field_value
                            ]
        
        # テンプレートが配列型の場合
        elif template["type"] == FieldType.ARRAY.value and isinstance(data, list):
            # 配列の各要素にテンプレートを適用
            if "common_fields" in template and template["common_fields"]:
                result = [
                    self.apply_template({"type": FieldType.OBJECT.value, "fields": template["common_fields"]}, item)
                    if isinstance(item, dict) else item
                    for item in data
                ]
        
        # イベントハブが利用可能な場合、イベントを発行
        if self.event_hub:
            self.event_hub.publish(
                EventType.TEMPLATE_APPLIED,
                {
                    "template_type": template["type"],
                    "source_data_type": type(data).__name__
                },
                "json_template",
                EventPriority.NORMAL
            )
        
        return result
    
    def _generate_default_value(self, field_type: str) -> Any:
        """フィールドタイプに基づいてデフォルト値を生成します。"""
        if field_type == FieldType.STRING.value:
            return ""
        elif field_type == FieldType.NUMBER.value:
            return 0
        elif field_type == FieldType.BOOLEAN.value:
            return False
        elif field_type == FieldType.OBJECT.value:
            return {}
        elif field_type == FieldType.ARRAY.value:
            return []
        elif field_type == FieldType.DATE.value:
            return datetime.now().isoformat()
        elif field_type == FieldType.ID.value:
            return "new_id"
        elif field_type == FieldType.NULL.value:
            return None
        else:
            return None
    
    def detect_patterns(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        データリスト内のパターンを検出します。
        
        Args:
            data: 検出対象のデータリスト
            
        Returns:
            Dict[str, Any]: 検出されたパターン
        """
        if not data or not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            return {}
        
        result = {
            "field_frequency": {},
            "field_types": {},
            "value_patterns": {},
            "correlations": {},
            "dependencies": {}
        }
        
        # フィールドの出現頻度とタイプを集計
        field_types = defaultdict(list)
        field_values = defaultdict(list)
        
        for item in data:
            for key, value in item.items():
                field_types[key].append(self._get_primitive_type(value))
                if not isinstance(value, (dict, list)):
                    field_values[key].append(value)
        
        # 出現頻度の計算
        total_items = len(data)
        for key in field_types:
            result["field_frequency"][key] = len(field_types[key]) / total_items
        
        # 最も多い型を決定
        for key, types in field_types.items():
            counter = Counter(types)
            most_common = counter.most_common(1)
            if most_common:
                result["field_types"][key] = most_common[0][0]
        
        # 数値フィールドの統計情報を計算
        for key, values in field_values.items():
            number_values = [v for v in values if isinstance(v, (int, float))]
            if number_values:
                try:
                    result["value_patterns"][key] = {
                        "min": min(number_values),
                        "max": max(number_values),
                        "mean": statistics.mean(number_values),
                        "median": statistics.median(number_values),
                        "unique_values": len(set(number_values)),
                    }
                except Exception:
                    pass
        
        # フィールド間の相関関係を検出
        field_pairs = [(k1, k2) for k1 in field_types for k2 in field_types if k1 != k2]
        for k1, k2 in field_pairs:
            # 両方のフィールドを持つアイテムを抽出
            joint_items = [item for item in data if k1 in item and k2 in item]
            if joint_items:
                # 共起頻度の計算
                joint_freq = len(joint_items) / total_items
                if joint_freq > result["field_frequency"][k1] * result["field_frequency"][k2] * 1.5:
                    # 相関が高いと判断
                    result["correlations"][(k1, k2)] = joint_freq
                
                # k1が存在する場合にk2も存在する割合
                items_with_k1 = [item for item in data if k1 in item]
                if items_with_k1:
                    k2_given_k1 = len(joint_items) / len(items_with_k1)
                    if k2_given_k1 > 0.9:  # 90%以上の確率でk2も存在
                        result["dependencies"][k1] = result.get("dependencies", {})
                        result["dependencies"][k1][k2] = k2_given_k1
        
        return result
    
    def suggest_missing_fields(self, template: Dict[str, Any], data: Dict[str, Any]) -> List[str]:
        """
        テンプレートに基づいて、データに不足しているフィールドを提案します。
        
        Args:
            template: テンプレート
            data: チェック対象のデータ
            
        Returns:
            List[str]: 不足しているフィールドのリスト
        """
        if not template or not data:
            return []
        
        missing_fields = []
        
        # テンプレートがオブジェクト型の場合
        if template["type"] == FieldType.OBJECT.value:
            for field_name, field_info in template["fields"].items():
                # 必須フィールドの確認
                if field_info.get("importance") == FieldImportance.REQUIRED.value and field_name not in data:
                    missing_fields.append(field_name)
                
                # 推奨フィールドの確認
                elif field_info.get("importance") == FieldImportance.RECOMMENDED.value and field_name not in data:
                    missing_fields.append(f"{field_name} (推奨)")
                
                # 再帰的に子オブジェクトをチェック
                elif field_name in data and field_info["type"] == FieldType.OBJECT.value and isinstance(data[field_name], dict):
                    child_missing = self.suggest_missing_fields(field_info, data[field_name])
                    missing_fields.extend([f"{field_name}.{f}" for f in child_missing])
        
        return missing_fields
    
    def suggest_field_roles(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        データ構造からフィールドの役割を推測します。
        
        Args:
            data: 推測対象のデータ
            
        Returns:
            Dict[str, str]: フィールド名とその推測される役割のマッピング
        """
        if not data:
            return {}
        
        roles = {}
        
        for key, value in data.items():
            role = self._infer_field_role(key, value)
            roles[key] = role.value
        
        return roles
    
    def create_empty_template(self, field_roles: Dict[str, str] = None) -> Dict[str, Any]:
        """
        空のテンプレートを作成します。
        
        Args:
            field_roles: フィールドの役割（オプション）
            
        Returns:
            Dict[str, Any]: 作成されたテンプレート
        """
        template = {
            "type": FieldType.OBJECT.value,
            "fields": {},
            "sample_data": {}
        }
        
        # フィールドの役割が指定されている場合
        if field_roles:
            for field_name, role in field_roles.items():
                field_type = self._infer_type_from_role(role)
                importance = self._infer_importance_from_role(role)
                
                template["fields"][field_name] = {
                    "type": field_type.value,
                    "role": role,
                    "importance": importance.value
                }
        
        return template
    
    def _infer_type_from_role(self, role: str) -> FieldType:
        """役割から型を推測します。"""
        role_type_mapping = {
            FieldRole.ID.value: FieldType.ID,
            FieldRole.PARENT_ID.value: FieldType.REFERENCE,
            FieldRole.LABEL.value: FieldType.STRING,
            FieldRole.NAME.value: FieldType.STRING,
            FieldRole.TITLE.value: FieldType.STRING,
            FieldRole.DESCRIPTION.value: FieldType.STRING,
            FieldRole.DATE.value: FieldType.DATE,
            FieldRole.CREATED_AT.value: FieldType.DATE,
            FieldRole.UPDATED_AT.value: FieldType.DATE,
            FieldRole.AUTHOR.value: FieldType.STRING,
            FieldRole.STATUS.value: FieldType.STRING,
            FieldRole.TYPE.value: FieldType.STRING,
            FieldRole.CATEGORY.value: FieldType.STRING,
            FieldRole.TAG.value: FieldType.ARRAY,
            FieldRole.PRICE.value: FieldType.NUMBER,
            FieldRole.QUANTITY.value: FieldType.NUMBER,
            FieldRole.CHILDREN.value: FieldType.ARRAY,
            FieldRole.METADATA.value: FieldType.OBJECT,
            FieldRole.CONFIG.value: FieldType.OBJECT,
            FieldRole.SETTINGS.value: FieldType.OBJECT,
            FieldRole.ATTRIBUTES.value: FieldType.OBJECT,
            FieldRole.PROPERTIES.value: FieldType.OBJECT,
        }
        
        return role_type_mapping.get(role, FieldType.UNKNOWN)
    
    def _infer_importance_from_role(self, role: str) -> FieldImportance:
        """役割から重要度を推測します。"""
        role_importance_mapping = {
            FieldRole.ID.value: FieldImportance.REQUIRED,
            FieldRole.PARENT_ID.value: FieldImportance.OPTIONAL,
            FieldRole.LABEL.value: FieldImportance.RECOMMENDED,
            FieldRole.NAME.value: FieldImportance.RECOMMENDED,
            FieldRole.TITLE.value: FieldImportance.RECOMMENDED,
            FieldRole.DESCRIPTION.value: FieldImportance.OPTIONAL,
            FieldRole.DATE.value: FieldImportance.OPTIONAL,
            FieldRole.CREATED_AT.value: FieldImportance.SYSTEM,
            FieldRole.UPDATED_AT.value: FieldImportance.SYSTEM,
            FieldRole.AUTHOR.value: FieldImportance.OPTIONAL,
            FieldRole.STATUS.value: FieldImportance.RECOMMENDED,
            FieldRole.TYPE.value: FieldImportance.RECOMMENDED,
            FieldRole.CATEGORY.value: FieldImportance.OPTIONAL,
            FieldRole.TAG.value: FieldImportance.OPTIONAL,
            FieldRole.PRICE.value: FieldImportance.OPTIONAL,
            FieldRole.QUANTITY.value: FieldImportance.OPTIONAL,
            FieldRole.CHILDREN.value: FieldImportance.OPTIONAL,
            FieldRole.METADATA.value: FieldImportance.OPTIONAL,
            FieldRole.CONFIG.value: FieldImportance.OPTIONAL,
            FieldRole.SETTINGS.value: FieldImportance.OPTIONAL,
            FieldRole.ATTRIBUTES.value: FieldImportance.OPTIONAL,
            FieldRole.PROPERTIES.value: FieldImportance.OPTIONAL,
        }
        
        return role_importance_mapping.get(role, FieldImportance.OPTIONAL)

def create_json_template(event_hub=None) -> JSONTemplate:
    """
    JSONTemplateのインスタンスを作成します。
    
    Args:
        event_hub: イベントハブ（オプション）
        
    Returns:
        JSONTemplate: JSONTemplateのインスタンス
    """
    return JSONTemplate(event_hub)