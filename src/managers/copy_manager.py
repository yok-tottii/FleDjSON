"""
copy_manager.py

深いコピー処理と配列参照を安全に扱うためのユーティリティクラス

このモジュールは、JSONデータの深いコピーを行う際に、
特に配列型のデータが他のノードに意図せず反映されるバグを解決するための
専用のマネージャークラスを提供します。
"""
import copy
from typing import Any, Dict, List, Optional, Union, Set
import json

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


class CopyManager(EventAwareManager):
    """
    深いコピー処理を安全に行うためのマネージャークラス
    
    配列型データの参照問題を解決し、各ノードのデータが独立して扱われるようにします。
    特にショートカットキー保存時（Ctrl+S/Cmd+S）の問題を修正します。
    
    Attributes:
        app_state (Dict): アプリケーションの状態を保持する辞書
        ui_controls (Dict): UIコントロールを保持する辞書
        page (ft.Page): Fletページオブジェクト
        event_hub: イベントハブインスタンス
    """
    
    def __init__(self, app_state: Dict[str, Any], ui_controls: Dict[str, Any], page=None, event_hub=None):
        """
        CopyManagerを初期化します
        
        Args:
            app_state: アプリケーション状態辞書
            ui_controls: UIコントロール辞書
            page: Fletページオブジェクト（オプション）
            event_hub: イベントハブ（オプション）
        """
        super().__init__(app_state, ui_controls, page, event_hub)
        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] CopyManager initialized")
    
    def deep_copy(self, data: Any) -> Any:
        """
        データの深いコピーを作成する（後方互換性のためのエイリアス）
        
        Args:
            data: コピーするデータ（任意の型）
            
        Returns:
            コピーされたデータ
        """
        return self.safe_deep_copy(data)
    
    def safe_deep_copy(self, data: Any) -> Any:
        """
        データの安全な深いコピーを作成する
        
        標準のcopy.deepcopyを拡張し、配列型データを特別に処理して
        参照問題を解決します。
        
        Args:
            data: コピーするデータ（任意の型）
            
        Returns:
            コピーされたデータ
        """
        # Noneや基本型はそのまま返す
        if data is None or isinstance(data, (str, int, float, bool)):
            return data
            
        # 辞書型の場合は再帰的に処理
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # 値が配列の場合は特別処理
                if isinstance(value, list):
                    result[key] = self.safe_deep_copy_list(value)
                else:
                    result[key] = self.safe_deep_copy(value)
            return result
            
        # 配列型の場合は専用の処理
        if isinstance(data, list):
            return self.safe_deep_copy_list(data)
            
        # その他の型はstandard deepcopyを使用
        return copy.deepcopy(data)
    
    def safe_deep_copy_list(self, data_list: List) -> List:
        """
        リスト型データの安全な深いコピーを作成する
        
        Args:
            data_list: コピーするリスト
            
        Returns:
            コピーされたリスト
        """
        result = []
        for item in data_list:
            # 各要素を再帰的に処理
            if isinstance(item, dict):
                result.append(self.safe_deep_copy(item))
            elif isinstance(item, list):
                result.append(self.safe_deep_copy_list(item))
            else:
                # 基本型はそのままでOK、その他はdeep_copy
                if isinstance(item, (str, int, float, bool, type(None))):
                    result.append(item)
                else:
                    result.append(copy.deepcopy(item))
        return result


class JSONStructureHandler:
    """
    JSONデータの構造を適切に管理するためのハンドラクラス
    
    JSONデータの構造整合性を保ち、特に配列参照問題を解決します。
    フォーム表示時のデータ参照問題も処理します。
    """
    
    def __init__(self):
        """JSONStructureHandlerを初期化します"""
        # CopyManagerのインスタンスを作成（app_stateとui_controlsは空で初期化）
        self.copy_manager = CopyManager({}, {}, None, None)
        
    def rebuild_data_map(self, raw_data: List[Dict], id_key: str) -> Dict[str, Dict]:
        """
        raw_dataからdata_mapを再構築する
        
        Args:
            raw_data: 元データのリスト
            id_key: IDとして使用するキー
            
        Returns:
            構築されたdata_map
        """
        data_map = {}
        
        for item in raw_data:
            if isinstance(item, dict) and id_key in item:
                item_id = str(item[id_key])
                # 安全なコピーを使用
                data_map[item_id] = self.copy_manager.safe_deep_copy(item)
        
        return data_map
        
    def prepare_save_data(self, data_map: Dict[str, Dict], raw_data: List[Dict], 
                         id_key: str) -> List[Dict]:
        """
        保存用のデータを構築する
        
        Args:
            data_map: 処理中のデータマップ
            raw_data: 元データのリスト
            id_key: IDとして使用するキー
            
        Returns:
            保存用のデータリスト
        """
        # 順序保持のためのマッピング
        original_indices = {}
        for i, item in enumerate(raw_data):
            if isinstance(item, dict) and id_key in item:
                original_indices[str(item[id_key])] = i
        
        # 元の順序でdata_mapのデータを構築
        ordered_ids = sorted(data_map.keys(), 
                           key=lambda node_id: original_indices.get(str(node_id), 999999))
        
        data_to_save = []
        for node_id in ordered_ids:
            node_data = data_map.get(node_id)
            if node_data:
                # 安全なコピーを使用
                node_data_copy = self.copy_manager.safe_deep_copy(node_data)
                data_to_save.append(node_data_copy)
        
        return data_to_save
    
    def update_array_value(self, target_dict: Dict, key: str, value: List) -> None:
        """
        辞書内の配列値を安全に更新する
        
        Args:
            target_dict: 更新対象の辞書
            key: 更新するキー
            value: 設定する配列値
        """
        if isinstance(value, list):
            # 安全なコピーを使用
            target_dict[key] = self.copy_manager.safe_deep_copy_list(value)
        else:
            target_dict[key] = self.copy_manager.safe_deep_copy(value)
            
    def prepare_form_data(self, node_data: Dict) -> Dict:
        """
        フォーム表示用のノードデータを安全にコピーする
        
        配列参照問題を解決し、フォーム間でデータが共有されないようにします。
        特にノード切り替え時の問題を修正します。
        
        Args:
            node_data: 元のノードデータ
            
        Returns:
            安全にコピーされたノードデータ
        """
        # DeepCopyManagerを使用して完全に独立したコピーを作成
        return self.copy_manager.safe_deep_copy(node_data)
    
    def validate_data_integrity(self, data_map: Dict[str, Dict], raw_data: List[Dict], 
                              id_key: str) -> bool:
        """
        データの整合性を検証する
        
        Args:
            data_map: 検証するデータマップ
            raw_data: 元データのリスト
            id_key: IDとして使用するキー
            
        Returns:
            整合性が保たれている場合はTrue
        """
        # data_mapに存在するIDのセット
        data_map_ids = set(data_map.keys())
        
        # raw_dataに存在するIDのセット
        raw_data_ids = set()
        for item in raw_data:
            if isinstance(item, dict) and id_key in item:
                raw_data_ids.add(str(item[id_key]))
        
        # 両方に存在するIDが同じかチェック
        return data_map_ids == raw_data_ids


def create_copy_manager(app_state: Dict[str, Any], ui_controls: Dict[str, Any], page=None, event_hub=None) -> CopyManager:
    """CopyManagerのインスタンスを作成する工場関数"""
    copy_manager = CopyManager(app_state, ui_controls, page, event_hub)
    app_state["copy_manager"] = copy_manager
    return copy_manager