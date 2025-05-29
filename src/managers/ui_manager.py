"""
ui_manager.py
UI関連操作を担当するマネージャークラス

FleDjSONのUI関連の操作を担当し、ツリービューやその他のUIコンポーネントの
生成・更新・管理を行う
"""
import flet as ft
from flet import Colors, Draggable, DragTarget, Icons, ControlEvent, Page, Ref, FilePickerResultEvent
from typing import Optional, Dict, List, Any, Union, Tuple, Callable
import json
import os
import traceback
from collections import defaultdict
from optimizations import TreeOptimizer
from logging_config import get_logger
from managers.event_aware_manager import EventAwareManager
from event_hub import EventHub, EventType
from translation import t

# ロガーの取得
logger = get_logger(__name__)


class UIManager(EventAwareManager):
    """
    UI関連の操作とレンダリングを担当するマネージャークラス
    
    FleDjSONのUI要素の構築、更新、スタイル操作を管理する
    ツリービューの生成・更新やノードの表示形式の管理を担当する
    
    Attributes:
        app_state (Dict): アプリケーションの状態を保持する辞書
        ui_controls (Dict): UIコントロールを保持する辞書
        page (ft.Page): Fletページオブジェクト
    """
    
    def __init__(self, app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None):
        """
        UIManagerを初期化します。

        Args:
            app_state (Dict): アプリケーションの状態を保持する辞書
            ui_controls (Dict): UIコントロールを保持する辞書
            page (ft.Page, optional): Fletページオブジェクト
        """
        # EventAwareManagerの初期化
        super().__init__(
            app_state=app_state,
            ui_controls=ui_controls,
            page=page or app_state.get("page"),
            manager_name="ui_manager",
            event_hub=app_state.get("event_hub")
        )
        
        # コールバック関数の初期化
        self._on_drag_hover_callback = None
        self._on_node_drop_callback = None
        self._on_tree_node_select_callback = None
        self._theme_change_callback = None
        
        # 最適化関連の初期化
        self._tree_optimizer = None
        if "expanded_nodes" not in self.app_state:
            self.app_state["expanded_nodes"] = set()
        
        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] UIManager initialized with optimization support.")
    
    def _setup_event_subscriptions(self) -> None:
        """イベントハブへの購読を設定"""
        if self.event_hub:
            # 言語変更イベントを購読
            self.subscribe_to_event(EventType.LANGUAGE_CHANGED, self.on_language_changed)
    
    def on_language_changed(self, event) -> None:
        """言語変更時の処理"""
        logger.info(f"Language changed event received in UIManager")
        
        # 現在の展開状態を保存
        expanded_nodes = self.app_state.get("expanded_nodes", set()).copy()
        
        # UIテキストを更新
        self.update_ui_texts()
        
        # ツリービューが存在する場合は再生成
        if self.app_state.get("raw_data") is not None:
            self.update_tree_view()
            
            # 展開状態を復元
            self.app_state["expanded_nodes"] = expanded_nodes
    
    def update_ui_texts(self) -> None:
        """UI要素のテキストを現在の言語で更新"""
        # ツリービューの初期テキストを更新
        tree_view = self.ui_controls.get("tree_view")
        if tree_view and tree_view.controls and len(tree_view.controls) == 1:
            # 初期メッセージの場合のみ更新
            if hasattr(tree_view.controls[0], 'value'):
                current_value = tree_view.controls[0].value
                # 初期メッセージかどうかを判定（言語非依存）
                if current_value in ["ツリービューがここに表示されます...", "Tree view will appear here..."]:
                    tree_view.controls[0].value = t("tree.no_data")
                    tree_view.controls[0].update()
        
        # 詳細フォームの初期テキストを更新
        detail_form = self.ui_controls.get("detail_form_column")
        if detail_form and detail_form.controls and len(detail_form.controls) == 1:
            # 初期メッセージの場合のみ更新
            if hasattr(detail_form.controls[0], 'value'):
                current_value = detail_form.controls[0].value
                # 初期メッセージかどうかを判定（言語非依存）
                if current_value in ["ノードを選択してください", "Select a node"]:
                    detail_form.controls[0].value = t("form.select_node_message")
                    detail_form.controls[0].update()
    
    def toggle_expansion(self, e: ControlEvent):
        """
        ExpansionPanelの展開状態を切り替える
        
        Args:
            e: ControlEventオブジェクト
        """
        # クリックされたコンテナの親（ExpansionPanel）を取得
        container = e.control
        if not container or not container.page:
            return
            
        # コンテナから最も近い ExpansionPanelList を検索
        current = container
        panel_list = None
        panel = None
        
        # 親要素を遡って ExpansionPanel と ExpansionPanelList を見つける
        while current and current.page:
            if isinstance(current, ft.ExpansionPanel):
                panel = current
            elif isinstance(current, ft.ExpansionPanelList):
                panel_list = current
                break
            if hasattr(current, 'parent') and current.parent:
                current = current.parent
            else:
                break
        
        # 見つかったパネルの展開状態を反転
        if panel:
            panel.expanded = not panel.expanded
            panel.update()
        elif panel_list and panel_list.controls and len(panel_list.controls) > 0:
            # ExpansionPanelList が見つかった場合、最初のパネルの状態を反転
            first_panel = panel_list.controls[0]
            if isinstance(first_panel, ft.ExpansionPanel):
                first_panel.expanded = not first_panel.expanded
                first_panel.update()
    
    def get_node_display_label(self, node_id: str, node_data: Dict) -> str:
        """
        ノードの表示ラベルを取得する
        
        Args:
            node_id: ノードのID
            node_data: ノードのデータ
            
        Returns:
            表示用のラベル文字列
        """
        id_key = self.app_state.get("id_key")
        label_key = self.app_state.get("label_key")
        label = str(node_id)
        label_value = None
        
        # 仮想IDの場合の特別処理
        if id_key == "virtual_id" or node_id.startswith("item_"):
            # フラット構造データの場合は構造ベースで有用な情報を抽出
            if isinstance(node_data, dict):
                # 構造ベースで代表的なフィールドを見つける
                representative_field = self._find_representative_field(node_data)
                if representative_field:
                    field_name, field_value = representative_field
                    return f"{field_name}: {str(field_value)}"
                
                # 何も見つからない場合はオブジェクト情報を表示
                return f"JSON Object ({len(node_data)} fields)"
        
        # 内部要素（ドット区切りIDまたは配列インデックス）の場合の処理
        if ("." in node_id and not node_id.startswith("item_")) or "[" in node_id:
            if "[" in node_id and "]" in node_id:
                # 配列インデックス表記の場合 "item_0.products[0]"
                bracket_start = node_id.rfind("[")
                bracket_end = node_id.rfind("]")
                array_index = node_id[bracket_start+1:bracket_end]
                base_name = node_id[:bracket_start].split(".")[-1]  # 配列名
                
                if isinstance(node_data, dict):
                    return f"[ARRAY] {base_name}[{array_index}] ({len(node_data)} fields)"
                elif isinstance(node_data, list):
                    return f"[INFO] {base_name}[{array_index}] ({len(node_data)} items)"
                else:
                    return f"[FILE] {base_name}[{array_index}]: {str(node_data)}"
            else:
                # "item_0.organization" のような形式
                parts = node_id.split(".")
                field_name = parts[-1]  # 最後の部分がフィールド名
                
                if isinstance(node_data, dict):
                    # 辞書の場合は代表的なフィールドを探す
                    representative_field = self._find_representative_field(node_data)
                    if representative_field:
                        field_key, field_value = representative_field
                        return f"{field_key}: {str(field_value)}"
                    else:
                        return f"[FILE] {field_name} ({len(node_data)} fields)"
                elif isinstance(node_data, list):
                    return f"[INFO] {field_name} ({len(node_data)} items)"
                else:
                    return f"[FILE] {field_name}: {str(node_data)}"
        
        # 通常のIDキーがある場合の処理
        if label_key:
            data_manager = self.app_state.get("data_manager")
            if data_manager and hasattr(data_manager, "get_nested_value"):
                label_value = data_manager.get_nested_value(node_data, label_key)
            else:
                # フォールバック: データマネージャーが利用できない場合は直接アクセス
                keys = label_key.split('.')
                value = node_data
                try:
                    for key in keys:
                        if isinstance(value, dict):
                            value = value[key]
                        else:
                            value = None
                            break
                    label_value = value
                except (KeyError, TypeError):
                    label_value = None

        if label_value is not None and isinstance(label_value, (str, int, float, bool)):
             label = str(label_value)
             if id_key and id_key != label_key and '.' not in label_key and '[]' not in label_key and id_key in node_data:
                 label = f"{node_id}: {label}"
        elif isinstance(node_data, dict):
            fallback_label = None
            for key, value in node_data.items():
                 if key == id_key or key.startswith("_"): continue
                 if isinstance(value, (str, int, float, bool)) and value:
                     fallback_label = f"{key}: {str(value)}"
                     break
            if fallback_label:
                 label = fallback_label
            else:
                 label = f"Object ({node_id})"
        return label
    
    def update_node_style_recursive(self, controls: List[ft.Control], target_id: Optional[str], 
                                   is_selected: bool, force_label_update: bool = False) -> bool:
        """
        ツリービュー内の特定のノードのスタイルを再帰的に更新する
        
        Args:
            controls: 検索対象のコントロールリスト
            target_id: ターゲットノードID
            is_selected: 選択状態かどうか
            force_label_update: ラベルを強制的に更新するか
            
        Returns:
            更新が行われた場合はTrue
        """
        updated = False
        for item in controls:
            if hasattr(item, 'data') and item.data == target_id:
                item.bgcolor = ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY) if is_selected else None
                if isinstance(item.content, ft.Row) and len(item.content.controls) > 2 and isinstance(item.content.controls[2], ft.Text):
                    text_control = item.content.controls[2]
                    text_control.color = ft.Colors.PRIMARY if is_selected else None
                    text_control.weight = ft.FontWeight.BOLD if is_selected else None

                    if force_label_update:
                        node_data = self.app_state["data_map"].get(target_id)
                        if node_data:
                            new_label = self.get_node_display_label(target_id, node_data)
                            display_label = new_label
                            if len(display_label) > 50:
                                display_label = display_label[:47] + "..."
                            text_control.value = display_label

                item.update()
                updated = True
            
            # サブコントロールの検索
            if hasattr(item, 'controls') and isinstance(item.controls, list):
                sub_updated = self.update_node_style_recursive(item.controls, target_id, is_selected, force_label_update)
                updated = updated or sub_updated
            
            # Draggableの場合はそのコンテントを検索
            if isinstance(item, ft.Draggable) and hasattr(item, 'content') and item.content:
                if isinstance(item.content, ft.DragTarget) and hasattr(item.content, 'content'):
                    content = item.content.content
                    if hasattr(content, 'data') and content.data == target_id:
                        content.bgcolor = ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY) if is_selected else None
                        if isinstance(content.content, ft.Row) and len(content.content.controls) > 2 and isinstance(content.content.controls[2], ft.Text):
                            text_control = content.content.controls[2]
                            text_control.color = ft.Colors.PRIMARY if is_selected else None
                            text_control.weight = ft.FontWeight.BOLD if is_selected else None
                            
                            if force_label_update:
                                node_data = self.app_state["data_map"].get(target_id)
                                if node_data:
                                    new_label = self.get_node_display_label(target_id, node_data)
                                    display_label = new_label
                                    if len(display_label) > 50:
                                        display_label = display_label[:47] + "..."
                                    text_control.value = display_label
                            
                        content.update()
                        updated = True

        return updated
    
    def set_on_tree_node_select_callback(self, callback: Callable):
        """
        ツリーノード選択時のコールバックを設定する
        
        Args:
            callback: 選択時に呼び出すコールバック関数
        """
        self._on_tree_node_select_callback = callback
    
    def on_tree_node_select(self, e):
        """
        ツリービューのノードがクリックされたときの処理
        
        Args:
            e: ControlEventオブジェクト、または直接ノードIDを表す文字列
        """
        # カスタムコールバックが設定されている場合はそれを使用
        if self._on_tree_node_select_callback:
            self._on_tree_node_select_callback(e)
            return
            
        # 内部処理（FormManagerが初期化されていない場合のフォールバック）
        # eがControlEventの場合はdata属性からIDを取得、文字列の場合は直接使用
        if isinstance(e, str):
            selected_node_id = e  # 直接ノードIDとして使用
        else:
            selected_node_id = e.control.data  # data属性にはJSON内のユニークIDが格納されている
        
        logger.debug(f"Node selected: {selected_node_id}")

        # 移動ロックがオフの時（D&D可能な時）は編集不可
        if not self.app_state["tree_drag_locked"]:
            logger.debug("Edit not allowed - tree is in move mode")
            if not isinstance(e, str) and hasattr(e, 'page'):
                e.page.snack_bar = ft.SnackBar(
                    content=ft.Text(t("ui.move_mode_warning")),
                    action="OK"
                )
                e.page.update()
            return

        if self.app_state.get("selected_node_id") == selected_node_id:
            # 同じノードが再度クリックされた場合は何もしない
            return

        # --- 変更破棄の確認（オプション、今回はシンプルに破棄） ---
        if self.app_state.get("is_dirty"):
            logger.warning("Discarding unsaved changes in the detail form.")
            if "edit_buffer" in self.app_state:
                self.app_state["edit_buffer"].clear()
            self.app_state["is_dirty"] = False

        old_selected_id = self.app_state.get("selected_node_id")

        # UIStateManagerを使用してノード選択を処理
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager:
            ui_state_manager.select_node(selected_node_id)
        else:
            # UIStateManagerがない場合のフォールバック処理
            self.app_state["selected_node_id"] = selected_node_id
            
            # フォームマネージャーを探して詳細フォームを更新
            form_manager = self.app_state.get("form_manager")
            if form_manager:
                form_manager.update_detail_form(selected_node_id)
            
            # 古い選択項目のハイライト解除
            if old_selected_id:
                self.update_node_style_recursive(self.ui_controls["tree_view"].controls, old_selected_id, False)
            
            # 新しい選択項目のハイライト設定
            if selected_node_id:
                self.update_node_style_recursive(self.ui_controls["tree_view"].controls, selected_node_id, True)
    
    def set_on_drag_hover_callback(self, callback: Callable):
        """
        ドラッグホバー時のコールバックを設定する
        
        Args:
            callback: ドラッグホバー時に呼び出すコールバック関数
        """
        self._on_drag_hover_callback = callback
    
    def on_drag_hover(self, e, is_hovering: bool, is_node: bool = False):
        """
        ドラッグ中にドロップターゲット上でホバーした時の処理
        
        Args:
            e: ドラッグイベント
            is_hovering: ホバー中かどうか
            is_node: ノード自体への操作かどうか
        """
        # カスタムコールバックが設定されている場合はそれを使用
        if self._on_drag_hover_callback:
            self._on_drag_hover_callback(e, is_hovering, is_node)
            return
            
        # DragDropManagerが初期化されている場合はそちらに委譲
        drag_drop_manager = self.app_state.get("drag_drop_manager")
        if drag_drop_manager:
            drag_drop_manager.on_drag_hover(e, is_hovering, is_node)
            return
            
        # 内部処理（DragDropManagerが初期化されていない場合のフォールバック）
        if is_hovering:
            if is_node:
                # ノード自体へのドロップの場合は、子として追加するためのスタイル
                e.control.content.bgcolor = ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY)
            else:
                # ノード間へのドロップの場合は、兄弟として挿入するためのスタイル
                e.control.content.bgcolor = ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)
                e.control.content.height = 10
        else:
            # ホバーが終了したらスタイルをリセット
            e.control.content.bgcolor = None
            if not is_node:
                e.control.content.height = 5
        
        e.control.content.update()
    
    def set_on_node_drop_callback(self, callback: Callable):
        """
        ノードドロップ時のコールバックを設定する
        
        Args:
            callback: ドロップ時に呼び出すコールバック関数
        """
        self._on_node_drop_callback = callback
    
    def on_node_drop(self, e):
        """
        ドラッグしたノードをドロップした時の処理
        
        Args:
            e: ドロップイベント
        """
        # カスタムコールバックが設定されている場合はそれを使用
        if self._on_node_drop_callback:
            self._on_node_drop_callback(e)
            return
            
        # DragDropManagerが初期化されている場合はそちらに委譲
        drag_drop_manager = self.app_state.get("drag_drop_manager")
        if drag_drop_manager:
            drag_drop_manager.on_node_drop(e)
            return
            
        # DragDropManagerが初期化されていない場合は警告メッセージのみ表示
        logger.warning("DragDropManager not initialized. Node drop event ignored.")
        if hasattr(e, 'page') and e.page:
            e.page.snack_bar = ft.SnackBar(
                content=ft.Text(t("ui.drag_drop_unavailable")),
                action="OK"
            )
            e.page.snack_bar.open = True
            e.page.update()
    
    def build_list_tiles(self, node_ids: List[str], depth: int = 0) -> List[ft.Control]:
        """
        指定されたノードIDのリストからListTileのリストを再帰的に構築する
        
        Args:
            node_ids: ノードIDのリスト
            depth: 現在の階層の深さ
            
        Returns:
            構築されたコントロールのリスト
        """
        tiles = []
        id_key = self.app_state.get("id_key")
        label_key = self.app_state.get("label_key")

        # イベントハンドラ関数を作成する関数
        def create_on_accept_handler(node_id):
            def handler(e):
                if not self.app_state["tree_drag_locked"]:
                    self.on_node_drop(e)
            return handler
        
        def create_on_will_accept_handler(node_id, is_node=False):
            def handler(e):
                if not self.app_state["tree_drag_locked"]:
                    self.on_drag_hover(e, True, is_node=is_node)
            return handler
        
        def create_on_leave_handler(node_id, is_node=False):
            def handler(e):
                self.on_drag_hover(e, False, is_node=is_node)
            return handler

        for node_id in node_ids:
            sibling_drop_target = ft.DragTarget(
                group="tree_nodes",
                content=ft.Container(bgcolor=None, height=5, width=float("inf")),
                data={"target_type": "sibling", "before_id": node_id},
                on_accept=create_on_accept_handler(node_id),
                on_will_accept=create_on_will_accept_handler(node_id),
                on_leave=create_on_leave_handler(node_id),
            )

            node_data = self.app_state["data_map"].get(node_id)
            if node_data is None:
                continue
            
            # 辞書または配列のみを処理対象とする
            if not isinstance(node_data, (dict, list)):
                continue

            # ノードラベルの取得
            label = self.get_node_display_label(node_id, node_data)

            # 子ノードの有無（通常の階層構造 + フラット構造の内部要素）
            children_ids = self.app_state["children_map"].get(node_id, [])
            
            # フラット構造の場合は、内部のオブジェクトや配列も子として扱う（適切な粒度で）
            internal_children = []
            if not children_ids:
                # 現在の階層深度を計算
                current_depth = node_id.count('.') + node_id.count('[')
                
                if isinstance(node_data, dict):
                    # 辞書の場合: 意味のある内部要素のみを子として追加
                    for key, value in node_data.items():
                        if isinstance(value, (dict, list)) and value:
                            if self._should_expand_as_child(key, value, current_depth):
                                child_id = f"{node_id}.{key}"
                                internal_children.append(child_id)
                                # data_mapに一時的に追加（表示用）
                                if child_id not in self.app_state["data_map"]:
                                    self.app_state["data_map"][child_id] = value
                elif isinstance(node_data, list):
                    # 配列の場合: 意味のある要素のみを子として追加
                    for i, item in enumerate(node_data):
                        if isinstance(item, (dict, list)) and item:
                            if self._should_expand_as_child(f"[{i}]", item, current_depth):
                                child_id = f"{node_id}[{i}]"  # 配列インデックス表記
                                internal_children.append(child_id)
                                # data_mapに一時的に追加（表示用）
                                if child_id not in self.app_state["data_map"]:
                                    self.app_state["data_map"][child_id] = item
            
            # 実際の子IDリストを更新
            all_children = children_ids + internal_children
            has_children = bool(all_children)
            
            # 表示用ラベルの調整
            display_label = label
            if len(display_label) > 50:
                display_label = display_label[:47] + "..."

            # アイコンの設定
            icon = Icons.FOLDER_OPEN if has_children else Icons.ARTICLE_OUTLINED

            # リストタイルを構築
            list_tile = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(width=depth * 20),  # インデント
                        ft.Icon(
                            icon,
                            size=16,
                            color=ft.Colors.PRIMARY if has_children else ft.Colors.ON_SURFACE_VARIANT
                        ),
                        ft.Text(
                            display_label,
                            size=14,
                            color=ft.Colors.PRIMARY if self.app_state["selected_node_id"] == node_id else None,
                            weight=ft.FontWeight.BOLD if self.app_state["selected_node_id"] == node_id else None,
                        ),
                    ],
                    spacing=5
                ),
                padding=ft.padding.symmetric(vertical=6, horizontal=10),
                border_radius=5,
                data=node_id,
                on_click=self.on_tree_node_select,
                ink=True,
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY) if self.app_state["selected_node_id"] == node_id else None,
            )

            # ドラッグロック状態に応じてコントロールを追加
            if self.app_state["tree_drag_locked"]:
                tiles.append(sibling_drop_target)
                tiles.append(list_tile)
            else:
                # ドラッグ可能な状態の場合
                node_drop_target = ft.DragTarget(
                    group="tree_nodes",
                    content=list_tile,
                    data={"target_type": "parent", "parent_id": node_id},
                    on_accept=create_on_accept_handler(node_id),
                    on_will_accept=create_on_will_accept_handler(node_id, is_node=True),
                    on_leave=create_on_leave_handler(node_id, is_node=True),
                )

                draggable_item = ft.Draggable(
                    group="tree_nodes",
                    content=node_drop_target,
                    data=node_id,
                    disabled=self.app_state["tree_drag_locked"],
                    visible=True
                )
                tiles.append(sibling_drop_target)
                tiles.append(draggable_item)

            # 子要素が存在する場合は再帰的に処理
            if has_children:
                child_tiles = self.build_list_tiles(all_children, depth + 1)
                tiles.extend(child_tiles)

        # 最後のドロップターゲットを追加
        final_drop_target = ft.DragTarget(
            group="tree_nodes",
            content=ft.Container(bgcolor=None, height=5, width=float("inf")),
            data={"target_type": "sibling", "before_id": None},
            on_accept=create_on_accept_handler(None),
            on_will_accept=create_on_will_accept_handler(None),
            on_leave=create_on_leave_handler(None),
        )
        tiles.append(final_drop_target)

        return tiles
    
    def _should_expand_as_child(self, key: str, value, current_depth: int) -> bool:
        """
        指定されたkey-valueペアを子ノードとして展開すべきかどうかを判断する
        
        Args:
            key: フィールド名または配列インデックス
            value: 値（dict または list）
            current_depth: 現在の階層深度
            
        Returns:
            展開すべき場合はTrue、そうでなければFalse
        """
        
        # 1. 深すぎる場合は展開しない（最大4階層まで）
        if current_depth >= 4:
            logger.debug(f"[展開判定] 深度制限: {key} (depth={current_depth})")
            return False
        
        # 2. 配列の場合の判定
        if isinstance(value, list):
            # 空配列は展開しない
            if not value:
                return False
            
            # 文字列のみの配列は展開しない（amenities, deliverables等）
            if all(isinstance(item, (str, int, float, bool)) for item in value):
                logger.debug(f"[展開判定] 基本型配列: {key} ({len(value)} items)")
                return False
            
            # 小さな配列（5要素以下）で全て小さなオブジェクトの場合は展開しない
            if len(value) <= 5:
                all_small_objects = True
                for item in value:
                    if isinstance(item, dict) and len(item) > 3:
                        all_small_objects = False
                        break
                    elif not isinstance(item, dict):
                        all_small_objects = False
                        break
                if all_small_objects:
                    logger.debug(f"[展開判定] 小規模配列: {key} ({len(value)} small items)")
                    return False
        
        # 3. 辞書の場合の判定
        elif isinstance(value, dict):
            # 空辞書は展開しない
            if not value:
                return False
            
            # 小さなオブジェクト（3フィールド以下で全て基本型）は展開しない
            if len(value) <= 3:
                if all(isinstance(v, (str, int, float, bool)) for v in value.values()):
                    logger.debug(f"[展開判定] 小規模オブジェクト: {key} ({len(value)} fields, all primitive)")
                    return False
            
            # 構造的特徴に基づいて詳細オブジェクトかどうかを判定
            if self._is_detail_object(key, value):
                logger.debug(f"[展開判定] 詳細オブジェクト: {key}")
                return False
        
        # 4. 意味のある構造として展開する
        logger.debug(f"[展開判定] 展開許可: {key} ({type(value).__name__}, depth={current_depth})")
        return True
    
    def _find_representative_field(self, data: dict) -> Optional[Tuple[str, Any]]:
        """
        構造的特徴に基づいて代表的なフィールドを汎用的に特定
        
        Args:
            data: 分析対象の辞書データ
            
        Returns:
            (フィールド名, 値) のタプル、または None
        """
        
        # 1. 表示名らしき文字列フィールドを優先（言語スコア重視）
        display_candidates = []
        for k, v in data.items():
            if isinstance(v, str) and 1 <= len(v) <= 50 and not v.isdigit():
                lang_score = self._evaluate_field_name_for_display(k)
                display_candidates.append((k, v, lang_score, len(v)))
        
        # 高スコアの表示名候補があれば優先
        if display_candidates:
            high_score_candidates = [c for c in display_candidates if c[2] >= 2.0]
            if high_score_candidates:
                # 高スコアの中から文字数が適切なものを選択
                best_candidate = max(high_score_candidates, key=lambda x: (x[2], -x[3]))
                return (best_candidate[0], best_candidate[1])
        
        # 2. IDらしき数値・文字列フィールド
        id_candidates = []
        for k, v in data.items():
            if isinstance(v, (int, str)):
                lang_score = self._evaluate_field_name_for_id(k)
                if lang_score >= 2.0:  # ID らしさのスコアが高い場合のみ
                    id_candidates.append((k, v, lang_score))
        
        if id_candidates:
            best_candidate = max(id_candidates, key=lambda x: x[2])
            return (best_candidate[0], best_candidate[1])
        
        # 3. 中程度の表示名候補にフォールバック
        if display_candidates:
            best_candidate = max(display_candidates, key=lambda x: (x[2], -x[3]))
            return (best_candidate[0], best_candidate[1])
        
        # 4. その他の基本型フィールド（最終フォールバック）
        for k, v in data.items():
            if isinstance(v, (str, int, float, bool)) and not str(k).startswith("_"):
                return (k, v)
        
        return None
    
    def _evaluate_field_name_for_display(self, field_name: str) -> float:
        """
        フィールド名が表示用として適切かを評価（英語・日本語対応）
        
        Args:
            field_name: フィールド名
            
        Returns:
            適切度スコア（高いほど適切）
        """
        name_lower = field_name.lower()
        score = 0.0
        
        # 英語の表示名らしいキーワード
        en_display_keywords = ["name", "title", "label", "caption", "heading", "subject"]
        for keyword in en_display_keywords:
            if name_lower == keyword:
                score += 3.0
                break
            elif keyword in name_lower:
                score += 1.5
        
        # 日本語の表示名らしいキーワード
        ja_display_keywords = ["名前", "タイトル", "見出し", "件名", "表題", "氏名"]
        for keyword in ja_display_keywords:
            if keyword in field_name:
                score += 3.0
                break
        
        # フィールド名の短さ（表示名は短い傾向）
        if len(field_name) <= 8:
            score += 1.0
        elif len(field_name) <= 15:
            score += 0.5
        
        return score
    
    def _evaluate_field_name_for_id(self, field_name: str) -> float:
        """
        フィールド名がID用として適切かを評価（英語・日本語対応）
        
        Args:
            field_name: フィールド名
            
        Returns:
            適切度スコア（高いほど適切）
        """
        name_lower = field_name.lower()
        score = 0.0
        
        # 英語のID系キーワード
        if name_lower == "id":
            score += 5.0
        elif name_lower.endswith("_id") or name_lower.endswith("id"):
            score += 3.0
        elif "uuid" in name_lower or "guid" in name_lower:
            score += 2.0
        
        # 日本語のID系キーワード
        ja_id_keywords = ["識別子", "番号", "コード", "ID", "ＩＤ"]
        for keyword in ja_id_keywords:
            if keyword in field_name:
                score += 3.0
                break
        
        # フィールド名の短さ（IDは短い傾向）
        if len(field_name) <= 5:
            score += 2.0
        elif len(field_name) <= 10:
            score += 1.0
        
        return score
    
    def _is_detail_object(self, key: str, value: dict) -> bool:
        """
        構造的特徴に基づいて詳細オブジェクトかどうかを汎用判定
        
        Args:
            key: フィールド名
            value: 値（辞書）
            
        Returns:
            詳細オブジェクトの場合はTrue
        """
        
        # 座標系構造の検出（2つの数値ペア）
        if len(value) == 2:
            numeric_count = sum(1 for v in value.values() if isinstance(v, (int, float)))
            if numeric_count == 2:
                return True
        
        # 連絡先系構造の検出（短い文字列のみの小オブジェクト）
        if len(value) <= 4:
            string_fields = [v for v in value.values() if isinstance(v, str)]
            if len(string_fields) == len(value) and all(len(s) < 100 for s in string_fields):
                # 連絡先らしいフィールド名パターンの検出
                contact_score = self._evaluate_contact_like_structure(key, value)
                if contact_score > 2.0:
                    return True
        
        # 設定・メタデータ系構造の検出
        config_score = self._evaluate_config_like_structure(key, value)
        if config_score > 2.0 and len(value) <= 5:
            return True
        
        return False
    
    def _evaluate_contact_like_structure(self, key: str, value: dict) -> float:
        """
        連絡先らしい構造かどうかを評価
        
        Args:
            key: フィールド名
            value: 値（辞書）
            
        Returns:
            連絡先らしさスコア
        """
        score = 0.0
        key_lower = key.lower()
        
        # 英語の連絡先系キーワード
        en_contact_keywords = ["contact", "address", "phone", "email", "mail"]
        for keyword in en_contact_keywords:
            if keyword in key_lower:
                score += 2.0
                break
        
        # 日本語の連絡先系キーワード
        ja_contact_keywords = ["連絡先", "住所", "アドレス", "電話", "メール", "郵便"]
        for keyword in ja_contact_keywords:
            if keyword in key:
                score += 2.0
                break
        
        # フィールド値の特徴（メールアドレス、電話番号らしいパターン）
        for field_key, field_value in value.items():
            if isinstance(field_value, str):
                field_lower = field_key.lower()
                if "@" in field_value or "email" in field_lower or "mail" in field_lower:
                    score += 1.5
                elif field_value.replace("-", "").replace(" ", "").isdigit() and len(field_value) > 8:
                    score += 1.0  # 電話番号らしい
        
        return score
    
    def _evaluate_config_like_structure(self, key: str, value: dict) -> float:
        """
        設定・メタデータらしい構造かどうかを評価
        
        Args:
            key: フィールド名
            value: 値（辞書）
            
        Returns:
            設定らしさスコア
        """
        score = 0.0
        key_lower = key.lower()
        
        # 英語の設定系キーワード
        en_config_keywords = ["config", "settings", "metadata", "options", "preferences", "specifications", "spec"]
        for keyword in en_config_keywords:
            if keyword in key_lower:
                score += 2.0
                break
        
        # 日本語の設定系キーワード
        ja_config_keywords = ["設定", "構成", "メタデータ", "仕様", "オプション", "環境設定"]
        for keyword in ja_config_keywords:
            if keyword in key:
                score += 2.0
                break
        
        # 全て基本型で小さなオブジェクト（設定の特徴）
        if len(value) <= 5 and all(isinstance(v, (str, int, float, bool)) for v in value.values()):
            score += 1.0
        
        return score
    
    def update_tree_view(self, optimize=False):
        """解析結果に基づいてツリービューを再構築して更新する
        
        Args:
            optimize (bool): TreeOptimizerを使用して最適化するかどうか
        """
        logger.debug("Updating tree view..." + (" (optimized)" if optimize else ""))

        # データ存在チェック
        if not self.app_state.get("analysis_results") or not self.app_state.get("raw_data"):
            logger.error("No data available for tree view.")
            
            # ツリービューが存在するか確認
            tree_view = self.ui_controls.get("tree_view")
            if tree_view:
                tree_view.controls.clear()  # 既存のコントロールをクリア
                tree_view.controls = [ft.Text(t("ui.no_data_loaded"))]
                tree_view.update()
            return

        try:
            # 解析結果から必要な情報を取得
            analysis = self.app_state["analysis_results"]
            raw_data = self.app_state["raw_data"]

            id_key = analysis["heuristic_suggestions"].get("identifier")
            children_key = analysis["heuristic_suggestions"].get("children_link")
            depth_key = next((f["name"] for f in analysis["field_details"] if f["name"].endswith("depth")), None)
            label_key = analysis["heuristic_suggestions"].get("label")

            # app_stateのキー情報を更新（DataManagerが実行済みの場合は不要）
            self.app_state["id_key"] = id_key
            self.app_state["children_key"] = children_key
            self.app_state["depth_key"] = depth_key
            self.app_state["label_key"] = label_key


            # IDキーのチェック（データマップが構築されている場合は継続）
            if not id_key:
                logger.warning("No identifier key found, but checking if data_map is available...")
                
                # データマップが既に構築されている場合は平坦構造として処理
                if self.app_state.get("data_map") and len(self.app_state["data_map"]) > 0:
                    logger.info("Data map available - proceeding with flat structure visualization")
                    # 仮想IDキーを設定して処理を続行
                    id_key = "virtual_id"
                    self.app_state["id_key"] = id_key
                else:
                    logger.error("Cannot build tree: No data available.")
                    tree_view = self.ui_controls.get("tree_view")
                    if tree_view:
                        tree_view.controls = [ft.Text(t("error.no_data"))]
                        tree_view.update()
                    return

            # データマップとツリーが既に構築されているか確認
            if not self.app_state.get("data_map") or not self.app_state.get("root_ids"):
                logger.error("data_map or root_ids not found. Building data map...")
                
                # DataManagerに処理を委譲
                data_manager = self.app_state.get("data_manager")
                if data_manager:
                    data_manager.build_data_map_and_tree()
                    
                    # それでも構築できなかった場合はエラー表示
                    if not self.app_state.get("data_map") or not self.app_state.get("root_ids"):
                        tree_view = self.ui_controls.get("tree_view")
                        if tree_view:
                            tree_view.controls = [ft.Text(t("error.structure_build_failed"))]
                            tree_view.update()
                        return
                else:
                    logger.error("DataManager not available to build data_map and tree structure.")
                    return

            # ツリービューのコントロールが正しく存在するか確認
            if "tree_view" not in self.ui_controls or self.ui_controls["tree_view"] is None:
                logger.error("ツリービューコントロールが存在しません。")
                return
                
            try:
                # TreeOptimizerを使用する場合
                if optimize:
                    self._update_tree_view_optimized()
                else:
                    # 通常の更新処理
                    # リストタイルを構築
                    list_tiles = self.build_list_tiles(self.app_state["root_ids"], depth=0)
                    
                    # ツリービューのコントロールを明示的にクリアしてから設定
                    self.ui_controls["tree_view"].controls.clear()
                    for i, tile in enumerate(list_tiles):
                        self.ui_controls["tree_view"].controls.append(tile)
                    
                    # UIの表示設定
                    self.ui_controls["tree_view"].visible = True  # 明示的に可視性を設定
                    self.ui_controls["tree_view"].height = None   # 高さの制限を解除
                    self.ui_controls["tree_view"].expand = True   # 利用可能なスペースいっぱいに拡張
                
                # メインコンテンツエリアの表示保証
                self.ensure_main_content_visible()
                
                # UIStateManagerが利用可能な場合は更新メソッドを使用
                ui_state_manager = self.app_state.get("ui_state_manager")
                if ui_state_manager:
                    ui_state_manager.set_tree_view_dirty(False)
                
                # ツリービュー自体の更新を強制実行
                try:
                    self.ui_controls["tree_view"].update()
                    logger.debug("ツリービューの強制更新を実行しました")
                except Exception as update_ex:
                    logger.warning(f"ツリービューの強制更新に失敗: {update_ex}")
                
                # ページ全体の更新
                if self.page:
                    self.page.update()
                
                logger.info(f"ツリービューを更新しました (ルートノード数: {len(self.app_state.get('root_ids', []))})")
            
            except Exception as tree_ex:
                import traceback
                logger.error(f"Error building tree view: {str(tree_ex)}")
                logger.debug(traceback.format_exc())
                tree_view = self.ui_controls.get("tree_view")
                if tree_view:
                    tree_view.controls = [ft.Text(f"{t('error.tree_build_failed')}: {str(tree_ex)}")]
                    tree_view.update()

        except Exception as e:
            import traceback
            logger.error(f"Error updating tree view: {str(e)}")
            logger.debug(traceback.format_exc())
            tree_view = self.ui_controls.get("tree_view")
            if tree_view:
                tree_view.controls = [ft.Text(f"{t('error.tree_display_failed')}: {str(e)}")]
                tree_view.update()
            
            # エラー時もページ全体を更新
            if self.page:
                self.page.update()
                
    def _update_tree_view_optimized(self):
        """TreeOptimizerを使用して最適化されたツリービューの更新を行う"""
        logger.debug("Updating tree view with optimization...")
        
        try:
            # TreeOptimizerのインポート
            
            
            # 既存のオプティマイザーを取得または新規作成
            tree_optimizer = self.app_state.get("tree_optimizer")
            if not tree_optimizer:
                logger.debug("Creating new TreeOptimizer instance")
                tree_optimizer = TreeOptimizer(self.ui_controls, self.app_state)
                self.app_state["tree_optimizer"] = tree_optimizer
                
                # 初期化
                tree_optimizer.initialize(self.app_state["root_ids"], self.app_state["data_map"])
            else:
                # 変更があった場合は強制更新
                tree_optimizer.optimize_tree_update(force_update=True)
            
            # ビューポートの設定（表示可能な要素数を計算）
            # ツリービューの高さと1アイテムの高さから表示可能な数を計算
            tree_view = self.ui_controls.get("tree_view")
            if tree_view and hasattr(tree_view, "height") and tree_view.height is not None:
                viewport_height = tree_view.height
            else:
                viewport_height = 600  # デフォルト値
                
            item_height = 35  # 推定アイテム高さ
            visible_items = max(20, int(viewport_height / item_height))  # 少なくとも20アイテムは表示
            
            # ビューポートの設定
            tree_optimizer.set_viewport(0, visible_items)
            
            # 現在のビューポート内のノードを取得
            viewport_nodes = tree_optimizer.get_viewport_nodes()
            logger.debug(f"ビューポートに表示するノード数: {len(viewport_nodes)}")
            
            # ビューポート内のノードだけを構築
            optimized_tiles = self._build_optimized_list_tiles(viewport_nodes, tree_optimizer)
            
            # ツリービューを更新
            tree_view = self.ui_controls.get("tree_view")
            if tree_view:
                tree_view.controls.clear()
                for tile in optimized_tiles:
                    tree_view.controls.append(tile)
                
                tree_view.visible = True
                tree_view.height = None
                tree_view.expand = True
                tree_view.update()
            
            # スクロール検出のためのイベントリスナーを設定（将来的な拡張）
            # 現在のFletフレームワークではスクロールイベントを直接検出できないため、
            # 将来的な機能として追加予定
            
            logger.info(f"ツリービューを最適化更新しました（表示ノード数: {len(viewport_nodes)}）")
            return True
            
        except Exception as e:
            import traceback
            logger.error(f"Error in optimized tree view update: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
            
    def _build_optimized_list_tiles(self, node_ids, tree_optimizer):
        """最適化された方法でリストタイルを構築する
        
        Args:
            node_ids: 表示するノードIDのリスト
            tree_optimizer: TreeOptimizerインスタンス
            
        Returns:
            構築されたコントロールのリスト
        """
        tiles = []
        
        # イベントハンドラ関数を作成する関数
        def create_on_accept_handler(node_id):
            def handler(e):
                if not self.app_state["tree_drag_locked"]:
                    self.on_node_drop(e)
            return handler
        
        def create_on_will_accept_handler(node_id, is_node=False):
            def handler(e):
                if not self.app_state["tree_drag_locked"]:
                    self.on_drag_hover(e, True, is_node=is_node)
            return handler
        
        def create_on_leave_handler(node_id, is_node=False):
            def handler(e):
                self.on_drag_hover(e, False, is_node=is_node)
            return handler
            
        for node_id in node_ids:
            # ノードの深さを取得
            depth = tree_optimizer.node_depths.get(node_id, 0)
            
            sibling_drop_target = ft.DragTarget(
                group="tree_nodes",
                content=ft.Container(bgcolor=None, height=5, width=float("inf")),
                data={"target_type": "sibling", "before_id": node_id},
                on_accept=create_on_accept_handler(node_id),
                on_will_accept=create_on_will_accept_handler(node_id),
                on_leave=create_on_leave_handler(node_id),
            )

            node_data = self.app_state["data_map"].get(node_id)
            if node_data is None or not isinstance(node_data, dict):
                continue

            # ノードラベルの取得
            label = self.get_node_display_label(node_id, node_data)

            # 子ノードの有無
            children_ids = self.app_state["children_map"].get(node_id, [])
            has_children = bool(children_ids)

            # 表示用ラベルの調整
            display_label = label
            if len(display_label) > 50:
                display_label = display_label[:47] + "..."

            # アイコンの設定 - 展開/折りたたみ状態に基づく
            icon = Icons.FOLDER if has_children and not tree_optimizer.is_node_expanded(node_id) else \
                  Icons.FOLDER_OPEN if has_children else Icons.ARTICLE_OUTLINED

            # リストタイルを構築
            list_tile = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(width=depth * 20),  # インデント
                        ft.IconButton(
                            icon=icon,
                            icon_size=16,
                            icon_color=ft.Colors.PRIMARY if has_children else ft.Colors.ON_SURFACE_VARIANT,
                            visible=has_children,  # 子ノードがある場合のみ表示
                            on_click=lambda e, node_id=node_id: self._toggle_node_expansion(e, node_id, tree_optimizer),
                            style=ft.ButtonStyle(padding=ft.padding.all(0)),  # パディングを小さくして密度を上げる
                            tooltip="展開/折りたたむ"
                        ) if has_children else ft.Icon(
                            icon,
                            size=16,
                            color=ft.Colors.ON_SURFACE_VARIANT
                        ),
                        ft.Text(
                            display_label,
                            size=14,
                            color=ft.Colors.PRIMARY if self.app_state["selected_node_id"] == node_id else None,
                            weight=ft.FontWeight.BOLD if self.app_state["selected_node_id"] == node_id else None,
                        ),
                    ],
                    spacing=5
                ),
                padding=ft.padding.symmetric(vertical=6, horizontal=10),
                border_radius=5,
                data=node_id,
                on_click=self.on_tree_node_select,
                ink=True,
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY) if self.app_state["selected_node_id"] == node_id else None,
            )

            # ドラッグロック状態に応じてコントロールを追加
            if self.app_state["tree_drag_locked"]:
                tiles.append(sibling_drop_target)
                tiles.append(list_tile)
            else:
                # ドラッグ可能な状態の場合
                node_drop_target = ft.DragTarget(
                    group="tree_nodes",
                    content=list_tile,
                    data={"target_type": "parent", "parent_id": node_id},
                    on_accept=create_on_accept_handler(node_id),
                    on_will_accept=create_on_will_accept_handler(node_id, is_node=True),
                    on_leave=create_on_leave_handler(node_id, is_node=True),
                )

                draggable_item = ft.Draggable(
                    group="tree_nodes",
                    content=node_drop_target,
                    data=node_id,
                    disabled=self.app_state["tree_drag_locked"],
                    visible=True
                )
                tiles.append(sibling_drop_target)
                tiles.append(draggable_item)
        
        # 最後のドロップターゲットを追加
        final_drop_target = ft.DragTarget(
            group="tree_nodes",
            content=ft.Container(bgcolor=None, height=5, width=float("inf")),
            data={"target_type": "sibling", "before_id": None},
            on_accept=create_on_accept_handler(None),
            on_will_accept=create_on_will_accept_handler(None),
            on_leave=create_on_leave_handler(None),
        )
        tiles.append(final_drop_target)
        
        return tiles
        
    def _toggle_node_expansion(self, e, node_id, tree_optimizer):
        """ノードの展開/折りたたみ状態を切り替える
        
        Args:
            e: イベントオブジェクト
            node_id: 対象ノードID
            tree_optimizer: TreeOptimizerインスタンス
        """
        # イベントの伝播を停止
        if hasattr(e, 'control') and hasattr(e.control, 'page'):
            e.control.page.prevent_default()
            
        try:
            # 現在の状態を取得
            is_expanded = tree_optimizer.is_node_expanded(node_id)
            
            # 状態の切り替え
            if is_expanded:
                updated = tree_optimizer.collapse_node(node_id)
            else:
                updated = tree_optimizer.expand_node(node_id)
                
            if updated:
                # 更新が必要な場合は、ツリービューを更新
                self._update_tree_view_optimized()
                
                # イベントの発行（EventHubがある場合）
                event_hub = self.app_state.get("event_hub")
                if event_hub:
                    
                    event_type = EventType.NODE_EXPANDED if not is_expanded else EventType.NODE_COLLAPSED
                    event_hub.publish(
                        event_type,
                        data={"node_id": node_id},
                        source="ui_manager"
                    )
        except Exception as e:
            logger.error(f"Error toggling node expansion: {str(e)}")
            
    def expand_all_nodes(self):
        """すべてのノードを展開する"""
        try:
            # 展開状態を保存するSetが存在するか確認
            if "expanded_nodes" not in self.app_state:
                self.app_state["expanded_nodes"] = set()
                
            # すべてのノードIDを取得
            all_nodes = set(self.app_state.get("data_map", {}).keys())
            
            # すべて展開状態にする
            self.app_state["expanded_nodes"] = all_nodes.copy()
            
            # TreeOptimizerが存在する場合は、そちらも更新
            tree_optimizer = self.app_state.get("tree_optimizer")
            if tree_optimizer:
                for node_id in all_nodes:
                    tree_optimizer.expand_node(node_id)
                    
            # ツリービューを更新
            self.update_tree_view(optimize=True)
            logger.info(f"すべてのノードを展開しました（合計: {len(all_nodes)}ノード）")
        except Exception as e:
            logger.error(f"Error expanding all nodes: {str(e)}")
            
    def collapse_all_nodes(self):
        """すべてのノードを折りたたむ"""
        try:
            # ルートノード以外を折りたたむ
            root_ids = set(self.app_state.get("root_ids", []))
            
            # 展開状態をリセットしてルートノードだけを展開状態にする
            self.app_state["expanded_nodes"] = root_ids.copy()
            
            # TreeOptimizerが存在する場合は、それも更新
            tree_optimizer = self.app_state.get("tree_optimizer")
            if tree_optimizer:
                # 一度すべて折りたたむ
                all_nodes = set(self.app_state.get("data_map", {}).keys())
                for node_id in all_nodes - root_ids:
                    tree_optimizer.collapse_node(node_id)
                    
                # ルートノードは展開状態に
                for node_id in root_ids:
                    tree_optimizer.expand_node(node_id)
                    
            # ツリービューを更新
            self.update_tree_view(optimize=True)
            logger.info(f"ルートノード以外のすべてのノードを折りたたみました（ルートノード数: {len(root_ids)}）")
        except Exception as e:
            logger.error(f"Error collapsing all nodes: {str(e)}")
    
    def ensure_main_content_visible(self):
        """メインコンテンツエリアの表示状態を確認して設定する"""
        # UIStateManagerが利用可能な場合は委譲
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager:
            ui_state_manager.ensure_main_content_visible()
            return
            
        # UIStateManagerがない場合の実装
        
        # まず、app_stateの参照を確認
        if "main_content_area" in self.app_state:
            # Refオブジェクトとして保存されている場合
            main_content = self.app_state["main_content_area"]
            if main_content and hasattr(main_content, 'current'):
                if main_content.current:
                    print(f"[OK] main_content_area.current経由でメインコンテンツを表示設定 (ID: {main_content.current.id})")
                    main_content.current.visible = True
                    if self.page:
                        main_content.current.update()
                    return True
                else:
                    print(f"[WARNING] main_content_area.currentがNoneです")
        
        # pageからの検索を試みる
        if self.page:
            # IDによる検索
            main_content = self.page.get_control("main_content_area")
            if main_content:
                print(f"[OK] ID検索でメインコンテンツを表示設定 (visible: {main_content.visible} -> True)")
                main_content.visible = True
                main_content.update()
                return True
            
            # 全コントロールから検索
            for control in self.page.controls:
                if isinstance(control, ft.Container) and control.id == "main_content_area":
                    print(f"[OK] ページ内検索でメインコンテンツを表示設定 (visible: {control.visible} -> True)")
                    control.visible = True
                    control.update()
                    return True
        
        print("[WARNING] メインコンテンツエリアが見つかりませんでした")
        return False
    
    def clear_detail_form(self):
        """詳細フォームの内容をクリアし、ボタンを非表示にする"""
        # FormManagerがあればそれを使用
        form_manager = self.app_state.get("form_manager")
        if form_manager:
            form_manager.clear_detail_form()
            return
            
        # なければ直接クリア処理を実行
        print("[CLEANUP] Clearing detail form...")
        detail_form_column = self.ui_controls.get("detail_form_column")
        if detail_form_column:
            detail_form_column.controls = [ft.Text(t("ui.select_node"))] # 空のメッセージを表示

            # ボタンを非表示にする
            save_button = self.ui_controls.get("detail_save_button")
            cancel_button = self.ui_controls.get("detail_cancel_button")
            delete_button = self.ui_controls.get("detail_delete_button")

            if save_button:
                save_button.visible = False
                save_button.disabled = True # 念のため無効化
            if cancel_button:
                cancel_button.visible = False
                cancel_button.disabled = True # 念のため無効化
            if delete_button:
                delete_button.visible = False

            detail_form_column.update()
            print("[OK] Detail form cleared and buttons hidden.")
        else:
            print("[WARNING] Detail form column not found, cannot clear.")
    
    def on_file_selected(self, e: FilePickerResultEvent):
        """
        ファイル選択時の処理
        
        Args:
            e: ファイル選択結果イベント
        """
        # DataManagerが利用可能な場合はそちらに委譲
        data_manager = self.app_state.get("data_manager")
        if data_manager and e.files and len(e.files) > 0:
            file_path = e.files[0].path
            data_manager.load_json_file(file_path)
            return
            
        # DataManagerが利用できない場合の内部実装
        if not e.files or len(e.files) == 0:
            print("[ERROR] ファイルが選択されませんでした")
            return

        selected_file = e.files[0]
        file_path = os.path.abspath(selected_file.path)
        
        # ファイルパスを表示
        selected_file_path_text = self.ui_controls.get("selected_file_path_text")
        if selected_file_path_text:
            selected_file_path_text.value = os.path.basename(file_path)
            selected_file_path_text.tooltip = file_path
            selected_file_path_text.update()
        
        # 右ペインの詳細フォームを初期化（ファイル読み込み時に毎回リセット）
        detail_form_column = self.ui_controls.get("detail_form_column")
        if detail_form_column:
            detail_form_column.controls = [ft.Text(t("ui.select_node"), color=ft.Colors.ON_SURFACE_VARIANT)]
            detail_form_column.update()
        
        try:
            # JSONファイルを読み込み
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                
            if not isinstance(raw_data, list):
                raw_data = [raw_data]  # 単一オブジェクトの場合はリストに変換
                
            # 空のデータの場合はエラーメッセージを表示
            if len(raw_data) == 0:
                analysis_summary = self.ui_controls.get("analysis_result_summary_text")
                if analysis_summary:
                    analysis_summary.value = "[ERROR] JSONファイルが空です"
                    analysis_summary.update()
                
                main_content_area = self.app_state.get("main_content_area")
                if main_content_area:
                    main_content_area.visible = False
                    main_content_area.update()
                return
                
            # AnalysisManagerが利用可能ならそちらに解析を委譲、なければ直接解析を行う
            analysis_manager = self.app_state.get("analysis_manager")
            if analysis_manager:
                analysis_results = analysis_manager.analyze_json_structure(data=raw_data)
            else:
                # 直接analyze_json.pyのインポートを試みる
                
                analysis_results = analyze_json_structure(data=raw_data)
                
                # フィールドの役割を推測
                if isinstance(analysis_results, dict) and "field_details" in analysis_results:
                    field_details = analysis_results["field_details"]
                    roles = suggest_field_roles(field_details, raw_data)
                    # 解析結果にsuggested_rolesキーが既にある場合は更新、なければ追加
                    if "suggested_roles" in analysis_results:
                        analysis_results["suggested_roles"].update(roles)
                    else:
                        analysis_results["suggested_roles"] = roles
            
            # ヒューリスティック提案を取得
            heuristic_suggestions = {
                "identifier": analysis_results.get("heuristic_suggestions", {}).get("identifier"),
                "children_link": analysis_results.get("heuristic_suggestions", {}).get("children_link"),
                "depth": analysis_results.get("heuristic_suggestions", {}).get("depth"),
                "label": analysis_results.get("heuristic_suggestions", {}).get("label")
            }
            
            # アプリケーション状態を更新
            self.app_state.update({
                "file_path": file_path,
                "raw_data": raw_data,
                "analysis_results": analysis_results,
                "id_key": heuristic_suggestions.get("identifier"),
                "children_key": heuristic_suggestions.get("children_link"),
                "depth_key": heuristic_suggestions.get("depth"),
                "label_key": heuristic_suggestions.get("label"),
                "selected_node_id": None,
                "edit_buffer": {},
                "is_dirty": False,
                "data_map": {},  # 明示的に初期化
                "children_map": {},  # 明示的に初期化
                "root_ids": []  # 明示的に初期化
            })
            
            
            # データマップとツリー構造の構築（DataManagerに委譲できれば）
            data_manager = self.app_state.get("data_manager")
            if data_manager:
                success = data_manager.build_data_map_and_tree()
            else:
                # data_handlers.pyの関数を直接使用
                from src.data_handlers import build_data_map_and_tree
                success = build_data_map_and_tree()
            
            # 解析結果サマリーの更新
            analysis_summary = self.ui_controls.get("analysis_result_summary_text")
            if analysis_summary:
                if not success:
                    analysis_summary.value = t("error.analysis_structure_failed")
                else:
                    field_count = len(analysis_results.get("field_details", []))
                    analysis_summary.value = (
                        t("analysis.result_summary").format(
                            data_count=len(raw_data),
                            node_count=analysis_results.get('total_nodes', 0),
                            max_depth=analysis_results.get('max_depth', 0),
                            field_count=field_count
                        ) + "\n" +
                        t("analysis.key_info").format(
                            id_key=self.app_state['id_key'],
                            label_key=self.app_state['label_key'],
                            children_key=self.app_state['children_key']
                        )
                    )
                analysis_summary.update()
            
            # 保存ボタンを有効化
            save_button = self.ui_controls.get("save_button")
            if save_button:
                save_button.disabled = False
                save_button.update()
            
            # ツリービューを更新
            if self.app_state.get("data_map") and self.app_state.get("root_ids"):
                self.update_tree_view()
                print(f"[TREE] ツリービューを更新しました（ルートノード数: {len(self.app_state.get('root_ids', []))}）")
            else:
                print("[WARNING] データマップまたはルートIDがないため、ツリービューを更新できません")
                tree_view = self.ui_controls.get("tree_view")
                if tree_view:
                    tree_view.controls = [ft.Text(t("ui.tree_display_error"))]
                    tree_view.update()
            
            # メインコンテンツと検索UIを表示
            self.ensure_main_content_visible()
            
            # 検索UIの表示
            search_ui_container = self.ui_controls.get("search_ui_container")
            if search_ui_container:
                search_ui_container.visible = True
                search_ui_container.update()
            
            # 検索インデックスの構築
            search_manager = self.app_state.get("search_manager")
            if search_manager:
                search_manager.build_search_index()
                
            # ページ全体を更新
            if self.page:
                self.page.update()
                print("[FILE] ページ全体を更新しました")
                
        except json.JSONDecodeError as e:
            analysis_summary = self.ui_controls.get("analysis_result_summary_text")
            if analysis_summary:
                analysis_summary.value = t("error.json_analysis_failed").format(error=str(e))
                analysis_summary.update()
        except Exception as e:
            import traceback
            analysis_summary = self.ui_controls.get("analysis_result_summary_text")
            if analysis_summary:
                analysis_summary.value = t("error.general_error").format(error=str(e))
                analysis_summary.update()
            print(f"エラー: {str(e)}")
            print(traceback.format_exc())
    
    def on_save_file_result(self, e: ft.FilePickerResultEvent):
        """
        ファイル保存ダイアログの結果を処理する
        
        Args:
            e: ファイル選択結果イベント
        """
        # DataManagerに委譲可能かチェック
        data_manager = self.app_state.get("data_manager")
        if data_manager and e.path:
            data_manager.save_json_file(e.path)
            return
            
        # 内部実装（DataManagerが利用できない場合）
        save_path = e.path
        if save_path:
            if self.app_state.get("raw_data") is None:
                if self.page:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(t("error.no_data_to_save")),
                        open=True
                    )
                    self.page.update()
                return

            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(self.app_state["raw_data"], f, ensure_ascii=False, indent=4)
                
                if self.page:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"{t('notification.file_save_success')}: {os.path.basename(save_path)}"),
                        open=True,
                        bgcolor=ft.Colors.GREEN_ACCENT_700
                    )
                    self.page.update()
                print(f"[SAVE] File saved successfully: {save_path}")
            except Exception as ex:
                error_message = f"{t('notification.file_save_error')}: {ex}"
                if self.page:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(error_message),
                        open=True,
                        bgcolor=ft.Colors.RED_ACCENT_700
                    )
                    self.page.update()
                print(f"[ERROR] Error saving file: {ex}")
        else:
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(t("notification.file_save_cancelled")),
                    open=True
                )
                self.page.update()
    
    def trigger_save_as_dialog(self, save_file_picker: ft.FilePicker):
        """
        「名前を付けて保存」ダイアログを表示する
        
        Args:
            save_file_picker: ファイル選択ピッカー
        """
        if self.app_state.get("raw_data") is None:
             if self.page:
                 self.page.snack_bar = ft.SnackBar(
                     content=ft.Text(t("error.no_data_to_save")),
                     open=True
                 )
                 self.page.update()
             return
             
        suggested_filename = os.path.basename(self.app_state.get("file_path", "")) or "data.json"
        save_file_picker.save_file(
            dialog_title=t("dialog.save_as_title"),
            file_name=suggested_filename,
            allowed_extensions=["json"]
        )
    
    def on_lock_change(self, e: ft.ControlEvent):
        """
        ツリービューのドラッグロック状態を変更する
        
        Args:
            e: コントロールイベント
        """
        is_locked = e.control.value
        self.app_state["tree_drag_locked"] = is_locked
        print(f"[LOCK] Lock state changed: {is_locked}")

        # ツリービューを更新
        self.update_tree_view()
        
        # ページ更新
        if self.page:
            self.page.update()

    def update_ui_save_state(self):
        """保存関連UIの状態を更新する"""
        is_dirty = self.app_state.get("is_dirty", False)
        
        # 詳細画面の保存ボタン更新
        if self.ui_controls.get("detail_save_button"):
            try:
                self.ui_controls["detail_save_button"].disabled = not is_dirty
                # ページに追加されている場合のみ更新
                button = self.ui_controls["detail_save_button"]
                if hasattr(button, '_page') and button._page is not None:
                    button.update()
            except Exception as ex:
                # ElevatedButtonのページ追加前エラーは無視
                if "must be added to the page first" not in str(ex):
                    print(f"[WARNING] detail_save_button.update()エラー: {ex}")
        
        # 詳細画面のキャンセルボタン更新
        if self.ui_controls.get("detail_cancel_button"):
            try:
                self.ui_controls["detail_cancel_button"].disabled = not is_dirty
                # ページに追加されている場合のみ更新
                if hasattr(self.ui_controls["detail_cancel_button"], '_page') and self.ui_controls["detail_cancel_button"]._page is not None:
                    self.ui_controls["detail_cancel_button"].update()
            except Exception as ex:
                # ElevatedButtonのページ追加前エラーは無視
                if "must be added to the page first" not in str(ex):
                    print(f"[ERROR] [エラー] detail_cancel_button.update() 失敗: {ex}")
        
        # メイン画面の保存ボタン更新（名前を付けて保存）
        if self.ui_controls.get("save_button"):
            try:
                # ファイルがロードされているときのみ有効化
                file_loaded = self.app_state.get("file_path") is not None
                self.ui_controls["save_button"].disabled = not file_loaded  # ファイル読み込み済みの時に有効
                # ページに追加されている場合のみ更新
                if hasattr(self.ui_controls["save_button"], 'page') and self.ui_controls["save_button"].page:
                    self.ui_controls["save_button"].update()
            except Exception as ex:
                # ElevatedButtonのページ追加前エラーは無視
                if "must be added to the page first" not in str(ex):
                    print(f"[ERROR] [エラー] save_button.update() 失敗: {ex}")

    def save_file_directly(self, file_path: str):
        """ファイルを直接保存する"""
        try:
            # edit_bufferの内容を適用
            form_manager = self.app_state.get("form_manager")
            if form_manager and self.app_state.get("edit_buffer"):
                success, errors = form_manager.apply_edit_buffer_to_data()
                if not success:
                    logger.error(f"Failed to apply edit buffer: {errors}")
                    if self.page:
                        error_msg = errors.get("general", "編集内容の適用に失敗しました")
                        # 代替通知システムを使用
                        try:
                            from notification_system import NotificationSystem
                            notification_system = NotificationSystem(self.page)
                            notification_system.show_error(error_msg)
                        except Exception as e:
                            # フォールバック: 従来のSnackBar
                            self.page.snack_bar = ft.SnackBar(
                                content=ft.Text(error_msg),
                                open=True,
                                duration=3000,
                                bgcolor=ft.Colors.RED
                            )
                            self.page.update()
                    return False
                elif errors:
                    logger.warning(f"Edit buffer applied with warnings: {errors}")
            
            data_manager = self.app_state.get("data_manager")
            if data_manager:
                success = data_manager.save_json_file(file_path)
                if success:
                    self.app_state["is_dirty"] = False
                    self.update_ui_save_state()
                    print(f"[OK] ファイルが保存されました: {file_path}")
                    if self.page:
                        # 代替通知システムを使用
                        try:
                            from notification_system import NotificationSystem
                            notification_system = NotificationSystem(self.page)
                            notification_system.show_save_success(os.path.basename(file_path))
                        except Exception as e:
                            # フォールバック: 従来のSnackBar
                            print(f"代替通知システムエラー: {e}")
                            try:
                                self.page.snack_bar = ft.SnackBar(
                                    content=ft.Text(f"[OK] {t('notification.file_save_success')}: {os.path.basename(file_path)}"),
                                    open=True,
                                    duration=3000,
                                    bgcolor=ft.Colors.GREEN_700
                                )
                                self.page.update()
                                print("[OK] フォールバック：従来スナックバーを表示")
                            except:
                                print("[WARNING] 全ての通知方法が失敗しました")
                    return True
                else:
                    logger.error(f"ファイル保存に失敗しました: {file_path}")
                    if self.page:
                        # 代替通知システムを使用
                        try:
                            from notification_system import NotificationSystem
                            notification_system = NotificationSystem(self.page)
                            notification_system.show_save_error(t("notification.file_save_failed_detail").format(filename=os.path.basename(file_path)))
                        except Exception as e:
                            # フォールバック: 従来のSnackBar
                            print(f"代替通知システムエラー: {e}")
                            try:
                                self.page.snack_bar = ft.SnackBar(
                                    content=ft.Text(f"{t('error.save_failed')}: {os.path.basename(file_path)}"),
                                    open=True,
                                    duration=3000,
                                    bgcolor=ft.Colors.RED
                                )
                                self.page.update()
                                print("[OK] フォールバック：従来スナックバーを表示")
                            except:
                                print("[WARNING] 全ての通知方法が失敗しました")
                    return False
            else:
                logger.error("DataManager not available for save")
                return False
        except Exception as e:
            logger.error(f"保存中にエラーが発生しました: {e}")
            return False

    def handle_data_change(self, changed=True):
        """データ変更状態を処理する"""
        self.app_state["is_dirty"] = changed
        self.update_ui_save_state()
        if changed:
            pass  # 変更があった場合の処理（既にis_dirtyを設定済み）
        else:
            logger.info("データが保存されました（変更なし）")

    def close_all_dialogs(self):
        """すべてのダイアログを閉じる（オーバーレイ方式では使用されない）"""
        # オーバーレイ方式では、page.controlsから直接削除するため、この方法は使用しない
        logger.debug("オーバーレイ方式ではclose_all_dialogsは使用されません")
        return True

    def perform_save_operation(self, file_path=None, save_as=False, force_confirm=False):
        """保存操作を実行する"""
        try:
            current_file_path = self.app_state.get("file_path")
            
            if save_as or not current_file_path:
                # Save Asまたは新規ファイルの場合
                if not file_path:
                    logger.error("Save As操作にファイルパスが必要です")
                    return False
                target_path = file_path
            else:
                # 既存ファイルの上書き
                target_path = current_file_path
            
            # 保存実行
            success = self.save_file_directly(target_path)
            if success:
                self.app_state["file_path"] = target_path
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"保存操作エラー: {e}")
            return False

    def show_save_confirmation(self, file_path: str) -> bool:
        """
        保存確認ダイアログを表示する（過去の実装に基づくオーバーレイ方式）
        
        Args:
            file_path (str): 保存対象のファイルパス
            
        Returns:
            bool: ダイアログ表示の成功可否
        """
        if not self.page:
            logger.error("Page object not available")
            return False
            
        try:
            def on_cancel_click(e):
                """キャンセルボタンクリック時の処理"""
                logger.debug("キャンセルボタンがクリックされました - オーバーレイを削除します")
                # オーバーレイコンテナを削除
                overlay_container = None
                for control in self.page.controls[:]:  # コピーを作成して反復
                    if hasattr(control, 'data') and control.data == "save_confirm_overlay":
                        overlay_container = control
                        break
                
                if overlay_container:
                    self.page.controls.remove(overlay_container)
                    self.page.update()
                    logger.debug("オーバーレイコンテナを削除しました")
                
                self.app_state["confirmation_dialog_showing"] = False
                logger.info("保存がキャンセルされました")
            
            def on_save_click(e):
                """保存ボタンクリック時の処理"""
                logger.debug("保存ボタンがクリックされました - オーバーレイを削除して保存処理を開始")
                # オーバーレイコンテナを削除
                overlay_container = None
                for control in self.page.controls[:]:  # コピーを作成して反復
                    if hasattr(control, 'data') and control.data == "save_confirm_overlay":
                        overlay_container = control
                        break
                
                if overlay_container:
                    self.page.controls.remove(overlay_container)
                    self.page.update()
                    logger.debug("オーバーレイコンテナを削除しました")
                
                self._handle_save_confirmation(file_path)
            
            # 既存のオーバーレイコンテナを削除
            for control in self.page.controls[:]:  # コピーを作成して反復
                if hasattr(control, 'data') and control.data == "save_confirm_overlay":
                    self.page.controls.remove(control)
            
            # オーバーレイコンテナを作成（画面全体を覆う）
            overlay_container = ft.Container(
                data="save_confirm_overlay",
                width=self.page.width if self.page.width else 1200,
                height=self.page.height if self.page.height else 800,
                bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.BLACK),  # 半透明の黒背景
                content=ft.Column([
                    ft.Container(height=200),  # 上部の余白
                    ft.Row([
                        ft.Container(expand=True),  # 左の余白
                        ft.Container(
                            bgcolor=ft.Colors.with_opacity(0.98, ft.Colors.SURFACE),
                            border_radius=10,
                            padding=20,
                            width=500,
                            border=ft.border.all(2, ft.Colors.RED_500),
                            shadow=ft.BoxShadow(
                                spread_radius=1,
                                blur_radius=15,
                                color=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
                                offset=ft.Offset(2, 2)
                            ),
                            content=ft.Column([
                                ft.Row([
                                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.RED, size=24),
                                    ft.Text(t("dialog.confirm_save"), color=ft.Colors.RED_700, size=20, weight=ft.FontWeight.BOLD),
                                ]),
                                ft.Divider(color=ft.Colors.RED_200, height=1),
                                ft.Container(height=15),
                                ft.Text(
                                    t("dialog.save_question").format(filename=os.path.basename(file_path)),
                                    size=16,
                                ),
                                ft.Text(
                                    "ノードを削除した後のデータを保存しようとしています。",
                                    size=14,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        "[WARNING] 注意: この操作は元に戻せません", 
                                        color=ft.Colors.RED,
                                        weight=ft.FontWeight.BOLD,
                                        size=14
                                    ),
                                    margin=ft.margin.only(top=10)
                                ),
                                ft.Container(height=30),
                                ft.Row([
                                    ft.ElevatedButton(
                                        "キャンセル",
                                        color=ft.Colors.BLACK,
                                        bgcolor=ft.Colors.WHITE,
                                        on_click=on_cancel_click,
                                        height=40,
                                        width=140,
                                    ),
                                    ft.Container(width=20),
                                    ft.ElevatedButton(
                                        "保存する",
                                        color=ft.Colors.WHITE,
                                        bgcolor=ft.Colors.RED_600,
                                        on_click=on_save_click,
                                        height=40,
                                        width=140,
                                    ),
                                ], alignment=ft.MainAxisAlignment.END)
                            ])
                        ),
                        ft.Container(expand=True),  # 右の余白
                    ], alignment=ft.MainAxisAlignment.CENTER),
                ], alignment=ft.MainAxisAlignment.START)
            )
            
            # ページの最上部に追加
            self.page.controls.append(overlay_container)
            self.page.update()
            
            self.app_state["confirmation_dialog_showing"] = True
            logger.debug("オーバーレイ方式で保存確認ダイアログを表示しました")
            return True
            
        except Exception as e:
            logger.error(f"保存確認ダイアログエラー: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def _handle_save_confirmation(self, file_path: str):
        """保存確認後の処理"""
        # ダイアログは既にボタンクリック時に閉じられているので、フラグのみ設定
        self.app_state["confirmation_dialog_showing"] = False
        
        # edit_bufferの内容を適用
        form_manager = self.app_state.get("form_manager")
        if form_manager and self.app_state.get("edit_buffer"):
            success, errors = form_manager.apply_edit_buffer_to_data()
            if not success:
                logger.error(f"Failed to apply edit buffer: {errors}")
                if self.page:
                    error_msg = errors.get("general", "編集内容の適用に失敗しました")
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(error_msg),
                        open=True,
                        duration=3000,
                        bgcolor=ft.Colors.RED
                    )
                    self.page.update()
                return
            elif errors:
                logger.warning(f"Edit buffer applied with warnings: {errors}")
        
        # DataManagerを使用して保存を実行
        data_manager = self.app_state.get("data_manager")
        if data_manager:
            success = data_manager.save_json_file(file_path)
            if success:
                self.app_state["is_dirty"] = False
                self.app_state["node_deleted_since_last_save"] = False
                self.update_ui_save_state()
                
                # ツリービューを更新
                try:
                    self.update_tree_view()
                    logger.debug("確認ダイアログ保存後のツリービュー更新完了")
                except Exception as tree_ex:
                    logger.warning(f"ツリービュー更新エラー: {tree_ex}")
                
                # 代替通知システムで成功を通知（一貫性のため）
                if self.page:
                    try:
                        from notification_system import NotificationSystem
                        notification_system = NotificationSystem(self.page)
                        notification_system.show_save_success(os.path.basename(file_path))
                    except Exception as e:
                        # フォールバック: 従来のSnackBar
                        print(f"代替通知システムエラー: {e}")
                        try:
                            self.page.snack_bar = ft.SnackBar(
                                content=ft.Text(f"{t('notification.file_save_success')}: {os.path.basename(file_path)}"),
                                open=True,
                                bgcolor=ft.Colors.GREEN_700,
                                duration=3000
                            )
                            self.page.update()
                            print("[OK] フォールバック：従来スナックバーを表示")
                        except:
                            print("[WARNING] 全ての通知方法が失敗しました")
                logger.info(f"ファイル保存完了: {file_path}")
            else:
                logger.error(f"ファイル保存失敗: {file_path}")

    def initialize(self):
        """UI初期化処理"""
        logger.debug("UIManager initializing...")
        # 既存の初期化ロジックがあればここに実装
        return True
    
    def set_theme_change_callback(self, callback: Callable[[str], None]):
        """テーマ変更時のコールバックを設定
        
        Args:
            callback: テーマ変更時に呼び出される関数（テーマ名を引数に取る）
        """
        self._theme_change_callback = callback
    
    def create_theme_button(self) -> ft.PopupMenuButton:
        """テーマ切り替えボタンを作成して返す
        
        Returns:
            ft.PopupMenuButton: テーマ切り替えポップアップメニューボタン
        """
        def handle_theme_change(theme_mode: str):
            """テーマ変更ハンドラ"""
            if self._theme_change_callback:
                self._theme_change_callback(theme_mode)
        
        theme_menu_items = [
            ft.PopupMenuItem(
                text="システムテーマ",
                icon=Icons.COMPUTER,
                on_click=lambda _: handle_theme_change("system")
            ),
            ft.PopupMenuItem(
                text="ライトテーマ",
                icon=Icons.LIGHT_MODE,
                on_click=lambda _: handle_theme_change("light")
            ),
            ft.PopupMenuItem(
                text="ダークテーマ",
                icon=Icons.DARK_MODE,
                on_click=lambda _: handle_theme_change("dark")
            ),
        ]
        
        # IconButtonをcontentとして使用する方法を試す
        button = ft.PopupMenuButton(
            content=ft.IconButton(
                icon=Icons.PALETTE,
                tooltip="テーマ切り替え",
            ),
            items=theme_menu_items
        )
        
        return button


def create_ui_manager(app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None) -> UIManager:
    """UIManagerのインスタンスを作成する工場関数"""
    ui_manager = UIManager(app_state, ui_controls, page)
    app_state["ui_manager"] = ui_manager
    return ui_manager