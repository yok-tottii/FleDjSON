"""
ui_state_manager.py
UI状態管理専用のマネージャークラス

FleDjSONのアプリケーション全体のUI状態を管理する
複数のUIコンポーネント間の状態を一元管理し、状態の一貫性を保証する
"""
import flet as ft
from flet import Colors, Draggable, DragTarget, Icons, ControlEvent, Page, Ref, FilePickerResultEvent
from typing import Optional, Dict, List, Any, Union, Tuple, Callable
import json
import os
from collections import defaultdict
from translation import t


class UIStateManager:
    """
    UI状態を一元管理するクラス
    
    アプリケーション全体のUI状態を一箇所で管理し、状態の整合性を保証する
    各UIコンポーネントの表示/非表示、有効/無効状態、選択状態などを管理
    
    Attributes:
        app_state (Dict): アプリケーションの状態を保持する辞書
        ui_controls (Dict): UIコントロールを保持する辞書
        page (ft.Page): Fletページオブジェクト
        app (Any): アプリケーションのメインインスタンス
    """
    
    def __init__(self, app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: ft.Page, app_instance=None):
        """
        UIStateManagerを初期化します。

        Args:
            app_state (Dict): アプリケーションの状態を保持する辞書
            ui_controls (Dict): UIコントロールを保持する辞書
            page (ft.Page): Fletページオブジェクト
            app_instance: FlexiJSONEditorAppのインスタンス（オプション）
        """
        self.app_state = app_state
        self.ui_controls = ui_controls
        self.page = page or app_state.get("page")
        self.app = app_instance  # FlexiJSONEditorAppインスタンスへの参照
        
        # UI状態フラグ
        self._ui_state = {
            "is_loading": False,               # データロード中フラグ
            "is_tree_view_dirty": False,       # ツリービュー更新必要フラグ
            "is_detail_form_dirty": False,     # 詳細フォーム更新必要フラグ
            "is_search_mode": False,           # 検索モードフラグ
            "is_add_mode": False,              # 追加モードフラグ
            "is_edit_mode": False,             # 編集モードフラグ
            "is_delete_confirm_mode": False,   # 削除確認モードフラグ
            "current_view": "tree",            # 現在のビュー（tree/detail/add）
            "form_type": None,                 # 現在のフォームタイプ
            "selected_node_id": None,          # 選択されたノードID
            "control_states": {},              # コントロールの状態を保持する辞書
        }
        
        # 状態変更コールバック
        self._callbacks = defaultdict(list)
        
        # 初期化時にapp_stateから状態を同期
        self._sync_from_app_state()
        
        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] UIStateManager initialized.")
    
    def _safe_update_control(self, control, control_name: str = "control"):
        """コントロールを安全に更新する（ページ追加チェック付き）"""
        try:
            if hasattr(control, '_page') and control._page is not None:
                control.update()
        except Exception as e:
            if "must be added to the page first" not in str(e):
                print(f"[WARNING] {control_name}.update()エラー: {e}")
    
    def _sync_from_app_state(self):
        """app_stateの状態をUIStateManagerに同期"""
        self._ui_state["is_add_mode"] = self.app_state.get("add_mode", False)
        self._ui_state["is_edit_mode"] = self.app_state.get("is_dirty", False)
        self._ui_state["is_delete_confirm_mode"] = self.app_state.get("delete_confirm_mode", False)
        self._ui_state["is_tree_view_dirty"] = self.app_state.get("tree_view_dirty", False)
        self._ui_state["is_detail_form_dirty"] = self.app_state.get("detail_form_dirty", False)
        self._ui_state["is_loading"] = self.app_state.get("is_loading", False)
        self._ui_state["selected_node_id"] = self.app_state.get("selected_node_id")

        # 現在のビューの推定
        if self.app_state.get("add_mode", False):
            self._ui_state["current_view"] = "add"
        elif self.app_state.get("selected_node_id") is not None:
            self._ui_state["current_view"] = "detail"
        else:
            self._ui_state["current_view"] = "tree"

    def _sync_to_app_state(self):
        """UIStateManagerの状態をapp_stateに同期（双方向の整合性を保つ）"""
        self.app_state["add_mode"] = self._ui_state["is_add_mode"]
        self.app_state["is_dirty"] = self._ui_state["is_edit_mode"]
        self.app_state["delete_confirm_mode"] = self._ui_state["is_delete_confirm_mode"]
        self.app_state["tree_view_dirty"] = self._ui_state["is_tree_view_dirty"]
        self.app_state["detail_form_dirty"] = self._ui_state["is_detail_form_dirty"]
        self.app_state["is_loading"] = self._ui_state["is_loading"]

        # ノード選択状態が変更された場合のみ更新
        if self._ui_state["selected_node_id"] != self.app_state.get("selected_node_id"):
            self.app_state["selected_node_id"] = self._ui_state["selected_node_id"]
    
    # ----- 状態取得メソッド -----
    
    def get_state(self, key: str) -> Any:
        """UI状態を取得"""
        return self._ui_state.get(key)
    
    def is_loading(self) -> bool:
        """ロード中かどうかを返す"""
        return self._ui_state["is_loading"]
    
    def is_tree_view_dirty(self) -> bool:
        """ツリービューの更新が必要かどうかを返す"""
        return self._ui_state["is_tree_view_dirty"]
    
    def is_detail_form_dirty(self) -> bool:
        """詳細フォームの更新が必要かどうかを返す"""
        return self._ui_state["is_detail_form_dirty"]
    
    def is_search_mode(self) -> bool:
        """検索モードかどうかを返す"""
        return self._ui_state["is_search_mode"]
    
    def is_add_mode(self) -> bool:
        """追加モードかどうかを返す"""
        return self._ui_state["is_add_mode"]
    
    def is_edit_mode(self) -> bool:
        """編集モードかどうかを返す"""
        return self._ui_state["is_edit_mode"]
    
    def is_delete_confirm_mode(self) -> bool:
        """削除確認モードかどうかを返す"""
        return self._ui_state["is_delete_confirm_mode"]
    
    def get_current_view(self) -> str:
        """現在のビューを返す（tree/detail/add）"""
        return self._ui_state["current_view"]
    
    def get_form_type(self) -> Optional[str]:
        """現在のフォームタイプを返す"""
        return self._ui_state["form_type"]
    
    def get_selected_node_id(self) -> Optional[str]:
        """選択されたノードIDを返す"""
        return self._ui_state["selected_node_id"]
    
    def get_control_state(self, control_name: str) -> Dict[str, Any]:
        """特定のコントロールの状態を取得"""
        return self._ui_state["control_states"].get(control_name, {})
    
    # ----- 状態設定メソッド -----
    
    def set_state(self, key: str, value: Any):
        """
        UI状態を更新し、登録されたコールバックを呼び出す
        
        Args:
            key: 更新する状態のキー
            value: 設定する値
        """
        if key in self._ui_state and self._ui_state[key] != value:
            old_value = self._ui_state[key]
            self._ui_state[key] = value
            
            # 状態変更通知
            self._notify_state_change(key, old_value, value)
            
            # app_stateとの同期
            if key in ["is_add_mode", "is_edit_mode", "is_delete_confirm_mode", "selected_node_id", 
                      "is_tree_view_dirty", "is_detail_form_dirty", "is_loading"]:
                self._sync_to_app_state()
    
    def set_loading(self, is_loading: bool):
        """ロード中状態を設定"""
        self.set_state("is_loading", is_loading)
        
        # ローディングインジケータの表示制御
        if "loading_indicator" in self.ui_controls:
            self.ui_controls["loading_indicator"].visible = is_loading
            if self.page:
                self.page.update()
    
    def set_tree_view_dirty(self, is_dirty: bool):
        """ツリービューの更新必要フラグを設定"""
        self.set_state("is_tree_view_dirty", is_dirty)
    
    def set_detail_form_dirty(self, is_dirty: bool):
        """詳細フォームの更新必要フラグを設定"""
        self.set_state("is_detail_form_dirty", is_dirty)
    
    def set_search_mode(self, is_search_mode: bool):
        """検索モードを設定"""
        self.set_state("is_search_mode", is_search_mode)
        
        # 検索UIの表示制御
        if "search_ui_container" in self.ui_controls:
            self.ui_controls["search_ui_container"].visible = is_search_mode
            if self.page:
                self.page.update()
    
    def set_add_mode(self, is_add_mode: bool) -> bool:
        """
        追加モードを設定
        
        Args:
            is_add_mode: 追加モードを有効にする場合はTrue
            
        Returns:
            bool: 設定が成功した場合はTrue
        """
        print(f"[UPDATE] UIStateManager: 追加モードを{'開始' if is_add_mode else '終了'}")

        # ドラッグ移動モードが有効な場合、追加モードに入れない
        if is_add_mode and not self.app_state.get("tree_drag_locked", True):
            print("[LOCK] UIStateManager: 移動モード中は追加モードを使用できません")
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(t("ui.move_mode_add_disabled")),
                    action="OK"
                )
                self.page.snack_bar.open = True
                self.page.update()
            return False

        # 現在の状態と同じなら何もしない
        if self._ui_state["is_add_mode"] == is_add_mode:
            return True

        # 状態を更新
        self.set_state("is_add_mode", is_add_mode)
        self.app_state["add_mode"] = is_add_mode

        if is_add_mode:
            # 追加モード開始時の処理

            # 選択状態を解除
            self.deselect_node()

            # 必要なフィールドを初期化
            if "edit_buffer" not in self.app_state:
                self.app_state["edit_buffer"] = {}
            self.app_state["edit_buffer"].clear()

            if "removed_fields" not in self.app_state:
                self.app_state["removed_fields"] = set()
            self.app_state["removed_fields"].clear()

            # 追加モード用のビューに設定
            self.set_current_view("add")

            # 新規追加ボタンの状態更新
            if "add_data_button" in self.ui_controls:
                btn = self.ui_controls["add_data_button"]
                btn.text = "追加モード中"
                btn.icon = Icons.CANCEL
                btn.tooltip = "追加モードを終了"
                self._safe_update_control(btn, "add_data_button")

            # フォームマネージャーを使って追加フォームを表示
            form_manager = self.app_state.get('form_manager')
            if form_manager:
                form_manager.update_add_form()
        else:
            # 追加モード終了時の処理

            # 編集バッファをクリア
            if "edit_buffer" in self.app_state:
                self.app_state["edit_buffer"].clear()

            # ビューを更新
            self.set_current_view("tree")

            # 新規追加ボタンを元に戻す
            if "add_data_button" in self.ui_controls:
                btn = self.ui_controls["add_data_button"]
                btn.text = "新規追加"
                btn.icon = Icons.ADD
                btn.tooltip = "新しいデータを追加"
                self._safe_update_control(btn, "add_data_button")

            # フォームをクリア
            form_manager = self.app_state.get('form_manager')
            if form_manager:
                form_manager.clear_detail_form()

        # UI更新
        self.refresh_ui()

        print(f"[OK] UIStateManager: 追加モード{'開始' if is_add_mode else '終了'}完了")
        return True
    
    def set_edit_mode(self, is_edit_mode: bool):
        """編集モードを設定"""
        self.set_state("is_edit_mode", is_edit_mode)
        
        # 保存・キャンセルボタンの状態更新
        if "detail_save_button" in self.ui_controls and self.ui_controls["detail_save_button"]:
            button = self.ui_controls["detail_save_button"]
            button.disabled = not is_edit_mode
            self._safe_update_control(button, "detail_save_button")
            
        if "detail_cancel_button" in self.ui_controls and self.ui_controls["detail_cancel_button"]:
            button = self.ui_controls["detail_cancel_button"]
            button.disabled = not is_edit_mode
            self._safe_update_control(button, "detail_cancel_button")
    
    def set_delete_confirm_mode(self, is_confirm_mode: bool):
        """削除確認モードを設定"""
        self.set_state("is_delete_confirm_mode", is_confirm_mode)
        
        # 詳細フォームの更新が必要
        if is_confirm_mode and self.ui_controls.get("detail_form_column"):
            # 削除確認用UIを表示するために詳細フォームを更新
            fm = self.app_state.get('form_manager')
            if fm:
                fm.update_detail_form(self.app_state.get("selected_node_id"))
    
    def set_current_view(self, view: str):
        """現在のビューを設定（tree/detail/add）"""
        if view in ["tree", "detail", "add"]:
            self.set_state("current_view", view)
    
    def set_form_type(self, form_type: Optional[str]):
        """現在のフォームタイプを設定"""
        self.set_state("form_type", form_type)
    
    def set_control_state(self, control_name: str, state: Dict[str, Any]):
        """特定のコントロールの状態を設定"""
        control_states = self._ui_state["control_states"].copy()
        control_states[control_name] = state
        self.set_state("control_states", control_states)
        
    def update_control_visibility(self, control_name: str, is_visible: bool):
        """コントロールの表示/非表示を設定"""
        if control_name in self.ui_controls and self.ui_controls[control_name]:
            control = self.ui_controls[control_name]
            control.visible = is_visible
            self._safe_update_control(control, control_name)
    
    def update_control_enabled_state(self, control_name: str, is_enabled: bool):
        """コントロールの有効/無効を設定"""
        if control_name in self.ui_controls and self.ui_controls[control_name]:
            control = self.ui_controls[control_name]
            if hasattr(control, "disabled"):
                control.disabled = not is_enabled
                self._safe_update_control(control, control_name)
    
    def reset_ui_state(self):
        """UI状態を初期状態にリセット"""
        self._ui_state.update({
            "is_loading": False,
            "is_tree_view_dirty": False,
            "is_detail_form_dirty": False,
            "is_search_mode": False,
            "is_add_mode": False,
            "is_edit_mode": False,
            "is_delete_confirm_mode": False,
            "current_view": "tree",
            "form_type": None,
            "selected_node_id": None,
        })
        self._sync_to_app_state()
        
    # ----- 状態変更通知のコールバック管理 -----
    
    def register_callback(self, state_key: str, callback: Callable[[str, Any, Any], None]):
        """
        状態変更時に呼び出されるコールバックを登録
        
        Args:
            state_key: 監視する状態のキー
            callback: 状態変更時に呼び出されるコールバック関数
                     (key, old_value, new_value) を引数にとる
        """
        self._callbacks[state_key].append(callback)
        
    def unregister_callback(self, state_key: str, callback: Callable):
        """登録されたコールバックを削除"""
        if state_key in self._callbacks and callback in self._callbacks[state_key]:
            self._callbacks[state_key].remove(callback)
    
    def _notify_state_change(self, key: str, old_value: Any, new_value: Any):
        """状態変更時に登録されたコールバックを呼び出す"""
        # キーに対応するコールバックを呼び出し
        for callback in self._callbacks.get(key, []):
            try:
                callback(key, old_value, new_value)
            except Exception as ex:
                print(f"[ERROR] Error in state change callback for {key}: {ex}")
        
        # 全状態変更監視用コールバックも呼び出し
        for callback in self._callbacks.get("*", []):
            try:
                callback(key, old_value, new_value)
            except Exception as ex:
                print(f"[ERROR] Error in global state change callback: {ex}")
    
    # ----- UI状態に応じたメインウィンドウの制御 -----
    
    def ensure_main_content_visible(self):
        """メインコンテンツエリアの表示状態を確認して設定する"""
        # まず、app_stateの参照を確認
        if "main_content_area" in self.app_state:
            # Refオブジェクトとして保存されている場合
            main_content = self.app_state["main_content_area"]
            if main_content and hasattr(main_content, 'current'):
                if main_content.current:
                    print("[OK] main_content_area.current経由でメインコンテンツを表示設定")
                    main_content.current.visible = True
                    if self.page:
                        self._safe_update_control(main_content.current, "main_content_area.current")
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
                self._safe_update_control(main_content, "main_content")
                return True
            
            # 全コントロールから検索
            for control in self.page.controls:
                if isinstance(control, ft.Container) and hasattr(control, 'id') and control.id == "main_content_area":
                    print(f"[OK] ページ内検索でメインコンテンツを表示設定 (visible: {control.visible} -> True)")
                    control.visible = True
                    self._safe_update_control(control, "main_content_control")
                    return True
        
        print("[WARNING] メインコンテンツエリアが見つかりませんでした")
        return False
    
    # ----- ノード選択状態とハイライト制御 -----
    
    def select_node(self, node_id: str, bypass_lock: bool = False):
        """
        ノードを選択してUIを更新

        Args:
            node_id: 選択するノードのID
            bypass_lock: Trueの場合、移動モードのロックをバイパスする(検索からのジャンプ用)
        """
        print(f"[USER] UIStateManager: ノード選択 - {node_id}")

        # 移動モードでの選択を防止(bypass_lockがTrueの場合はスキップ)
        if not bypass_lock and not self.app_state.get("tree_drag_locked", True):
            print("[LOCK] UIStateManager: 移動モード中は編集できません")
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(t("ui.move_mode_warning")),
                    action="OK"
                )
                self.page.snack_bar.open = True
                self.page.update()
            return

        # 同じノードが再度選択された場合は何もしない
        if self.app_state.get("selected_node_id") == node_id:
            print("[USER] UIStateManager: 同じノードが選択されたため処理をスキップ")
            return

        # 追加モードの場合はキャンセル
        if self.is_add_mode():
            print("[UPDATE] UIStateManager: 追加モードを終了してノード選択に切り替え")
            self.set_add_mode(False)
            # 追加モード関連の状態をクリア
            if "removed_fields" in self.app_state:
                self.app_state["removed_fields"].clear()
            # 編集バッファをクリア
            self.app_state["edit_buffer"].clear()

        # 編集中の変更があれば破棄
        if self.is_edit_mode():
            print("[WARNING] UIStateManager: 未保存の変更を破棄")
            # 変更を破棄
            self.app_state["edit_buffer"].clear()
            self.set_edit_mode(False)

        # 選択状態を更新
        old_selected_id = self.app_state.get("selected_node_id")
        self.app_state["selected_node_id"] = node_id
        self._ui_state["selected_node_id"] = node_id

        # UIマネージャーのインスタンスを取得
        ui_manager = self.app_state.get('ui_manager')
        if ui_manager:
            # 古い選択項目のハイライト解除
            if old_selected_id:
                ui_manager.update_node_style_recursive(
                    self.ui_controls["tree_view"].controls,
                    old_selected_id,
                    False
                )

            # 新しい選択項目のハイライト設定
            if node_id:
                ui_manager.update_node_style_recursive(
                    self.ui_controls["tree_view"].controls,
                    node_id,
                    True
                )

        # 詳細フォームの更新が必要なことを示すフラグ
        self.set_detail_form_dirty(True)

        # 現在のビューを更新
        if node_id:
            self.set_current_view("detail")

        # UIを更新（フォームの更新などが実行される）
        self.refresh_ui()

        print(f"[OK] UIStateManager: ノード選択完了 - {node_id}")
    
    def deselect_node(self):
        """ノード選択を解除"""
        print("[USER] UIStateManager: ノード選択解除")

        if not self.app_state.get("selected_node_id"):
            print("[INFO] UIStateManager: 選択中のノードがないため、処理をスキップ")
            return

        # 追加モードの場合はキャンセル
        if self.is_add_mode():
            print("[UPDATE] UIStateManager: 追加モードを維持し、選択解除")
            # 追加モードは維持する
            # ノード選択状態だけをクリア
            node_id = self.app_state.get("selected_node_id")
            self.app_state["selected_node_id"] = None
            self._ui_state["selected_node_id"] = None

            # ハイライト解除
            ui_manager = self.app_state.get('ui_manager')
            if ui_manager and node_id:
                ui_manager.update_node_style_recursive(
                    self.ui_controls["tree_view"].controls,
                    node_id,
                    False
                )

            return

        # 編集中の変更を破棄
        if self.is_edit_mode():
            print("[WARNING] UIStateManager: 未保存の変更を破棄")
            self.app_state["edit_buffer"].clear()
            self.set_edit_mode(False)

        # 選択解除
        node_id = self.app_state.get("selected_node_id")
        self.app_state["selected_node_id"] = None
        self._ui_state["selected_node_id"] = None

        # ハイライト解除
        ui_manager = self.app_state.get('ui_manager')
        if ui_manager and node_id:
            ui_manager.update_node_style_recursive(
                self.ui_controls["tree_view"].controls,
                node_id,
                False
            )

        # 詳細フォームをクリア
        form_manager = self.app_state.get('form_manager')
        if form_manager:
            form_manager.clear_detail_form()

        # ビューを更新
        self.set_current_view("tree")

        # UIを更新
        self.refresh_ui()

        print("[OK] UIStateManager: ノード選択解除完了")
    
    # ----- UI状態の一括更新 -----
    
    def refresh_ui(self):
        """UI全体を最新の状態で更新"""
        print("[UPDATE] UIStateManager: UI全体の更新を実行")

        # メインコンテンツの表示を確保
        self.ensure_main_content_visible()

        # 現在のビューとツリービューの更新状態に応じて処理
        current_view = self.get_current_view()

        # ツリービューの更新が必要な場合
        if self.is_tree_view_dirty():
            print("[UPDATE] UIStateManager: ツリービューの更新が必要")
            ui_manager = self.app_state.get('ui_manager')
            if ui_manager:
                ui_manager.update_tree_view()
            self.set_tree_view_dirty(False)

        # 追加モードの場合
        if self.is_add_mode():
            print("[UPDATE] UIStateManager: 追加モードのフォーム更新")
            form_manager = self.app_state.get('form_manager')
            if form_manager:
                form_manager.update_add_form()

        # 詳細表示モードの場合（選択されたノードがある）
        elif self.app_state.get("selected_node_id") is not None:
            print(f"[UPDATE] UIStateManager: 詳細フォーム更新 - ノードID: {self.app_state.get('selected_node_id')}")
            # 詳細フォームの更新が必要な場合またはフォームが表示されている場合
            if self.is_detail_form_dirty() or current_view == "detail":
                form_manager = self.app_state.get('form_manager')
                if form_manager:
                    form_manager.update_detail_form(self.app_state.get("selected_node_id"))
                self.set_detail_form_dirty(False)

        # ノード未選択の場合は詳細フォームをクリア
        elif current_view == "detail" or self.is_detail_form_dirty():
            print("[UPDATE] UIStateManager: 詳細フォームのクリア")
            form_manager = self.app_state.get('form_manager')
            if form_manager:
                form_manager.clear_detail_form()
            self.set_detail_form_dirty(False)

        # ボタン状態の更新
        form_manager = self.app_state.get('form_manager')
        if form_manager:
            form_manager.update_detail_buttons_state()

        # ページ全体を更新
        if self.page:
            self.page.update()

        print("[OK] UIStateManager: UI更新完了")
    
    # ----- ファイル操作UI状態 -----
    
    def set_file_loaded(self, file_path: str):
        """ファイル読み込み完了時のUI状態更新"""
        print(f"[FILE] UIStateManager: ファイル読み込み完了 - {file_path}")

        # ファイルパス表示を更新
        if "selected_file_path_text" in self.ui_controls:
            path_text = self.ui_controls["selected_file_path_text"]
            path_text.value = os.path.basename(file_path)
            path_text.visible = True
            self._safe_update_control(path_text, "selected_file_path_text")

        if "file_name_text" in self.ui_controls:
            file_name_text = self.ui_controls["file_name_text"]
            file_name_text.value = os.path.basename(file_path)
            self._safe_update_control(file_name_text, "file_name_text")

        # 保存ボタンを有効化
        if "save_button" in self.ui_controls:
            save_button = self.ui_controls["save_button"]
            save_button.disabled = False
            self._safe_update_control(save_button, "save_button")

        # メインコンテンツエリアを表示
        self.ensure_main_content_visible()

        # 検索UIを表示
        search_container = self.ui_controls.get('search_ui_container')
        if search_container:
            search_container.visible = True
            try:
                # ページに追加されている場合のみ更新
                if hasattr(search_container, '_page') and search_container._page is not None:
                    search_container.update()
                    # 検索UIが含まれるページセクションを更新
                    parent = search_container.parent
                    while parent and parent != self.app_state.get("page"):
                        if hasattr(parent, '_page') and parent._page is not None:
                            parent.update()
                        parent = parent.parent if hasattr(parent, 'parent') else None
            except Exception as ex:
                print(f"[WARNING] 検索UI更新エラー: {ex}")

        # ツリービューを更新するフラグを設定
        self.set_tree_view_dirty(True)

        # 各種フラグをリセット
        self.set_edit_mode(False)
        self.set_add_mode(False)
        self.set_current_view("tree")

        # UIの全体的な更新
        if self.page:
            self.page.update()


def create_ui_state_manager(app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: ft.Page, app_instance=None) -> UIStateManager:
    """UIStateManagerのインスタンスを作成する工場関数"""
    ui_state_manager = UIStateManager(app_state, ui_controls, page, app_instance)
    app_state["ui_state_manager"] = ui_state_manager
    return ui_state_manager