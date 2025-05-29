"""
template_manager.py
テンプレート生成・管理・適用を担当するマネージャークラス

FleDjSONのJSONテンプレート生成とパターン検出を担当する
特定の構造に依存せず、パターン認識と型推論に基づいてJSONデータのテンプレートを
動的に生成・適用します。
"""
from typing import Dict, List, Any, Optional, Set, Union, Tuple, Callable
from collections import defaultdict, Counter
import json
import re
import copy
from enum import Enum, auto
import statistics
from datetime import datetime

# EventHubのインポート
try:
    from ..event_hub import EventType, EventPriority
except ImportError:
    EventType = None
    EventPriority = None

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


class TemplateManager(EventAwareManager):
    """
    JSONテンプレート生成・管理・適用を担当するマネージャークラス
    
    特定の構造に依存せず、データパターンを検出し、動的にテンプレートを生成・適用します。
    
    Attributes:
        app_state (Dict): アプリケーションの状態を保持する辞書
        ui_controls (Dict): UIコントロールを保持する辞書  
        page (ft.Page): Fletページオブジェクト
        event_hub: イベントハブインスタンス
    """
    
    def __init__(self, app_state: Dict[str, Any], ui_controls: Dict[str, Any], page=None, event_hub=None):
        """
        TemplateManagerを初期化します
        
        Args:
            app_state: アプリケーション状態辞書
            ui_controls: UIコントロール辞書
            page: Fletページオブジェクト（オプション）
            event_hub: イベントハブ（オプション）
        """
        super().__init__(app_state, ui_controls, page, event_hub)
        
        # 型推論のためのパターン定義
        self.type_patterns = {
            FieldType.EMAIL: [
                re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            ],
            FieldType.URL: [
                re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE),
            ],
            FieldType.PHONE: [
                re.compile(r'^\+?[\d\s\-\(\)]{7,}$'),
            ],
            FieldType.DATE: [
                re.compile(r'^\d{4}-\d{2}-\d{2}$'),  # YYYY-MM-DD
                re.compile(r'^\d{2}/\d{2}/\d{4}$'),  # MM/DD/YYYY
                re.compile(r'^\d{4}/\d{2}/\d{2}$'),  # YYYY/MM/DD
                re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'),  # ISO datetime
            ],
            FieldType.ID: [
                re.compile(r'^[a-zA-Z0-9_-]+\d+$'),  # user123, item_456
                re.compile(r'^[0-9]+$'),  # 純粋な数値ID
                re.compile(r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$'),  # UUID
            ],
            FieldType.CURRENCY: [
                re.compile(r'^\$\d+(\.\d{2})?$'),  # $123.45
                re.compile(r'^\d+(\.\d{2})?\s?(USD|EUR|JPY|GBP)$'),  # 123.45 USD
            ],
            FieldType.PERCENTAGE: [
                re.compile(r'^\d+(\.\d+)?%$'),  # 50.5%
            ],
            FieldType.COLOR: [
                re.compile(r'^#[a-fA-F0-9]{6}$'),  # #FF0000
                re.compile(r'^#[a-fA-F0-9]{3}$'),  # #F00
                re.compile(r'^rgb\(\d+,\s?\d+,\s?\d+\)$'),  # rgb(255, 0, 0)
            ],
        }
        
        # フィールド名パターンによる役割推論
        self.role_patterns = {
            FieldRole.ID: [r'id$', r'^.*_id$', r'^id_'],
            FieldRole.PARENT_ID: [r'parent.*id', r'.*parent.*id', r'pid'],
            FieldRole.LABEL: [r'label', r'name$', r'title$'],
            FieldRole.NAME: [r'^name$', r'.*name$'],
            FieldRole.TITLE: [r'^title$', r'.*title$'],
            FieldRole.DESCRIPTION: [r'desc', r'description', r'detail', r'comment'],
            FieldRole.DATE: [r'date', r'time'],
            FieldRole.CREATED_AT: [r'created', r'create.*time', r'.*created.*'],
            FieldRole.UPDATED_AT: [r'updated', r'update.*time', r'.*updated.*', r'modified'],
            FieldRole.AUTHOR: [r'author', r'creator', r'user', r'owner'],
            FieldRole.STATUS: [r'status', r'state', r'flag'],
            FieldRole.TYPE: [r'^type$', r'.*type$', r'kind'],
            FieldRole.CATEGORY: [r'category', r'cat', r'group'],
            FieldRole.TAG: [r'tag', r'tags', r'label'],
            FieldRole.PRICE: [r'price', r'cost', r'amount', r'value'],
            FieldRole.QUANTITY: [r'qty', r'quantity', r'count', r'num'],
            FieldRole.CHILDREN: [r'child', r'sub', r'items'],
        }
        
        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] TemplateManager initialized")

    def generate_template(self, data: Union[Dict, List[Dict]]) -> Dict[str, Any]:
        """
        データからテンプレートを生成します
        
        Args:
            data: テンプレート生成元のデータ
            
        Returns:
            生成されたテンプレート
        """
        if not data:
            return {}
        
        # データが配列の場合は最初の要素をサンプルとして使用
        if isinstance(data, list):
            if not data:
                return {}
            sample_data = data[0]
            # 複数のサンプルがある場合はマージして共通構造を抽出
            if len(data) > 1:
                sample_data = self._merge_samples(data[:5])  # 最初の5個をサンプルとして使用
        else:
            sample_data = data
        
        if not isinstance(sample_data, dict):
            return {}
        
        template = {
            "type": FieldType.OBJECT.value,
            "fields": {},
            "sample_data": sample_data,
            "generated_at": datetime.now().isoformat(),
            "source": "template_manager"
        }
        
        # 各フィールドを分析
        for field_name, field_value in sample_data.items():
            field_info = self._analyze_field(field_name, field_value, data if isinstance(data, list) else [data])
            template["fields"][field_name] = field_info
        
        # イベント発行
        if self.event_hub and EventType and EventPriority:
            try:
                self.event_hub.publish(
                    EventType.TEMPLATE_GENERATED,
                    {
                        "template": template,
                        "source_data_size": len(data) if isinstance(data, list) else 1
                    },
                    priority=EventPriority.NORMAL
                )
            except Exception as e:
                print(f"[WARNING] イベント発行エラー: {e}")
        
        return template

    def apply_template(self, template: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        テンプレートをデータに適用し、不足フィールドを補完します
        
        Args:
            template: 適用するテンプレート
            data: 適用先のデータ
            
        Returns:
            テンプレートが適用されたデータ
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
        
        # イベント発行
        if self.event_hub:
            try:
                self.event_hub.publish(
                    EventType.TEMPLATE_APPLIED,
                    {
                        "template": template,
                        "result": result
                    },
                    priority=EventPriority.NORMAL
                )
            except Exception as e:
                print(f"[WARNING] イベント発行エラー: {e}")
        
        return result

    def suggest_field_roles(self, data: Union[Dict, List[Dict]]) -> Dict[str, FieldRole]:
        """
        データから各フィールドの役割を推測します
        
        Args:
            data: 分析対象のデータ
            
        Returns:
            フィールド名と推測された役割のマッピング
        """
        field_roles = {}
        
        # データが配列の場合は統合して分析
        if isinstance(data, list):
            if not data:
                return field_roles
            
            # 全てのフィールドを収集
            all_fields = set()
            for item in data:
                if isinstance(item, dict):
                    all_fields.update(item.keys())
            
            # 各フィールドを分析
            for field_name in all_fields:
                sample_values = []
                for item in data:
                    if isinstance(item, dict) and field_name in item:
                        sample_values.append(item[field_name])
                
                role = self._infer_field_role(field_name, sample_values)
                field_roles[field_name] = role
        
        elif isinstance(data, dict):
            for field_name, field_value in data.items():
                role = self._infer_field_role(field_name, [field_value])
                field_roles[field_name] = role
        
        return field_roles

    def detect_patterns(self, data: Union[Dict, List[Dict]]) -> Dict[str, Any]:
        """
        データのパターンを検出します
        
        Args:
            data: パターン検出対象のデータ
            
        Returns:
            検出されたパターン情報
        """
        patterns = {
            "structural": {},
            "naming": {},
            "typing": {},
            "relationships": {}
        }
        
        if isinstance(data, list):
            patterns["structural"]["is_array"] = True
            patterns["structural"]["array_length"] = len(data)
            patterns["structural"]["item_types"] = [type(item).__name__ for item in data]
            
            # 共通フィールドの検出
            if data and all(isinstance(item, dict) for item in data):
                common_fields = set(data[0].keys())
                for item in data[1:]:
                    if isinstance(item, dict):
                        common_fields &= set(item.keys())
                
                patterns["structural"]["common_fields"] = list(common_fields)
                patterns["structural"]["consistency"] = len(common_fields) / len(data[0]) if data[0] else 0
        
        else:
            patterns["structural"]["is_array"] = False
            patterns["structural"]["is_object"] = isinstance(data, dict)
        
        return patterns

    def _analyze_field(self, field_name: str, field_value: Any, samples: List[Dict]) -> Dict[str, Any]:
        """単一フィールドの詳細分析"""
        field_info = {
            "type": self._infer_field_type(field_value),
            "role": self._infer_field_role(field_name, [field_value]).value,
            "importance": self._infer_field_importance(field_name, field_value, samples),
            "nullable": field_value is None,
            "sample_value": field_value
        }
        
        # 型固有の分析
        if field_info["type"] == FieldType.STRING.value:
            field_info["min_length"] = len(str(field_value)) if field_value else 0
            field_info["max_length"] = len(str(field_value)) if field_value else 0
        elif field_info["type"] == FieldType.NUMBER.value:
            field_info["min_value"] = field_value
            field_info["max_value"] = field_value
        elif field_info["type"] == FieldType.ARRAY.value and isinstance(field_value, list):
            field_info["min_items"] = len(field_value)
            field_info["max_items"] = len(field_value)
            if field_value:
                field_info["item_types"] = list(set(type(item).__name__ for item in field_value))
        
        return field_info

    def _infer_field_type(self, value: Any) -> str:
        """値から型を推論"""
        if value is None:
            return FieldType.NULL.value
        elif isinstance(value, bool):
            return FieldType.BOOLEAN.value
        elif isinstance(value, int):
            return FieldType.NUMBER.value
        elif isinstance(value, float):
            return FieldType.NUMBER.value
        elif isinstance(value, str):
            # 文字列の場合はパターンマッチングで詳細な型を判定
            for field_type, patterns in self.type_patterns.items():
                for pattern in patterns:
                    if pattern.match(value):
                        return field_type.value
            return FieldType.STRING.value
        elif isinstance(value, list):
            return FieldType.ARRAY.value
        elif isinstance(value, dict):
            return FieldType.OBJECT.value
        else:
            return FieldType.UNKNOWN.value

    def _infer_field_role(self, field_name: str, sample_values: List[Any]) -> FieldRole:
        """フィールド名と値から役割を推論"""
        field_name_lower = field_name.lower()
        
        # フィールド名パターンによる推論
        for role, patterns in self.role_patterns.items():
            for pattern in patterns:
                if re.search(pattern, field_name_lower):
                    return role
        
        # 値のパターンによる追加推論
        if sample_values:
            first_value = sample_values[0]
            if isinstance(first_value, str):
                # IDパターンの特別チェック
                for pattern in self.type_patterns[FieldType.ID]:
                    if pattern.match(first_value):
                        return FieldRole.ID
        
        return FieldRole.UNKNOWN

    def _infer_field_importance(self, field_name: str, field_value: Any, samples: List[Dict]) -> str:
        """フィールドの重要度を推論"""
        # IDフィールドは必須
        role = self._infer_field_role(field_name, [field_value])
        if role in [FieldRole.ID, FieldRole.PARENT_ID]:
            return FieldImportance.REQUIRED.value
        
        # 全サンプルに存在するフィールドは推奨
        if samples:
            presence_count = sum(1 for sample in samples if isinstance(sample, dict) and field_name in sample)
            presence_ratio = presence_count / len(samples)
            
            if presence_ratio >= 0.9:
                return FieldImportance.REQUIRED.value
            elif presence_ratio >= 0.7:
                return FieldImportance.RECOMMENDED.value
        
        return FieldImportance.OPTIONAL.value

    def _merge_samples(self, samples: List[Dict]) -> Dict[str, Any]:
        """複数のサンプルをマージして代表的な構造を生成"""
        if not samples:
            return {}
        
        merged = {}
        all_fields = set()
        
        # 全フィールドを収集
        for sample in samples:
            if isinstance(sample, dict):
                all_fields.update(sample.keys())
        
        # 各フィールドの代表値を決定
        for field_name in all_fields:
            values = []
            for sample in samples:
                if isinstance(sample, dict) and field_name in sample:
                    values.append(sample[field_name])
            
            if values:
                # 最も頻出する値を使用（同頻度の場合は最初の値）
                value_counts = Counter(str(v) for v in values)
                most_common_str = value_counts.most_common(1)[0][0]
                
                # 元の型を保持
                for v in values:
                    if str(v) == most_common_str:
                        merged[field_name] = v
                        break
        
        return merged

    def _generate_default_value(self, field_type: str) -> Any:
        """型に応じたデフォルト値を生成"""
        type_defaults = {
            FieldType.STRING.value: "",
            FieldType.NUMBER.value: 0,
            FieldType.BOOLEAN.value: False,
            FieldType.ARRAY.value: [],
            FieldType.OBJECT.value: {},
            FieldType.NULL.value: None,
            FieldType.DATE.value: datetime.now().strftime("%Y-%m-%d"),
            FieldType.ID.value: "auto_generated_id",
            FieldType.EMAIL.value: "example@example.com",
            FieldType.URL.value: "https://example.com",
            FieldType.PHONE.value: "+1234567890",
            FieldType.CURRENCY.value: "$0.00",
            FieldType.PERCENTAGE.value: "0%",
            FieldType.COLOR.value: "#000000"
        }
        
        return type_defaults.get(field_type, "")


def create_template_manager(app_state: Dict[str, Any], ui_controls: Dict[str, Any], page=None, event_hub=None) -> TemplateManager:
    """TemplateManagerのインスタンスを作成する工場関数"""
    template_manager = TemplateManager(app_state, ui_controls, page, event_hub)
    app_state["template_manager"] = template_manager
    return template_manager