"""
drag_drop_manager.py
ドラッグ＆ドロップ操作を管理するマネージャークラス

FleDjSONでのドラッグ＆ドロップ機能を提供する
ノードの移動、階層構造の編集、ツリービューの操作などの機能を担当する
"""

import flet as ft
from flet import Colors
from typing import Dict, List, Any, Optional, Callable, Tuple, Set, Union
from translation import t


class DragDropManager:
    """
    ドラッグ＆ドロップ機能を管理するクラス
    
    ノードのドラッグ＆ドロップ操作、ツリー構造の編集、深度の更新などを担当する
    UI要素のドラッグ状態やドロップ先の視覚的フィードバックも提供する
    
    Attributes:
        app_state (Dict): アプリケーションの状態を保持する辞書
        ui_controls (Dict): UIコントロールを保持する辞書
        page (ft.Page): Fletページオブジェクト
        ui_state_manager: UIStateManagerのインスタンス
        data_manager: DataManagerのインスタンス
        ui_manager: UIManagerのインスタンス
    """
    
    def __init__(self, app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None):
        """
        初期化
        
        Args:
            app_state: アプリケーションの状態辞書
            ui_controls: UIコントロールの辞書
            page: Fletページ
        """
        self.app_state = app_state
        self.ui_controls = ui_controls
        self.page = page or app_state.get("page")
        
        # 他のマネージャーへの参照（初期化後に設定される）
        self.ui_state_manager = None
        self.data_manager = None
        self.ui_manager = None
        
        # app_stateから既存のマネージャーがあれば取得
        self._load_managers_from_app_state()
        
        # DragDropManagerをapp_stateに登録
        self.app_state["drag_drop_manager"] = self
        
        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] DragDropManager initialized.")
    
    def _load_managers_from_app_state(self):
        """app_stateから他のマネージャーへの参照を取得"""
        if "ui_state_manager" in self.app_state:
            self.ui_state_manager = self.app_state["ui_state_manager"]
        
        if "data_manager" in self.app_state:
            self.data_manager = self.app_state["data_manager"]
        
        if "ui_manager" in self.app_state:
            self.ui_manager = self.app_state["ui_manager"]
    
    def set_ui_state_manager(self, ui_state_manager):
        """UIStateManagerを設定"""
        self.ui_state_manager = ui_state_manager
        return self
    
    def set_data_manager(self, data_manager):
        """DataManagerを設定"""
        self.data_manager = data_manager
        return self
    
    def set_ui_manager(self, ui_manager):
        """UIManagerを設定"""
        self.ui_manager = ui_manager
        return self
    
    def on_drag_hover(self, e: ft.ControlEvent, is_hovering: bool, is_node: bool = False):
        """
        DragTargetのホバー状態に応じて見た目を変更する
        
        Args:
            e: ControlEventオブジェクト
            is_hovering: ホバー中かどうか
            is_node: ノード自体へのドラッグかどうか
        """
        target_control = e.control.content if isinstance(e.control, ft.DragTarget) else e.control
        target_data = e.control.data if hasattr(e.control, 'data') else {}
        target_id = target_data.get("parent_id") if is_node else target_data.get("before_id")

        try:
            if is_node:
                if hasattr(target_control, 'bgcolor'):
                    original_bgcolor = Colors.with_opacity(0.05, Colors.PRIMARY) if self.app_state.get("selected_node_id") == target_id else None
                    target_control.bgcolor = Colors.PRIMARY_CONTAINER if is_hovering else original_bgcolor
            else:
                if hasattr(target_control, 'bgcolor'):
                    target_control.bgcolor = Colors.PRIMARY if is_hovering else None
                    target_control.height = 10 if is_hovering else 5

            if hasattr(target_control, '_page') and target_control._page is not None:
                target_control.update()
            elif e.page is not None:
                e.page.update()
        except Exception as ex:
            print(f"[WARNING] Warning: Error in on_drag_hover: {ex}")
    
    def find_node_parent_and_index(self, target_node_id: str) -> Tuple[Optional[str], Optional[int]]:
        """
        指定されたノードIDの親IDとその子リスト内でのインデックスを返す
        
        Args:
            target_node_id: 対象ノードのID
            
        Returns:
            Tuple[親ノードID, インデックス]。親がない場合は(None, index)を返す
        """
        for parent_id, children_ids in self.app_state["children_map"].items():
            if target_node_id in children_ids:
                try:
                    index = children_ids.index(target_node_id)
                    return parent_id, index
                except ValueError:
                    continue
        if target_node_id in self.app_state["root_ids"]:
            try:
                index = self.app_state["root_ids"].index(target_node_id)
                return None, index
            except ValueError:
                pass
        return None, None
    
    def get_node_depth(self, node_id: str, current_depth: int = 0, visited: Optional[set] = None) -> Optional[int]:
        """
        指定されたノードIDの深さを返す (再帰的に探索)
        
        Args:
            node_id: 対象ノードのID
            current_depth: 現在の深さ（再帰呼び出し用）
            visited: 処理済みノードのセット（循環参照防止用）
            
        Returns:
            ノードの深さ（階層レベル）
        """
        if visited is None:
            visited = set()
        if node_id in visited:
            return None
        visited.add(node_id)

        depth_key = self.app_state.get("depth_key")
        if depth_key:
            node_data = self.app_state["data_map"].get(node_id)
            if node_data and depth_key in node_data:
                try:
                    return int(node_data[depth_key])
                except (ValueError, TypeError):
                    pass

        parent_id, _ = self.find_node_parent_and_index(node_id)
        if parent_id is None:
            return 0
        else:
            parent_depth = self.get_node_depth(parent_id, current_depth + 1, visited)
            return parent_depth + 1 if parent_depth is not None else None
    
    def update_node_depth_recursive(self, node_id: str, new_depth: int):
        """
        指定されたノードとその子孫の深さを再帰的に更新する
        
        Args:
            node_id: 更新するノードのID
            new_depth: 設定する新しい深さ
        """
        depth_key = self.app_state.get("depth_key")
        if not depth_key: 
            return

        node_data = self.app_state["data_map"].get(node_id)
        if node_data and isinstance(node_data, dict):
            node_data[depth_key] = new_depth
            
            # raw_dataの対応するノードも更新
            id_key = self.app_state.get("id_key")
            if id_key:
                raw_obj = next((item for item in self.app_state["raw_data"] 
                              if isinstance(item, dict) and str(item.get(id_key)) == node_id), None)
                if raw_obj:
                    raw_obj[depth_key] = new_depth

        # 子ノードも再帰的に更新
        children_ids = self.app_state["children_map"].get(node_id, [])
        for child_id in children_ids:
            self.update_node_depth_recursive(child_id, new_depth + 1)
    
    def is_ancestor(self, potential_ancestor_id: str, node_id: str, visited: Optional[set] = None) -> bool:
        """
        potential_ancestor_id が node_id の祖先であるかチェックする
        
        Args:
            potential_ancestor_id: 祖先候補のノードID
            node_id: 子孫候補のノードID
            visited: 処理済みノードのセット（循環参照防止用）
            
        Returns:
            祖先関係が存在する場合はTrue
        """
        if visited is None:
            visited = set()
        if node_id in visited:
            return False
        visited.add(node_id)

        parent_id, _ = self.find_node_parent_and_index(node_id)
        if parent_id is None:
            return False
        if parent_id == potential_ancestor_id:
            return True
        return self.is_ancestor(potential_ancestor_id, parent_id, visited)
    
    def get_ordered_node_ids(self, node_ids: List[str]) -> List[str]:
        """
        指定されたノードIDリストから深さ優先順のIDリストを生成する
        
        Args:
            node_ids: 順序付けするノードIDのリスト
            
        Returns:
            深さ優先順に並べられたノードIDのリスト
        """
        ordered_ids = []
        for node_id in node_ids:
            ordered_ids.append(node_id)
            children_ids = self.app_state["children_map"].get(node_id, [])
            if children_ids:
                ordered_ids.extend(self.get_ordered_node_ids(children_ids))
        return ordered_ids
    
    def reorder_raw_data(self):
        """app_stateのツリー構造に基づいてraw_dataを並び替える"""
        print("[UPDATE] Reordering raw_data based on tree structure...")
        
        # DataManagerが利用可能ならそちらに処理を委譲
        if self.data_manager:
            self.data_manager.reorder_raw_data()
            return
            
        # DataManagerが利用できない場合の内部実装
        id_key = self.app_state.get("id_key")
        if not id_key:
            print("[ERROR] Cannot reorder raw_data: ID key not found.")
            return

        ordered_node_ids = self.get_ordered_node_ids(self.app_state["root_ids"])

        raw_data_map = {str(item.get(id_key)): item for item in self.app_state["raw_data"] 
                       if isinstance(item, dict) and id_key in item}

        new_raw_data = []
        missing_ids = []
        for node_id in ordered_node_ids:
            if node_id in raw_data_map:
                new_raw_data.append(raw_data_map[node_id])
            else:
                missing_ids.append(node_id)
                print(f"[WARNING] Node ID {node_id} found in tree structure but missing in raw_data_map during reorder.")

        original_ids = set(raw_data_map.keys())
        ordered_set = set(ordered_node_ids)
        orphaned_ids = original_ids - ordered_set
        if orphaned_ids:
            print(f"[WARNING] Found orphaned nodes in raw_data not present in the final tree structure: {orphaned_ids}")

        self.app_state["raw_data"] = new_raw_data
        print(f"[OK] raw_data reordered. New length: {len(self.app_state['raw_data'])}")
        if missing_ids:
            print(f"[QUESTION] Missing IDs during reorder: {missing_ids}")
    
    def on_node_drop(self, e: ft.ControlEvent):
        """
        ノードがドロップされたときの処理
        
        Args:
            e: ドロップイベントのControlEvent
        """
        dragged_node_id = e.page.get_control(e.src_id).data
        target_info = e.control.data

        print(f"[MOVE] Node dropped: {dragged_node_id} -> {target_info}")
        target_type = target_info.get("target_type")
        target_id = target_info.get("before_id") if target_type == "sibling" else target_info.get("parent_id")

        # 自分自身へのドロップを防止
        if dragged_node_id == target_id:
            print("[ERROR] Cannot drop node onto itself.")
            try:
                from notification_system import NotificationSystem
                notification_system = NotificationSystem(e.page)
                notification_system.show_save_error(t("error.cannot_drop_self"))
            except Exception as notif_ex:
                print(f"代替通知システムエラー: {notif_ex}")
                try:
                    e.page.snack_bar = ft.SnackBar(ft.Text(t("error.cannot_drop_self")), open=True, bgcolor=Colors.RED)
                    e.page.update()
                except:
                    print("[WARNING] 全ての通知方法が失敗しました")
            return

        # 子孫への親ドロップを防止（循環参照になるため）
        if target_type == "parent" and self.is_ancestor(dragged_node_id, target_id):
            print(f"[ERROR] Cannot drop node {dragged_node_id} onto its descendant {target_id}.")
            try:
                from notification_system import NotificationSystem
                notification_system = NotificationSystem(e.page)
                notification_system.show_save_error(t("error.cannot_drop_descendant"))
            except Exception as notif_ex:
                print(f"代替通知システムエラー: {notif_ex}")
                try:
                    e.page.snack_bar = ft.SnackBar(ft.Text(t("error.cannot_drop_descendant")), open=True, bgcolor=Colors.RED)
                    e.page.update()
                except:
                    print("[WARNING] 全ての通知方法が失敗しました")
            return

        # 元の位置情報を取得
        original_parent_id, original_index = self.find_node_parent_and_index(dragged_node_id)
        if original_index is None:
            print(f"[ERROR] Could not find original position for node {dragged_node_id}.")
            return

        # 元の親から削除
        if original_parent_id:
            if original_parent_id in self.app_state["children_map"]:
                try:
                    self.app_state["children_map"][original_parent_id].pop(original_index)
                    print(f"  Removed {dragged_node_id} from children_map of {original_parent_id}")
                except IndexError:
                     print(f"[WARNING] Index error removing {dragged_node_id} from children_map of {original_parent_id}")
            else:
                print(f"[WARNING] Original parent {original_parent_id} not found in children_map")
        else:
            try:
                self.app_state["root_ids"].pop(original_index)
                print(f"  Removed {dragged_node_id} from root_ids")
            except IndexError:
                print(f"[WARNING] Index error removing {dragged_node_id} from root_ids")

        # raw_dataの親子関係も更新
        children_key = self.app_state.get("children_key")
        id_key = self.app_state.get("id_key")
        if children_key and original_parent_id and id_key:
            original_parent_raw = next((item for item in self.app_state["raw_data"] 
                                    if isinstance(item, dict) and str(item.get(id_key)) == original_parent_id), None)
            if original_parent_raw and children_key in original_parent_raw and isinstance(original_parent_raw[children_key], list):
                try:
                    # IDの型（文字列か数値か）に合わせて削除
                    if any(isinstance(child, int) for child in original_parent_raw[children_key]):
                        try:
                            dragged_node_id_int = int(dragged_node_id)
                            original_parent_raw[children_key].remove(dragged_node_id_int)
                        except (ValueError, TypeError):
                            original_parent_raw[children_key].remove(dragged_node_id)
                    else:
                        original_parent_raw[children_key].remove(dragged_node_id)
                    print(f"  Removed {dragged_node_id} from raw_data children of {original_parent_id}")
                except ValueError:
                     print(f"[WARNING] Node {dragged_node_id} not found in raw_data children of {original_parent_id}")

        # 兄弟としてのドロップ処理
        if target_type == "sibling":
            insert_before_id = target_id
            target_parent_id, target_index = self.find_node_parent_and_index(insert_before_id) if insert_before_id else (None, len(self.app_state["root_ids"]))

            if target_index is None and insert_before_id is not None:
                 print(f"[ERROR] Cannot find insertion point for sibling before {insert_before_id}")
                 # UIManagerへ処理を委譲してツリービューを更新
                 if self.ui_manager and hasattr(self.ui_manager, "update_tree_view"):
                     self.ui_manager.update_tree_view()
                 else:
                     print("[WARNING] UIマネージャーが利用できないため、ツリービュー更新をスキップします")
                 return

            # children_mapを更新
            if target_parent_id:
                if target_parent_id not in self.app_state["children_map"]: 
                    self.app_state["children_map"][target_parent_id] = []
                self.app_state["children_map"][target_parent_id].insert(target_index, dragged_node_id)
                print(f"  Inserted {dragged_node_id} into children_map of {target_parent_id} at index {target_index}")
            else:
                self.app_state["root_ids"].insert(target_index, dragged_node_id)
                print(f"  Inserted {dragged_node_id} into root_ids at index {target_index}")

            # raw_dataも更新
            if children_key and target_parent_id and id_key:
                target_parent_raw = next((item for item in self.app_state["raw_data"] 
                                       if isinstance(item, dict) and str(item.get(id_key)) == target_parent_id), None)
                if target_parent_raw:
                    if children_key not in target_parent_raw or not isinstance(target_parent_raw[children_key], list):
                        target_parent_raw[children_key] = []
                    
                    # IDの型（文字列か数値か）に合わせて挿入
                    node_id_to_insert = dragged_node_id
                    if target_parent_raw[children_key] and any(isinstance(child, int) for child in target_parent_raw[children_key]):
                        try:
                            node_id_to_insert = int(dragged_node_id)
                        except (ValueError, TypeError):
                            print(f"[WARNING] Could not convert {dragged_node_id} to int for raw_data children")
                    
                    safe_target_index = min(target_index, len(target_parent_raw[children_key]))
                    target_parent_raw[children_key].insert(safe_target_index, node_id_to_insert)
                    print(f"  Inserted {node_id_to_insert} into raw_data children of {target_parent_id} at index {safe_target_index}")

            # 深さを再計算して更新
            new_depth = self.get_node_depth(dragged_node_id)
            original_depth = self.get_node_depth(dragged_node_id, visited=set())
            if new_depth is not None and original_depth != new_depth:
                 print(f"  Updating depth for {dragged_node_id} from {original_depth} to {new_depth}")
                 self.update_node_depth_recursive(dragged_node_id, new_depth)

        # 親としてのドロップ処理
        elif target_type == "parent":
            new_parent_id = target_id

            # children_mapを更新
            if new_parent_id not in self.app_state["children_map"]: 
                self.app_state["children_map"][new_parent_id] = []
            self.app_state["children_map"][new_parent_id].append(dragged_node_id)
            print(f"  Appended {dragged_node_id} to children_map of {new_parent_id}")

            # raw_dataも更新
            if children_key and id_key:
                new_parent_raw = next((item for item in self.app_state["raw_data"] 
                                    if isinstance(item, dict) and str(item.get(id_key)) == new_parent_id), None)
                if new_parent_raw:
                    if children_key not in new_parent_raw or not isinstance(new_parent_raw[children_key], list):
                        new_parent_raw[children_key] = []
                    
                    # IDの型（文字列か数値か）に合わせて追加
                    node_id_to_append = dragged_node_id
                    if new_parent_raw[children_key] and any(isinstance(child, int) for child in new_parent_raw[children_key]):
                        try:
                            node_id_to_append = int(dragged_node_id)
                        except (ValueError, TypeError):
                            print(f"[WARNING] Could not convert {dragged_node_id} to int for raw_data children")
                    
                    new_parent_raw[children_key].append(node_id_to_append)
                    print(f"  Appended {node_id_to_append} to raw_data children of {new_parent_id}")

            # 深さを再計算して更新
            new_parent_depth = self.get_node_depth(new_parent_id)
            if new_parent_depth is not None:
                new_depth = new_parent_depth + 1
                print(f"  Updating depth recursively for {dragged_node_id} starting from {new_depth}")
                self.update_node_depth_recursive(dragged_node_id, new_depth)
            else:
                print(f"[WARNING] Could not determine depth for new parent {new_parent_id}. Depth update skipped.")

        # raw_dataの順序を再構築
        self.reorder_raw_data()

        # ID自動整列機能の実行（ドラッグ終了後に自動的にIDを振り直し）
        target_parent_id = None
        if target_type == "sibling":
            # 兄弟ノードとしてドロップされた場合は、その親のIDを取得
            target_parent_id, _ = self.find_node_parent_and_index(target_id) if target_id else (None, None)
        elif target_type == "parent":
            # 親ノードとしてドロップされた場合は、そのノードのIDを使用
            target_parent_id = new_parent_id
        else:
            # 不明なターゲットタイプの場合はルートノードとして扱う
            target_parent_id = None
        
        # 自動連番機能の実行（オプション確認）
        if self.app_state.get("auto_renumber_enabled", True):  # デフォルトは有効
            # ターゲット親ノード配下の子ノードをデバッグ出力
            children = self.app_state["children_map"].get(target_parent_id, []) if target_parent_id is not None else self.app_state["root_ids"]
            
            # ID自動整列処理を実行
            print(f"[UPDATE] ID自動整列処理を開始します - 親ノードID: {target_parent_id}")
            updated_ids = self.realign_sibling_ids(target_parent_id)
            print(f"[UPDATE] ID自動整列処理が完了しました - 更新されたノード数: {updated_ids}")
            
            if updated_ids > 0:
                print(f"[UPDATE] ドラッグ後のID自動整列: {updated_ids}個のノードIDを更新しました")
                # 通知システムを使用して成功メッセージを表示
                notification_system = self.app_state.get("notification_system")
                if notification_system:
                    notification_system.show_info(t("notification.auto_align_ids").format(count=updated_ids))
            else:
                print("[WARNING] ID自動整列: 更新するノードがありませんでした")
            
            # 元の親の兄弟も再整列（兄弟移動の場合）
            if target_type == "sibling" and original_parent_id != target_parent_id:
                original_updated = self.realign_sibling_ids(original_parent_id)
                if original_updated > 0:
                    print(f"[OK] 元親の自動連番実行: {original_updated}個のIDを更新しました")

        # ツリービューを更新
        if self.ui_manager and hasattr(self.ui_manager, "update_tree_view"):
            self.ui_manager.update_tree_view()
        else:
            print("[WARNING] UIマネージャーが利用できないため、ツリービュー更新をスキップします")

        # ドラッグホバー状態をリセット
        self.on_drag_hover(e, False, is_node=(target_info.get("target_type") == "parent"))
    
    def remove_node_from_parent(self, node_id: str) -> bool:
        """
        ノードを現在の親から削除する
        
        Args:
            node_id: 削除するノードのID
            
        Returns:
            削除が成功した場合はTrue
        """
        # 全親子関係をチェック
        for parent_id, children in self.app_state["children_map"].items():
            if node_id in children:
                # ノードを親からの参照リストから削除
                self.app_state["children_map"][parent_id] = [c for c in children if c != node_id]
                return True
        
        return False
    
    def on_drag_start(self, e: ft.ControlEvent):
        """
        ドラッグ開始時の処理
        
        Args:
            e: ドラッグイベントのControlEvent
        """
        # ドラッグ中のノードIDを保存
        self.app_state["dragging_node_id"] = e.control.data
    
    def on_drag_end(self, e: ft.ControlEvent):
        """
        ドラッグ終了時の処理
        
        Args:
            e: ドラッグイベントのControlEvent
        """
        # ドラッグ中のノードIDをリセット
        self.app_state["dragging_node_id"] = None

    def parse_node_id(self, node_id: Union[str, int]) -> Tuple[str, Optional[int]]:
        """
        ノードIDをプレフィックスと末尾の数値部分に分離する
        
        Args:
            node_id: 解析対象のノードID（文字列または数値）
            
        Returns:
            tuple: (prefix, number) の形式。数値部分がない場合は number=None
        """
        import re
        
        if node_id is None:
            return "", None
            
        # 数値型の場合は直接処理
        if isinstance(node_id, int):
            return "", node_id
            
        # 文字列化
        node_id_str = str(node_id)
        
        # 整数値だけの文字列の場合
        if node_id_str.isdigit():
            return "", int(node_id_str)
            
        # 正規表現パターン: 文字列の末尾にある数字をキャプチャ
        match = re.search(r'^(.*?)(\d+)$', node_id_str)
        if match:
            prefix, number_str = match.groups()
            return prefix, int(number_str)
        
        # 数値部分が見つからない場合
        return node_id_str, None

    def group_sibling_nodes_by_prefix(self, sibling_ids: List[Union[str, int]]) -> Dict[str, List[Union[str, int]]]:
        """
        兄弟ノードをプレフィックスごとにグループ化する
        
        数値部分を持つIDのみをグループ化し、数値型IDと文字列型IDの混在にも対応
        
        Args:
            sibling_ids: 同じ親を持つノードIDのリスト
            
        Returns:
            dict: プレフィックスをキーとしたノードIDグループの辞書
        """
        from collections import defaultdict
        groups = defaultdict(list)
        
        
        for i, node_id in enumerate(sibling_ids):
            if node_id is None:
                print(f"  [WARNING] 警告: ノードID[{i}]がNoneです")
                continue
            
            # 型の確認と処理
            prefix, number = self.parse_node_id(node_id)
            
            if number is not None:  # 数値部分があるIDのみグループ化
                print(f"  [OK] ノードID '{node_id}' をグループ化: プレフィックス='{prefix}', 数値部分={number}")
                groups[prefix].append(node_id)
            else:
                print(f"  ⏩ ノードID '{node_id}' は数値部分がないためグループ化しません")
        
        # 特殊なケース: 数値型IDと数値文字列IDの両方が空プレフィックスグループに存在する場合
        if "" in groups and len(groups[""]) > 1:
            # 数値型IDと文字列型IDが混在していないか確認
            numeric_ids = groups[""]
            has_mixed_types = any(isinstance(id, int) for id in numeric_ids) and any(isinstance(id, str) for id in numeric_ids)
            
            if has_mixed_types:
                print(f"  [UPDATE] 数値型IDと文字列型IDが混在しているため、文字列に統一します: {numeric_ids}")
                # 全て文字列に統一
                string_ids = [str(id) for id in numeric_ids]
                groups[""] = string_ids
        
        # グループ化結果を返す
        return groups

    def rename_node_id(self, old_id: Union[str, int], new_id: Union[str, int]) -> bool:
        """
        ノードのIDを変更し、関連するすべてのデータ構造を更新する
        
        Args:
            old_id: 変更前のノードID (文字列または数値)
            new_id: 変更後のノードID (文字列または数値)
            
        Returns:
            bool: 変更が成功したかどうか
        """
        # 文字列型に統一して比較
        old_id_str = str(old_id)
        new_id_str = str(new_id)
        
        # 不要な更新を避ける
        if old_id_str == new_id_str:
            print(f"  [INFO] IDが同一のため更新をスキップ: {old_id} == {new_id}")
            return True
        
        # 新しいIDが既に存在する場合は競合エラー
        if new_id_str in self.app_state["data_map"] or new_id in self.app_state["data_map"]:
            print(f"[WARNING] ID競合エラー: {new_id} は既に存在しています")
            return False
        
        try:
            # 1. data_mapのエントリを更新
            # 数値型と文字列型の両方をチェック
            if old_id in self.app_state["data_map"]:
                node_data = self.app_state["data_map"].pop(old_id)
            elif old_id_str in self.app_state["data_map"]:
                node_data = self.app_state["data_map"].pop(old_id_str)
            else:
                print(f"  [WARNING] data_map内にノード {old_id} が見つかりません")
                return False
            
            # 新しいIDを追加
            self.app_state["data_map"][new_id] = node_data
            print(f"  [OK] data_mapのエントリを更新: {old_id} → {new_id}")
                
            # IDフィールド自体も更新（id_keyが指定されている場合）
            id_key = self.app_state.get("id_key")
            if id_key and id_key in node_data:
                # IDの型を保持する必要があるか判断
                original_type = type(node_data[id_key])
                
                # 新しいIDの型変換（元の型に合わせる）
                converted_new_id = new_id
                if original_type == int and not isinstance(new_id, int):
                    try:
                        converted_new_id = int(new_id)
                        print(f"  [INFO] 整数型に変換: {new_id} → {converted_new_id}")
                    except (ValueError, TypeError):
                        print(f"  [WARNING] 整数型への変換に失敗: {new_id}")
                elif original_type == str and not isinstance(new_id, str):
                    converted_new_id = str(new_id)
                    print(f"  [INFO] 文字列型に変換: {new_id} → {converted_new_id}")
                    
                # 内部データのIDも更新
                node_data[id_key] = converted_new_id
                print(f"  [OK] ノードデータのIDフィールドを更新: {id_key}={converted_new_id}")
            
            # 2. children_mapの更新（親としての参照）
            if old_id in self.app_state["children_map"]:
                children = self.app_state["children_map"].pop(old_id)
                self.app_state["children_map"][new_id] = children
                print(f"  [OK] children_mapエントリを更新: {old_id} → {new_id}")
            elif old_id_str in self.app_state["children_map"]:
                children = self.app_state["children_map"].pop(old_id_str)
                self.app_state["children_map"][new_id] = children
                print(f"  [OK] children_mapエントリを更新: {old_id_str} → {new_id}")
            
            # 3. 全ての親ノードのchildren_map内での参照を更新
            for parent_id, children in self.app_state["children_map"].items():
                # 数値型と文字列型の両方をチェック
                for check_id in [old_id, old_id_str]:
                    if check_id in children:
                        index = children.index(check_id)
                        children[index] = new_id
                        print(f"  [OK] 親ノード {parent_id} の子リスト内の参照を更新")
            
            # 4. root_idsの更新
            # 数値型と文字列型の両方をチェック
            for check_id in [old_id, old_id_str]:
                if check_id in self.app_state["root_ids"]:
                    index = self.app_state["root_ids"].index(check_id)
                    self.app_state["root_ids"][index] = new_id
                    print(f"  [OK] root_ids内の参照を更新: {check_id} → {new_id}")
            
            # 5. raw_dataの更新
            id_key = self.app_state.get("id_key")
            updated_raw = False
            if id_key and isinstance(self.app_state.get("raw_data"), list):
                for item in self.app_state["raw_data"]:
                    if isinstance(item, dict) and id_key in item:
                        item_id = item.get(id_key)
                        # 文字列化して比較
                        if str(item_id) == old_id_str:
                            # IDの型を保持
                            if isinstance(item_id, int) and not isinstance(new_id, int):
                                try:
                                    item[id_key] = int(new_id)
                                except (ValueError, TypeError):
                                    item[id_key] = new_id
                            else:
                                item[id_key] = new_id
                            updated_raw = True
                            print(f"  [OK] raw_data内のノードID {old_id} を {new_id} に更新")
                
                # raw_data内の更新が見つからない場合の警告
                if not updated_raw:
                    print(f"  [WARNING] raw_data内に更新対象のノードが見つかりませんでした: {old_id}")
            
            # 6. children_keyがある場合、全raw_dataのchildren参照を更新
            children_key = self.app_state.get("children_key")
            if children_key and isinstance(self.app_state.get("raw_data"), list):
                for item in self.app_state["raw_data"]:
                    if isinstance(item, dict) and children_key in item and isinstance(item[children_key], list):
                        children_list = item[children_key]
                        # 数値型IDと文字列型IDの両方をチェック
                        for check_id in [old_id, old_id_str]:
                            if check_id in children_list:
                                index = children_list.index(check_id)
                                # 子リスト内のIDの型を保持
                                if isinstance(children_list[index], int) and not isinstance(new_id, int):
                                    try:
                                        children_list[index] = int(new_id)
                                    except (ValueError, TypeError):
                                        children_list[index] = new_id
                                else:
                                    children_list[index] = new_id
                                print(f"  [OK] raw_data内の子リスト参照を更新: {check_id} → {new_id}")
            
            # 7. 現在選択中のノードIDも更新
            if self.app_state.get("selected_node_id") in [old_id, old_id_str]:
                self.app_state["selected_node_id"] = new_id
                print(f"  [OK] 選択中ノードIDを更新: {old_id} → {new_id}")
            
            print(f"[UPDATE] ノードID変更完了: {old_id} → {new_id}")
            return True
            
        except Exception as e:
            print(f"[ERROR] ノードID変更中にエラーが発生: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def update_child_node_prefixes(self, old_parent_id: Union[str, int], new_parent_id: Union[str, int]) -> int:
        """親ノードが変更された際に、子ノードのIDプレフィックスを更新する"""
        updated_count = 0
        old_prefix, _ = self.parse_node_id(old_parent_id)
        new_prefix, _ = self.parse_node_id(new_parent_id)
        
        if old_prefix == new_prefix:
            return 0  # プレフィックスが同じ場合は更新不要
        
        # 子ノードを取得
        children = self.app_state["children_map"].get(str(old_parent_id), [])
        
        for child_id in children:
            child_prefix, child_number = self.parse_node_id(child_id)
            if child_prefix == old_prefix and child_number is not None:
                # 新しいプレフィックスでIDを生成
                new_child_id = f"{new_prefix}{child_number}"
                if self.rename_node_id(child_id, new_child_id):
                    updated_count += 1
                    # 再帰的に孫ノードも更新
                    updated_count += self.update_child_node_prefixes(child_id, new_child_id)
        
        return updated_count

    def realign_sibling_ids(self, parent_id: Optional[Union[str, int]] = None) -> int:
        """
        兄弟ノード（同じ親を持つノード）のIDを自動的に振り直す
        
        同じプレフィックスを持つノードのグループごとに、表示順に沿って連番を振り直します。
        二段階処理で安全に実行し、IDの衝突を回避します:
        1. まず一時的なIDに変換
        2. 次に昇順に連番を振って最終的なIDに変換
        
        Args:
            parent_id: 親ノードのID (Noneの場合はルートノードを処理)
            
        Returns:
            int: 更新されたノードの数
        """
        updated_count = 0
        
        try:
            # 対象ノードのリストを取得（コピーで作業）
            if parent_id is None:
                siblings = self.app_state["root_ids"].copy()
                print(f"[UPDATE] ルートノードのID自動整列を開始: {len(siblings)}個のノード")
            else:
                siblings = self.app_state["children_map"].get(str(parent_id), []).copy()
                print(f"[UPDATE] 親ノード '{parent_id}' の子ノードID自動整列を開始: {len(siblings)}個のノード")
            
            # ノードが少なすぎる場合は処理しない
            if len(siblings) < 2:
                return 0
            
            # プレフィックスでグループ化
            groups = self.group_sibling_nodes_by_prefix(siblings)
            print(f"  [OK] {len(groups)}個のプレフィックスグループを検出: {list(groups.keys())}")
            
            # 各グループでIDを振り直し
            for prefix, node_ids in groups.items():
                # 1つしかない場合は振り直し不要
                if len(node_ids) < 2:
                    print(f"  ⏩ プレフィックス '{prefix}' のノードは1つしかないため処理をスキップ: {node_ids}")
                    continue
                    
                
                # 第1段階: 一時IDに変換してID衝突を回避
                temp_ids = {}  # 元ID → 一時ID のマッピング
                for i, node_id in enumerate(node_ids):
                    temp_id = f"__temp_{prefix}_{i}"
                    temp_ids[node_id] = temp_id
                    print(f"    [UPDATE] 一時ID変換を試行: {node_id} → {temp_id}")
                    
                    if self.rename_node_id(node_id, temp_id):
                        print(f"    [OK] 一時ID変換成功: {node_id} → {temp_id}")
                    else:
                        print(f"    [ERROR] 一時ID変換失敗: {node_id} → {temp_id}")
                
                # 第2段階: インクリメントで最終IDに変換（表示順に連番振り）
                print(f"    [UPDATE] 最終ID変換開始 - {len(node_ids)}個のノード")
                
                # 表示順通りに連番を振る（1から始まる昇順）
                for i, orig_id in enumerate(node_ids):
                    temp_id = temp_ids[orig_id]
                    
                    # 数値のみでの連番を振るかどうかを判断
                    number_only = prefix == "" and all(isinstance(id, (int, str)) and (isinstance(id, int) or str(id).isdigit()) for id in node_ids)
                    
                    if number_only:
                        # 数値のみのIDの場合は整数型で振り直す
                        new_id = i + 1  # 数値型のID
                        print(f"    [INFO] 数値型IDを使用します: {i + 1}")
                    else:
                        # プレフィックス+数値の場合は文字列で連結
                        new_id = f"{prefix}{i + 1}"  # 文字列型のID
                    
                    print(f"    [UPDATE] 最終ID変換を試行: {temp_id} → {new_id} (元のID: {orig_id})")
                    
                    if self.rename_node_id(temp_id, new_id):
                        updated_count += 1
                        print(f"    [OK] 最終ID変換成功: {temp_id} → {new_id}")
                        
                        # 子ノードの接頭辞も更新（必要な場合）
                        if str(orig_id) != str(new_id):
                            print(f"    [UPDATE] 子ノードの接頭辞更新を試行: {orig_id} → {new_id}")
                            child_updates = self.update_child_node_prefixes(orig_id, new_id)
                            if child_updates > 0:
                                print(f"    [OK] 子孫ノード {child_updates}個の接頭辞を更新しました")
                                updated_count += child_updates
                    else:
                        print(f"    [ERROR] 最終ID変換失敗: {temp_id} → {new_id}")
            
            print(f"[UPDATE] ID自動整列完了: {updated_count}個のノードを更新")
            return updated_count
            
        except Exception as e:
            print(f"[ERROR] ID再整列エラー: {e}")
            import traceback
            print(traceback.format_exc())
            return 0

    def on_lock_change(self, e):
        """
        ドラッグ&ドロップロック状態の変更処理
        
        Args:
            e: チェックボックス変更イベント
        """
        try:
            lock_value = e.control.value
            self.app_state["tree_drag_locked"] = lock_value
            
            print(f"[LOCK] ドラッグ&ドロップロック状態変更: {lock_value}")
            
            # UIの更新が必要な場合はUIManagerを使用
            ui_manager = self.app_state.get("ui_manager")
            if ui_manager:
                # ツリービューの更新を要求（ドラッグ&ドロップの有効/無効を反映）
                ui_manager.update_tree_view()
                
            # ページ更新
            if self.page:
                self.page.update()
                
        except Exception as ex:
            print(f"[ERROR] ロック変更処理エラー: {ex}")


def create_drag_drop_manager(app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None) -> DragDropManager:
    """DragDropManagerのインスタンスを作成する工場関数"""
    drag_drop_manager = DragDropManager(app_state, ui_controls, page)
    app_state["drag_drop_manager"] = drag_drop_manager
    return drag_drop_manager