"""
form_manager.py
フォーム操作・イベントハンドラ関連のマネージャークラス

FleDjSONのフォーム生成、更新、イベント処理を担当する
ノードの詳細表示フォームや新規追加フォームの管理、フォームデータの保存などを行う
"""
import flet as ft
from flet import Colors
from typing import Optional, Dict, List, Any, Union, Tuple, Callable, Set
import json
import os
import uuid
import copy
import re
from collections import defaultdict
from managers.event_aware_manager import EventAwareManager
from event_hub import EventHub, EventType
from translation import t


class FormManager(EventAwareManager):
    """
    フォーム生成と処理を担当するマネージャークラス

    各種フォームの生成、表示、更新およびフォームイベントの処理を担当する
    編集バッファの管理、変更の保存・取り消し、フォーム状態の維持などを行う

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
        FormManagerを初期化します。

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
            manager_name="form_manager",
            event_hub=app_state.get("event_hub")
        )

        # 他のマネージャーへの参照（初期化後に設定される）
        self.ui_state_manager = None
        self.data_manager = None
        self.ui_manager = None
        self.search_manager = None

        # app_stateから既存のマネージャーがあれば取得
        self._load_managers_from_app_state()

        # 編集バッファの初期化
        if "edit_buffer" not in self.app_state:
            self.app_state["edit_buffer"] = {}

        # 削除予定フィールドの初期化
        if "removed_fields" not in self.app_state:
            self.app_state["removed_fields"] = set()
            
        # 入力順序追跡用のマップを初期化（キーパスを入力順にマッピング）
        self._key_input_order = {}
        self._input_counter = 0  # 入力順序をカウントする変数

        # コールバック関数の初期化
        self._on_save_callback = None
        self._on_cancel_callback = None
        self._on_delete_callback = None
        self._on_add_callback = None

        # FormManagerをapp_stateに登録
        self.app_state["form_manager"] = self

        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] FormManager initialized.")

    def _setup_event_subscriptions(self) -> None:
        """イベントハブへの購読を設定"""
        if self.event_hub:
            # 言語変更イベントを購読
            self.subscribe_to_event(EventType.LANGUAGE_CHANGED, self.on_language_changed)

    def on_language_changed(self, event) -> None:
        """言語変更時の処理"""
        # 現在のフォームが表示されている場合、ボタンのテキストを更新
        self._update_form_button_texts()
        
        # フォーム内の固定テキストを更新
        detail_form = self.ui_controls.get("detail_form_column")
        if detail_form and detail_form.controls:
            # フォームが空の初期状態の場合
            if len(detail_form.controls) == 1 and hasattr(detail_form.controls[0], 'value'):
                current_value = detail_form.controls[0].value
                # 初期メッセージかどうかを判定（言語非依存）
                if current_value in ["ノードを選択してください", "Select a node"]:
                    detail_form.controls[0].value = t("form.select_node_message")
                    detail_form.controls[0].update()

    def _update_form_button_texts(self):
        """フォームボタンのテキストを現在の言語で更新"""
        # 詳細フォームのボタンを更新
        if "detail_save_button" in self.ui_controls:
            save_btn = self.ui_controls["detail_save_button"]
            if save_btn and hasattr(save_btn, 'text'):
                save_btn.text = t("form.button.save_changes")
                if save_btn.page:
                    save_btn.update()
        
        if "detail_cancel_button" in self.ui_controls:
            cancel_btn = self.ui_controls["detail_cancel_button"]
            if cancel_btn and hasattr(cancel_btn, 'text'):
                cancel_btn.text = t("form.button.cancel")
                if cancel_btn.page:
                    cancel_btn.update()
        
        if "detail_delete_button" in self.ui_controls:
            delete_btn = self.ui_controls["detail_delete_button"]
            if delete_btn and hasattr(delete_btn, 'text'):
                delete_btn.text = t("form.button.delete_node")
                if delete_btn.page:
                    delete_btn.update()
        
        # 追加データボタンを更新
        if "add_data_button" in self.ui_controls:
            add_btn = self.ui_controls["add_data_button"]
            if add_btn and hasattr(add_btn, 'text'):
                add_btn.text = t("button.add")
                if add_btn.page:
                    add_btn.update()

    def _load_managers_from_app_state(self):
        """app_stateから他のマネージャーへの参照を取得"""
        if "ui_state_manager" in self.app_state:
            self.ui_state_manager = self.app_state["ui_state_manager"]

        if "data_manager" in self.app_state:
            self.data_manager = self.app_state["data_manager"]

        if "ui_manager" in self.app_state:
            self.ui_manager = self.app_state["ui_manager"]

        if "search_manager" in self.app_state:
            self.search_manager = self.app_state["search_manager"]

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

    def set_search_manager(self, search_manager):
        """SearchManagerを設定"""
        self.search_manager = search_manager
        return self
        
    def _get_key_input_order(self, key_path):
        """
        キーパスの入力順序を取得する。もし階層構造がある場合、親のパスの入力順序も参照する。
        
        Args:
            key_path (str): キーパス (e.g., "profile.name", "tags[0]")
            
        Returns:
            int: キーパスの入力順序。登録されていない場合は最大値を返す。
        """
        # キーパスが直接登録されている場合はその順序を返す
        if key_path in self._key_input_order:
            return self._key_input_order[key_path]
            
        # 親パスの入力順序を取得するロジック
        # 例: profile.contact.email の場合、profile.contact か profile の順序を参照
        parts = key_path.split('.')
        for i in range(len(parts) - 1, 0, -1):
            parent_path = '.'.join(parts[:i])
            if parent_path in self._key_input_order:
                # 親パスの順序 + 0.1 を返す（親より少し後の順序にする）
                return self._key_input_order[parent_path] + 0.1
                
        # 配列インデックスの処理（例: tags[0]）
        array_match = re.match(r'^(.+)\[\d+\]$', key_path)
        if array_match:
            array_path = array_match.group(1)
            if array_path in self._key_input_order:
                return self._key_input_order[array_path] + 0.1
        
        # 登録されていない場合は、ソート時に最後になるように大きな値を返す
        return float('inf')  # 無限大を返して最後にソートされるようにする
        
    def _get_parent_order(self, key_path):
        """
        キーパスの親の入力順序を取得する
        ソート時に、親の順序に基づいてグループ化するために使用
        
        Args:
            key_path (str): キーパス
            
        Returns:
            float: 親の入力順序。親がない場合は無限大
        """
        parts = key_path.split('.')
        array_match = re.match(r'^(.+)\[\d+\]$', key_path)
        
        # 配列の場合
        if array_match and not '.' in key_path:
            base = array_match.group(1)
            if base in self._key_input_order:
                return self._key_input_order[base]
            
        # 通常の階層構造
        if len(parts) > 1:
            parent = parts[0]
            if parent in self._key_input_order:
                return self._key_input_order[parent]
            
        return float('inf')
    
    # ----- コールバック設定メソッド -----
    
    def set_on_save_callback(self, callback: Callable[[ft.ControlEvent], None]):
        """保存ボタンクリック時のコールバックを設定"""
        self._on_save_callback = callback
    
    def set_on_cancel_callback(self, callback: Callable[[ft.ControlEvent], None]):
        """キャンセルボタンクリック時のコールバックを設定"""
        self._on_cancel_callback = callback
    
    def set_on_delete_callback(self, callback: Callable[[ft.ControlEvent], None]):
        """削除ボタンクリック時のコールバックを設定"""
        self._on_delete_callback = callback
    
    def set_on_add_callback(self, callback: Callable[[ft.ControlEvent], None]):
        """追加ボタンクリック時のコールバックを設定"""
        self._on_add_callback = callback
    
    # ----- 詳細フォーム関連メソッド -----
    
    def update_detail_form(self, selected_node_id: Optional[str]):
        """
        詳細フォームを指定されたノードIDの内容で更新する
        
        Args:
            selected_node_id: 選択されたノードのID
        """
        # データ追加モードの場合は何もしない
        if self.app_state.get("add_mode", False):
            print("[INFO] In add mode, skipping detail form update.")
            return
            
        # 削除確認モードを解除（UIStateManagerと整合させる）
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager:
            ui_state_manager.set_delete_confirm_mode(False)
        else:
            self.app_state["delete_confirm_mode"] = False
        
        print(f"[UPDATE] Updating detail form for node: {selected_node_id}")
        self.app_state["selected_node_id"] = selected_node_id
        controls = []
        
        # detail_form_columnの存在確認
        detail_form_column = self.ui_controls.get("detail_form_column")
        if detail_form_column is None:
            print("[WARNING] Warning: detail_form_column is not initialized yet")
            return
            
        detail_form_column.controls = controls  # いったんクリア
        
        if selected_node_id is None:
            controls.append(ft.Text(t("ui.select_node")))
            # ボタンを非表示にする
            if self.ui_controls.get("detail_save_button"): 
                self.ui_controls["detail_save_button"].visible = False
            if self.ui_controls.get("detail_cancel_button"): 
                self.ui_controls["detail_cancel_button"].visible = False
            if self.ui_controls.get("detail_delete_button"): 
                self.ui_controls["detail_delete_button"].visible = False
        else:
            # data_map から元のデータを取得し、edit_buffer の内容をマージして描画用データを作成
            original_node_data = self.app_state["data_map"].get(selected_node_id)
            node_data_to_render = None
            
            if original_node_data:
                # deepcopyして元のデータを変更しないようにする
                node_data_to_render = copy.deepcopy(original_node_data)
                
                # edit_buffer の内容をマージ
                if self.app_state.get("edit_buffer"):
                    print("  Merging edit_buffer into node_data for rendering...")
                    # キーをソートして適用順序を制御
                    # 改良版: 階層レベルを考慮しつつ入力順序を優先するソート基準
                    # 1. ルートレベルのフィールドは入力順序のみでソート
                    # 2. 子フィールドは親の入力順序を継承しつつ、部分的に階層深さを考慮
                    
                    # まず、キーを階層ごとにグループ化
                    root_keys = [k for k in self.app_state["edit_buffer"].keys() if '.' not in k and '[' not in k]
                    nested_keys = [k for k in self.app_state["edit_buffer"].keys() if '.' in k or '[' in k]
                    
                    # ルートキーは入力順序だけでソート
                    sorted_root_keys = sorted(root_keys, key=lambda x: self._get_key_input_order(x))
                    
                    # ネストされたキーは親の入力順に従ってソートしつつ、同じ親を持つキー同士では階層の浅いものを優先
                    sorted_nested_keys = sorted(nested_keys, 
                                      key=lambda x: (self._get_parent_order(x), x.count('.'), self._get_key_input_order(x)))
                    
                    # 両方を組み合わせる
                    sorted_keys = sorted_root_keys + sorted_nested_keys
                    for key_path in sorted_keys:
                        # バッファにキーが存在するか再確認
                        if key_path in self.app_state["edit_buffer"]:
                            value_to_set = self.app_state["edit_buffer"][key_path]
                            try:
                                # DataManagerのメソッドを使用
                                data_manager = self.app_state.get("data_manager")
                                if data_manager:
                                    data_manager.set_value_by_path(node_data_to_render, key_path, value_to_set)
                                    print(f"    Merged buffer: {key_path} = {repr(value_to_set)}")
                                else:
                                    print(f"[ERROR] DataManager not available for set_value_by_path")
                                    raise RuntimeError("DataManager not initialized")
                            except Exception as merge_err:
                                # マージエラーが発生しても、他のフィールドの描画は試みる
                                print(f"    [WARNING] Error merging buffer key '{key_path}': {merge_err}")
                        else:
                            print(f"    [INFO] Skipping merge for key '{key_path}' as it's no longer in buffer.")
            else:
                print(f"[WARNING] Node data not found in data_map for ID: {selected_node_id}")
                
            if node_data_to_render and isinstance(node_data_to_render, dict):
                field_details_map = {}
                if self.app_state.get("analysis_results"):
                    field_details_map = {
                        f["name"]: f for f in self.app_state["analysis_results"]["field_details"]
                    }
                    
                # マージ後のデータでフォームコントロールを構築
                form_controls = self.build_form_controls(node_data_to_render, field_details_map)
                controls.extend(form_controls)
                
                # 保存・キャンセル・削除ボタン (ui_controlsから取得)
                is_dirty = self.app_state.get("is_dirty", False)
                
                # ui_controlsからボタンを取得、なければ新規作成
                save_button = self.ui_controls.get("detail_save_button")
                if not save_button:
                    save_button = ft.ElevatedButton(
                        t("form.save_changes"),
                        icon=ft.Icons.SAVE,
                        on_click=self.save_changes,
                        disabled=not is_dirty
                    )
                    self.ui_controls["detail_save_button"] = save_button
                else:
                    # 既存のボタンの設定を更新
                    save_button.text = t("form.save_changes")
                    save_button.icon = ft.Icons.SAVE
                    save_button.on_click = self.save_changes
                    save_button.disabled = not is_dirty
                
                cancel_button = self.ui_controls.get("detail_cancel_button")
                if not cancel_button:
                    cancel_button = ft.OutlinedButton(
                        t("form.cancel"),
                        icon=ft.Icons.CANCEL_OUTLINED,
                        on_click=self.cancel_changes,
                        disabled=not is_dirty
                    )
                    self.ui_controls["detail_cancel_button"] = cancel_button
                else:
                    # 既存のボタンの設定を更新
                    cancel_button.text = t("form.cancel")
                    cancel_button.icon = ft.Icons.CANCEL_OUTLINED
                    cancel_button.on_click = self.cancel_changes
                    cancel_button.disabled = not is_dirty
                
                # 削除ボタンを追加（通常モード用）
                delete_button = self.ui_controls.get("detail_delete_button")
                if not delete_button:
                    delete_button = ft.OutlinedButton(
                        t("form.delete_node"),
                        icon=ft.Icons.DELETE_OUTLINED,
                        on_click=self.show_delete_confirmation,
                        style=ft.ButtonStyle(
                            color=ft.Colors.RED,
                            shape=ft.RoundedRectangleBorder(radius=5)
                        ),
                    )
                    self.ui_controls["detail_delete_button"] = delete_button
                else:
                    # 既存のボタンの設定を更新
                    delete_button.text = t("form.delete_node")
                    delete_button.icon = ft.Icons.DELETE_OUTLINED
                    delete_button.on_click = self.show_delete_confirmation
                    if not hasattr(delete_button, 'style') or delete_button.style is None:
                        delete_button.style = ft.ButtonStyle(
                            color=ft.Colors.RED,
                            shape=ft.RoundedRectangleBorder(radius=5)
                        )
                
                controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                delete_button,
                                ft.Container(expand=True),  # スペーサー
                                save_button, 
                                cancel_button
                            ],
                            alignment=ft.MainAxisAlignment.END,
                            spacing=10
                        ),
                        margin=ft.margin.only(top=15)
                    )
                )
                save_button.visible = True
                cancel_button.visible = True
                delete_button.visible = True
            else:
                # ノードデータが見つからないか、辞書型でない場合
                controls.append(ft.Text(f"{t('form.node_data_error')} (ID: {selected_node_id})"))
                if self.ui_controls.get("detail_save_button"): 
                    self.ui_controls["detail_save_button"].visible = False
                if self.ui_controls.get("detail_cancel_button"): 
                    self.ui_controls["detail_cancel_button"].visible = False
                if self.ui_controls.get("detail_delete_button"): 
                    self.ui_controls["detail_delete_button"].visible = False
        
        # 構築したコントロールでフォームを更新
        detail_form_column.controls = controls
        detail_form_column.update()
        print(f"[OK] Detail form column updated for node: {selected_node_id}")

        # ボタンの状態を明示的に更新 (is_dirty に基づいて)
        self.update_detail_buttons_state()

        # ハイライトされたフィールドへ自動スクロール
        self._scroll_to_highlighted_field()
    
    def clear_detail_form(self):
        """詳細フォームの内容をクリアする"""
        print("[CLEANUP] Clearing detail form")
        
        # detail_form_columnの存在確認
        detail_form_column = self.ui_controls.get("detail_form_column")
        if detail_form_column is None:
            print("[WARNING] Warning: detail_form_column is not initialized yet")
            return
            
        # 選択状態をクリア
        old_selected_id = self.app_state.get("selected_node_id")
        self.app_state["selected_node_id"] = None
        
        # コントロールをクリア
        detail_form_column.controls = [ft.Text(t("form.select_node_message"))]
        
        # ボタンを非表示に
        if self.ui_controls.get("detail_save_button"): 
            self.ui_controls["detail_save_button"].visible = False
        if self.ui_controls.get("detail_cancel_button"): 
            self.ui_controls["detail_cancel_button"].visible = False
        if self.ui_controls.get("detail_delete_button"): 
            self.ui_controls["detail_delete_button"].visible = False
        
        # UIを更新
        detail_form_column.update()
        print("[OK] Detail form cleared")
        
        # UIStateManagerと状態同期（選択ノードIDがクリアされたことを通知）
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager and old_selected_id:
            ui_state_manager.deselect_node()
    
    def update_detail_buttons_state(self):
        """詳細フォームの保存・キャンセル・削除ボタンの状態を更新する"""
        is_dirty = self.app_state.get("is_dirty", False)
        save_button = self.ui_controls.get("detail_save_button")
        cancel_button = self.ui_controls.get("detail_cancel_button")
        delete_button = self.ui_controls.get("detail_delete_button")
        
        print(f"[UPDATE] Update detail buttons state: is_dirty={is_dirty}")
        
        # save_buttonがある場合は状態を更新
        if save_button:
            old_disabled = save_button.disabled
            save_button.disabled = not is_dirty
            
            # ボタンがページに追加されているかを確認
            if hasattr(save_button, 'page') and save_button.page is not None:
                try:
                    save_button.update()
                except Exception as ex:
                    print(f"[ERROR] Error updating save_button: {ex}")
            else:
                # ページに追加されていない場合は親コンテナを更新
                parent_container = self.ui_controls.get("detail_form_column")
                if parent_container and hasattr(parent_container, 'page') and parent_container.page is not None:
                    try:
                        parent_container.update()
                    except Exception as ex:
                        print(f"[ERROR] Error updating parent_container: {ex}")
        
        # cancel_buttonがある場合は状態を更新
        if cancel_button:
            old_disabled = cancel_button.disabled
            cancel_button.disabled = not is_dirty
            
            # ボタンがページに追加されているかを確認
            if hasattr(cancel_button, 'page') and cancel_button.page is not None:
                try:
                    cancel_button.update()
                except Exception as ex:
                    print(f"[ERROR] Error updating cancel_button: {ex}")
        
        # delete_buttonがある場合に更新を確認（削除ボタンはis_dirtyに依存しない）
        if delete_button and hasattr(delete_button, 'page') and delete_button.page is not None:
            try:
                delete_button.update()
            except Exception as ex:
                print(f"[ERROR] Error updating delete_button: {ex}")
        
        # ボタン更新に問題がある場合、フォームコンテナ全体を再構築して更新
        if is_dirty and save_button and save_button.disabled:
            print(f"[UPDATE] Button update issue detected, triggering full form update")
            if self.app_state.get("selected_node_id"):
                self.update_detail_form(self.app_state.get("selected_node_id"))
    
    def _is_field_highlighted(self, field_path: str) -> bool:
        """
        フィールドがハイライト対象かどうかを判定する

        Args:
            field_path: フィールドのパス

        Returns:
            ハイライト対象の場合True
        """
        highlight_paths = self.app_state.get("highlight_field_paths", [])
        if not highlight_paths:
            return False

        # 完全一致チェック
        if field_path in highlight_paths:
            return True

        # 親パスが含まれているかチェック（例: "profile" がハイライト対象なら "profile.name" もハイライト）
        for hp in highlight_paths:
            # 親パスとしてマッチするかチェック
            if field_path.startswith(hp + ".") or field_path.startswith(hp + "["):
                return True
            # 子パスとしてマッチするかチェック（例: "tags[0]" がハイライト対象なら "tags" もハイライト）
            if hp.startswith(field_path + ".") or hp.startswith(field_path + "["):
                return True

        return False

    def _get_highlight_style(self) -> dict:
        """
        ハイライト用のスタイル設定を返す

        Returns:
            ハイライトスタイルの辞書
        """
        return {
            "bgcolor": Colors.with_opacity(0.15, Colors.YELLOW),
            "border_color": Colors.AMBER,
            "border_width": 2,
        }

    def _scroll_to_highlighted_field(self) -> None:
        """
        ハイライトされたフィールドへ自動スクロールする
        """
        highlight_paths = self.app_state.get("highlight_field_paths", [])
        if not highlight_paths:
            return

        # 最初のハイライトパスを取得
        first_highlight_path = highlight_paths[0] if highlight_paths else None
        if not first_highlight_path:
            return

        # detail_form_columnを取得
        detail_form_column = self.ui_controls.get("detail_form_column")
        if not detail_form_column:
            return

        # ハイライトされたコントロールを再帰的に検索
        def find_highlighted_control(controls, target_path):
            for control in controls:
                # コントロールのdataを確認
                if hasattr(control, 'data'):
                    ctrl_data = control.data
                    if isinstance(ctrl_data, dict):
                        ctrl_path = ctrl_data.get("path", "")
                        if ctrl_path == target_path or target_path.startswith(ctrl_path + ".") or target_path.startswith(ctrl_path + "["):
                            return control
                    elif isinstance(ctrl_data, str) and ctrl_data == target_path:
                        return control

                # 子コントロールを再帰的に検索
                if hasattr(control, 'controls'):
                    result = find_highlighted_control(control.controls, target_path)
                    if result:
                        return result
                if hasattr(control, 'content') and control.content:
                    if hasattr(control.content, 'controls'):
                        result = find_highlighted_control(control.content.controls, target_path)
                        if result:
                            return result

            return None

        # ハイライトされたコントロールを検索
        highlighted_control = find_highlighted_control(detail_form_column.controls, first_highlight_path)

        if highlighted_control:
            try:
                # scroll_toメソッドが使用可能な場合はスクロール
                if hasattr(detail_form_column, 'scroll_to'):
                    # キーを使用してスクロール
                    if hasattr(highlighted_control, 'key') and highlighted_control.key:
                        detail_form_column.scroll_to(key=highlighted_control.key, duration=300)
                    else:
                        # オフセットを使用してスクロール（おおよその位置）
                        # 最初のハイライトが見えるようにスクロール
                        detail_form_column.scroll_to(offset=0, duration=300)
                print(f"[SCROLL] ハイライトフィールド '{first_highlight_path}' へスクロールしました")
            except Exception as e:
                print(f"[WARNING] スクロールに失敗: {e}")

    def build_form_controls(self, data_obj: dict, field_details_map: dict, key_prefix: str = "") -> list[ft.Control]:
        """
        データオブジェクトに基づいてフォームコントロールを再帰的に構築する

        Args:
            data_obj: フォームに表示するデータオブジェクト
            field_details_map: フィールド情報を含む辞書
            key_prefix: キーパスのプレフィックス

        Returns:
            構築されたコントロールのリスト
        """
        # UIManagerのtoggle_expansion関数を取得
        ui_manager = self.app_state.get("ui_manager")
        toggle_expansion_func = getattr(ui_manager, "toggle_expansion", None) if ui_manager else None
        if not toggle_expansion_func:
            # フォールバック: 簡単なダミー関数を定義
            def toggle_expansion_func(e):
                print("[WARNING] toggle_expansion機能が利用できません")
                pass

        controls = []
        id_key = self.app_state["analysis_results"]["heuristic_suggestions"].get("identifier", "id")
        keys_order = list(data_obj.keys())

        # IDキーを先頭に移動
        if id_key in keys_order:
            keys_order.remove(id_key)
            keys_order.insert(0, id_key)

        for key in keys_order:
            value = data_obj[key]
            current_key_path = f"{key_prefix}.{key}" if key_prefix else key
            is_id_field = (current_key_path == id_key)

            # フィールド情報の取得とタイプの判定
            field_info = field_details_map.get(current_key_path)
            field_type = "unknown"
            if field_info and field_info["types"]:
                field_type = field_info["types"][0][0]
            elif isinstance(value, bool): field_type = "bool"
            elif isinstance(value, int): field_type = "int"
            elif isinstance(value, float): field_type = "float"
            elif isinstance(value, list): field_type = "list"
            elif isinstance(value, dict): field_type = "dict"
            elif isinstance(value, str): field_type = "string"

            control_to_add = None

            # ハイライト判定
            is_highlighted = self._is_field_highlighted(current_key_path)
            highlight_style = self._get_highlight_style() if is_highlighted else {}

            # 辞書型の場合は再帰的に処理
            if field_type == "dict":
                nested_controls = self.build_form_controls(value, field_details_map, current_key_path)
                if nested_controls:
                    # ハイライト時はアイコンも色変更
                    header_icon_color = Colors.AMBER if is_highlighted else None
                    header_content = ft.Row(
                        [
                            ft.Icon(ft.Icons.SETTINGS_INPUT_COMPONENT, color=header_icon_color),
                            ft.Text(key, weight=ft.FontWeight.W_500,
                                   color=Colors.AMBER_900 if is_highlighted else None)
                        ],
                    )
                    clickable_header = ft.Container(
                        content=header_content,
                        on_click=toggle_expansion_func,
                        ink=True,
                        border_radius=ft.border_radius.all(4),
                        bgcolor=highlight_style.get("bgcolor") if is_highlighted else None,
                    )
                    expansion_panel = ft.ExpansionPanelList(
                        expand_icon_color=Colors.with_opacity(0.5, Colors.ON_SURFACE),
                        elevation=0,
                        divider_color=Colors.with_opacity(0.3, Colors.OUTLINE),
                        controls=[
                            ft.ExpansionPanel(
                                header=clickable_header,
                                content=ft.Container(
                                    content=ft.Column(nested_controls, spacing=8),
                                    padding=ft.padding.only(left=10, top=5, bottom=5)
                                ),
                                bgcolor=Colors.with_opacity(0.03, Colors.ON_SURFACE_VARIANT),
                                expanded=True,  # デフォルトで展開
                            )
                        ],
                        data=current_key_path
                    )
                    # ハイライト時はボーダーでラップ
                    if is_highlighted:
                        control_to_add = ft.Container(
                            content=expansion_panel,
                            border=ft.border.all(highlight_style.get("border_width", 2),
                                                highlight_style.get("border_color", Colors.AMBER)),
                            border_radius=5,
                            data={"path": current_key_path, "highlighted": True}
                        )
                    else:
                        control_to_add = expansion_panel
                else:
                    text_area = ft.TextField(
                        label=key,
                        value=str(value),
                        multiline=True,
                        min_lines=3,
                        max_lines=10,
                        dense=True,
                        data={"path": current_key_path, "type": "dict"},
                        on_change=self.on_form_field_change,
                        hint_text=t("form.dict_json_hint"),
                        bgcolor=highlight_style.get("bgcolor") if is_highlighted else None,
                        border_color=highlight_style.get("border_color") if is_highlighted else None,
                    )
                    control_to_add = ft.Container(
                        content=ft.Column([
                            ft.Text(t("form.dict_type"), size=12, color=Colors.ON_SURFACE_VARIANT),
                            text_area
                        ]),
                        data={"path": current_key_path, "type": "dict", "highlighted": is_highlighted}
                    )

            # リスト型の場合
            elif field_type.startswith("list"):
                if isinstance(value, list):
                    list_items_controls = []
                    for index, item in enumerate(value):
                        item_prefix = f"{current_key_path}[{index}]"
                        # リスト要素のハイライト判定
                        is_item_highlighted = self._is_field_highlighted(item_prefix)
                        item_highlight_style = self._get_highlight_style() if is_item_highlighted else {}

                        if isinstance(item, dict):
                            dict_header = ft.Row([
                                ft.Text(f"[{index}]", weight=ft.FontWeight.W_500,
                                       color=Colors.AMBER_900 if is_item_highlighted else None),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_size=16,
                                    tooltip=t("form.delete_item_tooltip").format(index=index),
                                    data={"key_path": current_key_path, "index": index},
                                    on_click=lambda e: self.delete_list_item(e, e.control.data["key_path"], e.control.data["index"])
                                )
                            ])
                            list_items_controls.append(dict_header)
                            nested_item_controls = self.build_form_controls(item, field_details_map, item_prefix)
                            # ハイライト時はボーダー色を変更
                            item_border_color = item_highlight_style.get("border_color", Colors.OUTLINE_VARIANT) if is_item_highlighted else Colors.OUTLINE_VARIANT
                            item_border_width = item_highlight_style.get("border_width", 1) if is_item_highlighted else 1
                            list_items_controls.append(
                                ft.Container(
                                    content=ft.Column(nested_item_controls, spacing=5),
                                    padding=ft.padding.only(left=15),
                                    border=ft.border.all(item_border_width, item_border_color),
                                    border_radius=5,
                                    margin=ft.margin.only(bottom=10),
                                    bgcolor=item_highlight_style.get("bgcolor") if is_item_highlighted else None,
                                    data={"path": item_prefix, "highlighted": is_item_highlighted}
                                )
                            )
                        else:
                            # プリミティブ要素のハイライト
                            item_row = ft.Row([
                                ft.Text(f"[{index}]",
                                       color=Colors.AMBER_900 if is_item_highlighted else None),
                                ft.TextField(
                                    value=str(item),
                                    expand=True,
                                    dense=True,
                                    data={"path": item_prefix, "type": "list_item"},
                                    on_change=self.on_form_field_change,
                                    bgcolor=item_highlight_style.get("bgcolor") if is_item_highlighted else None,
                                    border_color=item_highlight_style.get("border_color") if is_item_highlighted else None,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_size=16,
                                    tooltip=t("form.delete_item_tooltip").format(index=index),
                                    data={"key_path": current_key_path, "index": index},
                                    on_click=lambda e: self.delete_list_item(e, e.control.data["key_path"], e.control.data["index"])
                                )
                            ])
                            list_items_controls.append(item_row)

                    add_item_button = ft.TextButton(
                        t("form.add_item_button"),
                        icon=ft.Icons.ADD,
                        on_click=lambda e, kp=current_key_path: self.add_list_item(e, kp),
                        data=current_key_path
                    )

                    # リスト全体のハイライト
                    header_icon_color = Colors.AMBER if is_highlighted else None
                    header_content = ft.Row(
                        [
                            ft.Icon(ft.Icons.FORMAT_LIST_NUMBERED, color=header_icon_color),
                            ft.Text(f"{key} [{len(value)} items]", weight=ft.FontWeight.W_500,
                                   color=Colors.AMBER_900 if is_highlighted else None)
                        ],
                    )
                    clickable_header = ft.Container(
                        content=header_content,
                        on_click=toggle_expansion_func,
                        ink=True,
                        border_radius=ft.border_radius.all(4),
                        bgcolor=highlight_style.get("bgcolor") if is_highlighted else None,
                    )
                    expansion_panel = ft.ExpansionPanelList(
                        expand_icon_color=Colors.with_opacity(0.5, Colors.ON_SURFACE),
                        elevation=0,
                        divider_color=Colors.with_opacity(0.3, Colors.OUTLINE),
                        controls=[
                            ft.ExpansionPanel(
                                header=clickable_header,
                                content=ft.Container(
                                    content=ft.Column(
                                        list_items_controls + [add_item_button],
                                        spacing=5
                                    ),
                                    padding=ft.padding.only(left=10, top=5, bottom=5)
                                ),
                                bgcolor=Colors.with_opacity(0.03, Colors.ON_SURFACE_VARIANT),
                                expanded=True,  # デフォルトで展開
                            )
                        ],
                        data=current_key_path
                    )
                    # ハイライト時はボーダーでラップ
                    if is_highlighted:
                        control_to_add = ft.Container(
                            content=expansion_panel,
                            border=ft.border.all(highlight_style.get("border_width", 2),
                                                highlight_style.get("border_color", Colors.AMBER)),
                            border_radius=5,
                            data={"path": current_key_path, "highlighted": True}
                        )
                    else:
                        control_to_add = expansion_panel
                else:
                    text_area = ft.TextField(
                        label=key,
                        value=str(value),
                        multiline=True,
                        min_lines=3,
                        max_lines=10,
                        dense=True,
                        data=current_key_path,
                        on_change=self.on_form_field_change,
                        hint_text=t("form.list_json_hint"),
                        bgcolor=highlight_style.get("bgcolor") if is_highlighted else None,
                        border_color=highlight_style.get("border_color") if is_highlighted else None,
                    )
                    control_to_add = ft.Container(
                        content=ft.Column([
                            ft.Text(t("form.list_type"), size=12, color=Colors.ON_SURFACE_VARIANT),
                            text_area
                        ]),
                        data={"path": current_key_path, "highlighted": is_highlighted}
                    )

            # ブール型の場合
            elif field_type == "bool":
                checkbox = ft.Checkbox(
                    label=key,
                    value=bool(value),
                    data={"path": current_key_path, "type": "bool"},
                    on_change=self.on_form_field_change,
                    fill_color=Colors.AMBER if is_highlighted else None,
                )
                # ハイライト時はコンテナでラップ
                if is_highlighted:
                    control_to_add = ft.Container(
                        content=checkbox,
                        bgcolor=highlight_style.get("bgcolor"),
                        border=ft.border.all(highlight_style.get("border_width", 2),
                                            highlight_style.get("border_color", Colors.AMBER)),
                        border_radius=5,
                        padding=5,
                        data={"path": current_key_path, "highlighted": True}
                    )
                else:
                    control_to_add = checkbox

            # 数値型の場合
            elif field_type == "int" or field_type == "float":
                control_to_add = ft.TextField(
                    label=key,
                    value=str(value),
                    keyboard_type=ft.KeyboardType.NUMBER,
                    data={"path": current_key_path, "is_id": is_id_field, "highlighted": is_highlighted},
                    dense=True,
                    hint_text=t("form.id_field_hint") if is_id_field else None,
                    on_change=self.on_id_field_change if is_id_field else self.on_form_field_change,
                    bgcolor=highlight_style.get("bgcolor") if is_highlighted else None,
                    border_color=highlight_style.get("border_color") if is_highlighted else None,
                )

            # その他の型（文字列など）の場合
            else:
                control_to_add = ft.TextField(
                    label=key,
                    value=str(value) if value is not None else "",
                    multiline=isinstance(value, str) and (len(value) > 60 or '\n' in value),
                    min_lines=1,
                    max_lines=5 if isinstance(value, str) and (len(value) > 60 or '\n' in value) else 1,
                    dense=True,
                    data={"path": current_key_path, "is_id": is_id_field, "highlighted": is_highlighted},
                    hint_text=t("form.id_field_hint") if is_id_field else None,
                    on_change=self.on_id_field_change if is_id_field else self.on_form_field_change,
                    bgcolor=highlight_style.get("bgcolor") if is_highlighted else None,
                    border_color=highlight_style.get("border_color") if is_highlighted else None,
                )

            if control_to_add:
                controls.append(control_to_add)

        return controls
    
    # ----- フォーム新規追加モード関連メソッド -----
    
    def update_add_form(self):
        """新規追加フォームを表示する"""
        print("[UPDATE] Updating add form...")
        
        # ui_controlsからdetail_form_columnを取得
        detail_form_column = self.ui_controls.get("detail_form_column")
        if detail_form_column is None:
            print("[WARNING] Warning: detail_form_column is not initialized yet")
            return

        # 現在の選択状態をクリア
        self.app_state["selected_node_id"] = None

        # コントロールをクリア
        controls = []
        detail_form_column.controls = controls

        # 分析結果がない場合は空のフォームを表示
        if not self.app_state.get("analysis_results") or not self.app_state.get("raw_data"):
            controls.append(ft.Text(t("error.file_not_selected"), color=Colors.RED))
            detail_form_column.update()
            return

        # テンプレートオブジェクトを作成
        # 既存のデータから典型的な構造を推測して新規作成フォームを構築
        try:
            # 典型的なノードを見つける
            id_key = self.app_state["analysis_results"]["heuristic_suggestions"].get("identifier", "id")

            # 重要な修正: edit_bufferが空の場合のみ初期化する
            # 既に値が入力されている場合は既存のedit_bufferを使用
            if not self.app_state.get("edit_buffer"):
                print("  Initializing new edit_buffer with template values")
                sample_obj = None

                if isinstance(self.app_state["raw_data"], list) and len(self.app_state["raw_data"]) > 0:
                    # サンプルとしてノードを1つ選択
                    for item in self.app_state["raw_data"]:
                        if isinstance(item, dict) and id_key in item:
                            sample_obj = item
                            break

                    # サンプルが見つからなければ最初の辞書型オブジェクトを使用
                    if sample_obj is None:
                        for item in self.app_state["raw_data"]:
                            if isinstance(item, dict):
                                sample_obj = item
                                break

                if sample_obj is None:
                    # サンプルが見つからない場合は最小限のオブジェクトを作成
                    sample_obj = {id_key: ""}

                # テンプレートオブジェクトの作成（ディープコピー）
                template_obj = copy.deepcopy(sample_obj)

                # テンプレートの値をリセット
                def reset_values(obj):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, (dict, list)):
                                reset_values(value)  # 再帰的に処理
                            elif isinstance(value, str):
                                obj[key] = ""  # 文字列は空にする
                            elif isinstance(value, (int, float)):
                                obj[key] = 0  # 数値は0にする
                            elif isinstance(value, bool):
                                obj[key] = False  # 真偽値はFalseにする
                            else:
                                obj[key] = None  # その他はNoneにする
                    elif isinstance(obj, list):
                        # リストは1つ目の要素だけ残して他は削除、中身もリセット
                        if len(obj) > 0:
                            first_item = obj[0]
                            obj.clear()
                            if isinstance(first_item, (dict, list)):
                                reset_values(first_item)  # 再帰的に処理
                                obj.append(first_item)
                            else:
                                # 単純な型の場合は適切なデフォルト値を追加
                                if isinstance(first_item, str):
                                    obj.append("")
                                elif isinstance(first_item, (int, float)):
                                    obj.append(0)
                                elif isinstance(first_item, bool):
                                    obj.append(False)
                                else:
                                    obj.append(None)

                # テンプレートの値をリセット
                reset_values(template_obj)

                # 新しいedit_bufferを初期化
                self.app_state["edit_buffer"] = {}

                # テンプレートから各フィールドの初期値をバッファに設定
                def populate_edit_buffer(obj, prefix=""):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            current_path = f"{prefix}.{key}" if prefix else key
                            if isinstance(value, (dict, list)) and value:  # 空でない辞書やリスト
                                populate_edit_buffer(value, current_path)
                            else:
                                self.app_state["edit_buffer"][current_path] = value
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            current_path = f"{prefix}[{i}]"
                            if isinstance(item, (dict, list)) and item:  # 空でない辞書やリスト
                                populate_edit_buffer(item, current_path)
                            else:
                                self.app_state["edit_buffer"][current_path] = item

                # edit_bufferに初期値を設定
                populate_edit_buffer(template_obj)

                # 自動生成IDをedit_bufferに設定
                existing_ids = list(self.app_state["data_map"].keys())
                new_id = None

                # 1. プレフィックス＋数字形式のIDの生成を試みる
                data_manager = self.app_state.get("data_manager")
                if data_manager and hasattr(data_manager, "generate_next_prefixed_id"):
                    prefixed_id = data_manager.generate_next_prefixed_id(existing_ids)
                else:
                    # データマネージャーが利用できない場合はNoneを返す
                    prefixed_id = None
                    print("[WARNING] DataManagerが利用できないため、プレフィックス付きID生成をスキップします")

                if prefixed_id:
                    # プレフィックス付きIDが生成できた場合はそれを使用
                    new_id = prefixed_id
                    print(f"  Generated prefixed ID: {new_id}")
                else:
                    # プレフィックス付きIDが生成できなかった場合、フォールバックのロジックを実行
                    id_field_info = next((f for f in self.app_state["analysis_results"]["field_details"] if f["name"] == id_key), None)
                    id_type = "string" # デフォルトは文字列
                    if id_field_info and id_field_info["types"]:
                        id_type = id_field_info["types"][0][0] # 最も一般的な型を取得

                    if id_type == "int":
                        numeric_ids = [int(id_) for id_ in existing_ids if str(id_).isdigit()]
                        new_id = max(numeric_ids) + 1 if numeric_ids else 1
                    elif id_type == "string":
                         # UUID形式かどうかを簡易的にチェック
                         is_uuid_like = False
                         if existing_ids:
                             uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
                             if uuid_pattern.match(str(existing_ids[0])):
                                 is_uuid_like = True

                         if is_uuid_like:
                             new_id = str(uuid.uuid4())
                         else:
                             # UUID形式でなければ、単純な文字列IDを生成（例: "new_item_1"）
                             count = 1
                             while f"new_item_{count}" in existing_ids:
                                 count += 1
                             new_id = f"new_item_{count}"
                    else: # float や bool など、通常IDには使われない型の場合もUUIDを生成
                         new_id = str(uuid.uuid4())

                if new_id is not None:
                    # IDをバッファに設定
                    self.app_state["edit_buffer"][id_key] = new_id
                    print(f"  Auto-generated ID set in edit_buffer: {id_key} = {new_id}")

                print(f"  Initialized edit_buffer with {len(self.app_state['edit_buffer'])} default fields")
            else:
                print(f"  Using existing edit_buffer with {len(self.app_state['edit_buffer'])} fields")

            # フォームを構築
            # field_detailsを取得
            field_details = self.app_state["analysis_results"].get("field_details", [])
            if not field_details:
                print("[WARNING] Warning: field_detailsが見つかりません")
                controls.append(ft.Text(t("error.field_info_missing"), color=Colors.RED))
                detail_form_column.update()
                return

            # フォームを構築
            field_details = self.app_state["analysis_results"]["field_details"]
            field_details_map = {f["name"]: f for f in field_details}
            
            # edit_bufferからデータオブジェクトを再構築
            rebuilt_obj = {}
            data_manager = self.app_state.get("data_manager")
            if data_manager:
                for key_path, value in self.app_state["edit_buffer"].items():
                    try:
                        data_manager.set_value_by_path(rebuilt_obj, key_path, value)
                    except Exception as ex:
                        print(f"  [WARNING] Error setting path {key_path}: {ex}")
            
            # 新規作成フォームのタイトルとヘルプテキスト
            controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(t("form.new_node_title"), size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(t("form.new_node_description"), size=14),
                    ]),
                    margin=ft.margin.only(bottom=15)
                )
            )
            
            # 再構築したオブジェクトからフォームコントロールを生成
            form_controls = self.build_add_form_controls(rebuilt_obj, field_details_map)
            controls.extend(form_controls)

            # 追加・キャンセルボタン
            save_button = ft.ElevatedButton(
                t("form.add_item"),
                icon=ft.Icons.ADD,
                on_click=self.commit_new_node
            )
            
            cancel_button = ft.OutlinedButton(
                t("form.cancel"),
                icon=ft.Icons.CANCEL_OUTLINED,
                on_click=lambda e: self.toggle_add_mode(e)
            )
            
            controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(expand=True),  # スペーサー
                            save_button, 
                            cancel_button
                        ],
                        alignment=ft.MainAxisAlignment.END,
                        spacing=10
                    ),
                    margin=ft.margin.only(top=15)
                )
            )
            
            # 構築したコントロールでフォームを更新
            detail_form_column.controls = controls
            detail_form_column.update()
            print(f"[OK] Add form updated with {len(form_controls)} controls")

        except Exception as ex:
            print(f"[ERROR] Error in update_add_form: {ex}")
            import traceback
            traceback.print_exc()
            controls.append(ft.Text(f"{t('form.error')}: {str(ex)}", color=Colors.RED))
            detail_form_column.controls = controls
            detail_form_column.update()

    def update_add_form_with_template(self, template_data: Dict[str, Any]):
        """テンプレートを使用して新規追加モード用のフォームを表示する
        
        Args:
            template_data (Dict): テンプレートから生成されたデータ
        """
        print("[UPDATE] Updating add form with template...")
        
        # 詳細表示エリアをクリア
        detail_form_column = self.ui_controls.get("detail_form_column")
        detail_form_column.controls.clear()
        
        # タイトルを追加
        title = ft.Text(t("form.template_title"), size=18, weight="bold")
        detail_form_column.controls.append(title)
        
        # 説明テキストを追加
        description = ft.Text(
            t("form.template_description"),
            size=14,
            color=Colors.ON_SURFACE_VARIANT
        )
        detail_form_column.controls.append(description)
        
        # テンプレートデータをバッファにコピー
        self.app_state["edit_buffer"] = copy.deepcopy(template_data)
        
        # パターン情報を取得
        detected_patterns = self.app_state.get("detected_patterns", {})
        field_roles = self.app_state.get("field_roles", {})
        
        # フォームフィールドを構築
        form_fields = []
        
        # フィールドの役割に基づいてソート
        field_order = []
        for field, value in template_data.items():
            # フィールドの重要度に基づいて順序付け（IDフィールド、名前フィールド、その他の順）
            if field_roles.get(field, "") in ["id", "parent_id"]:
                order = 0
            elif field_roles.get(field, "") in ["name", "label", "title"]:
                order = 1
            else:
                order = 2
            field_order.append((field, order))
        
        # 順序付けされたフィールドでフォーム構築
        for field, _ in sorted(field_order, key=lambda x: x[1]):
            value = template_data.get(field)
            
            # フィールドの型情報（利用可能な場合）
            field_type = None
            data_templates = self.app_state.get("data_templates", {})
            if "main" in data_templates and "fields" in data_templates["main"]:
                field_info = data_templates["main"]["fields"].get(field, {})
                field_type = field_info.get("type")
            
            # テキストフィールドを作成
            field_label = field
            if field in field_roles:
                field_label = f"{field} ({field_roles[field]})"
                
            field_control = ft.TextField(
                label=field_label,
                value="" if value is None else str(value),
                data={"field_path": field, "field_type": field_type},
                on_change=self.on_form_field_change,
                hint_text=t("form.input_hint").format(type=field_type) if field_type else t("form.enter_value"),
                expand=True
            )
            
            # 役割に基づいて追加のスタイルを適用
            if field_roles.get(field) in ["id", "parent_id"]:
                field_control.label_style = ft.TextStyle(weight="bold")
                
            form_fields.append(field_control)
        
        # フォームフィールドを追加
        for control in form_fields:
            detail_form_column.controls.append(control)
            
        # フィールド追加セクション
        add_field_section = ft.Container(
            content=ft.Column(
                [
                    ft.Text(t("form.add_field_title"), size=16, weight="bold"),
                    ft.Row(
                        [
                            ft.TextField(
                                label=t("form.field_name_label"),
                                expand=True,
                                data="new_field_name"
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ADD_CIRCLE,
                                tooltip=t("form.add_field_tooltip"),
                                on_click=self._on_add_field_click
                            )
                        ]
                    )
                ]
            ),
            margin=ft.margin.only(top=20, bottom=10),
            padding=10,
            border=ft.border.all(1, Colors.OUTLINE),
            border_radius=5
        )
        detail_form_column.controls.append(add_field_section)
        
        # ボタンコンテナの作成
        button_container = ft.Container(
            content=ft.Row(
                [
                    ft.ElevatedButton(
                        "追加",
                        icon=ft.Icons.ADD,
                        on_click=self.commit_new_node,
                        bgcolor=Colors.PRIMARY
                    ),
                    ft.TextButton(
                        "キャンセル",
                        icon=ft.Icons.CANCEL,
                        on_click=lambda e: self.ui_state_manager.set_add_mode(False) if self.ui_state_manager else None,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=10
            ),
            margin=ft.margin.only(top=20)
        )
        
        detail_form_column.controls.append(button_container)
        detail_form_column.update()

        # ui_controlsからdetail_form_columnを取得
        detail_form_column = self.ui_controls.get("detail_form_column")
        if detail_form_column is None:
            print("[WARNING] Warning: detail_form_column is not initialized yet")
            return

        # 現在の選択状態をクリア
        self.app_state["selected_node_id"] = None

        # コントロールをクリア
        controls = []
        detail_form_column.controls = controls

        # 分析結果がない場合は空のフォームを表示
        if not self.app_state.get("analysis_results") or not self.app_state.get("raw_data"):
            controls.append(ft.Text(t("error.file_not_selected"), color=Colors.RED))
            detail_form_column.update()
            return

        # テンプレートオブジェクトを作成
        # 既存のデータから典型的な構造を推測して新規作成フォームを構築
        try:
            # 典型的なノードを見つける
            id_key = self.app_state["analysis_results"]["heuristic_suggestions"].get("identifier", "id")

            # 重要な修正: edit_bufferが空の場合のみ初期化する
            # 既に値が入力されている場合は既存のedit_bufferを使用
            if not self.app_state.get("edit_buffer"):
                print("  Initializing new edit_buffer with template values")
                sample_obj = None

                if isinstance(self.app_state["raw_data"], list) and len(self.app_state["raw_data"]) > 0:
                    # サンプルとしてノードを1つ選択
                    for item in self.app_state["raw_data"]:
                        if isinstance(item, dict) and id_key in item:
                            sample_obj = item
                            break

                    # サンプルが見つからなければ最初の辞書型オブジェクトを使用
                    if sample_obj is None:
                        for item in self.app_state["raw_data"]:
                            if isinstance(item, dict):
                                sample_obj = item
                                break

                if sample_obj is None:
                    # サンプルが見つからない場合は最小限のオブジェクトを作成
                    sample_obj = {id_key: ""}

                # テンプレートオブジェクトの作成（ディープコピー）
                template_obj = copy.deepcopy(sample_obj)

                # テンプレートの値をリセット
                def reset_values(obj):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, (dict, list)):
                                reset_values(value)  # 再帰的に処理
                            elif isinstance(value, str):
                                obj[key] = ""  # 文字列は空にする
                            elif isinstance(value, (int, float)):
                                obj[key] = 0  # 数値は0にする
                            elif isinstance(value, bool):
                                obj[key] = False  # 真偽値はFalseにする
                            else:
                                obj[key] = None  # その他はNoneにする
                    elif isinstance(obj, list):
                        # リストは1つ目の要素だけ残して他は削除、中身もリセット
                        if len(obj) > 0:
                            first_item = obj[0]
                            obj.clear()
                            if isinstance(first_item, (dict, list)):
                                reset_values(first_item)  # 再帰的に処理
                                obj.append(first_item)
                            else:
                                # 単純な型の場合は適切なデフォルト値を追加
                                if isinstance(first_item, str):
                                    obj.append("")
                                elif isinstance(first_item, (int, float)):
                                    obj.append(0)
                                elif isinstance(first_item, bool):
                                    obj.append(False)
                                else:
                                    obj.append(None)

                # テンプレートの値をリセット
                reset_values(template_obj)

                # 新しいedit_bufferを初期化
                self.app_state["edit_buffer"] = {}

                # テンプレートから各フィールドの初期値をバッファに設定
                def populate_edit_buffer(obj, prefix=""):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            current_path = f"{prefix}.{key}" if prefix else key
                            if isinstance(value, (dict, list)) and value:  # 空でない辞書やリスト
                                populate_edit_buffer(value, current_path)
                            else:
                                self.app_state["edit_buffer"][current_path] = value
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            current_path = f"{prefix}[{i}]"
                            if isinstance(item, (dict, list)) and item:  # 空でない辞書やリスト
                                populate_edit_buffer(item, current_path)
                            else:
                                self.app_state["edit_buffer"][current_path] = item

                # edit_bufferに初期値を設定
                populate_edit_buffer(template_obj)

                # 自動生成IDをedit_bufferに設定
                existing_ids = list(self.app_state["data_map"].keys())
                new_id = None

                # 1. プレフィックス＋数字形式のIDの生成を試みる
                data_manager = self.app_state.get("data_manager")
                if data_manager and hasattr(data_manager, "generate_next_prefixed_id"):
                    prefixed_id = data_manager.generate_next_prefixed_id(existing_ids)
                else:
                    # データマネージャーが利用できない場合はNoneを返す
                    prefixed_id = None
                    print("[WARNING] DataManagerが利用できないため、プレフィックス付きID生成をスキップします")

                if prefixed_id:
                    # プレフィックス付きIDが生成できた場合はそれを使用
                    new_id = prefixed_id
                    print(f"  Generated prefixed ID: {new_id}")
                else:
                    # プレフィックス付きIDが生成できなかった場合、フォールバックのロジックを実行
                    id_field_info = next((f for f in self.app_state["analysis_results"]["field_details"] if f["name"] == id_key), None)
                    id_type = "string" # デフォルトは文字列
                    if id_field_info and id_field_info["types"]:
                        id_type = id_field_info["types"][0][0] # 最も一般的な型を取得

                    if id_type == "int":
                        numeric_ids = [int(id_) for id_ in existing_ids if str(id_).isdigit()]
                        new_id = max(numeric_ids) + 1 if numeric_ids else 1
                    elif id_type == "string":
                         # UUID形式かどうかを簡易的にチェック
                         is_uuid_like = False
                         if existing_ids:
                             uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
                             if uuid_pattern.match(str(existing_ids[0])):
                                 is_uuid_like = True

                         if is_uuid_like:
                             new_id = str(uuid.uuid4())
                         else:
                             # UUID形式でなければ、単純な文字列IDを生成（例: "new_item_1"）
                             count = 1
                             while f"new_item_{count}" in existing_ids:
                                 count += 1
                             new_id = f"new_item_{count}"
                    else: # float や bool など、通常IDには使われない型の場合もUUIDを生成
                         new_id = str(uuid.uuid4())

                if new_id is not None:
                    # IDをバッファに設定
                    self.app_state["edit_buffer"][id_key] = new_id
                    print(f"  Auto-generated ID set in edit_buffer: {id_key} = {new_id}")

                print(f"  Initialized edit_buffer with {len(self.app_state['edit_buffer'])} default fields")
            else:
                print(f"  Using existing edit_buffer with {len(self.app_state['edit_buffer'])} fields")

            # フォームを構築
            # field_detailsを取得
            field_details = self.app_state["analysis_results"]["field_details"]
            field_details_map = {f["name"]: f for f in field_details}

            # edit_bufferからデータオブジェクトを再構築
            rebuilt_obj = {}

            # DataManagerのメソッドを使用
            data_manager = self.app_state.get("data_manager")
            if data_manager:
                for key_path, value in self.app_state["edit_buffer"].items():
                    try:
                        data_manager.set_value_by_path(rebuilt_obj, key_path, value)
                    except Exception as ex:
                        print(f"  [WARNING] Error setting path {key_path}: {ex}")
            else:
                # DataManagerが利用できない場合はエラー
                print(f"[ERROR] DataManager not available for rebuilding object")
                rebuilt_obj = {}

            # 新規作成フォームのタイトルとヘルプテキスト
            controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(t("form.new_node_title"), size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(t("form.new_node_description"), size=14),
                    ]),
                    margin=ft.margin.only(bottom=15)
                )
            )

            # 再構築したオブジェクトからフォームコントロールを生成
            form_controls = self.build_add_form_controls(rebuilt_obj, field_details_map)
            controls.extend(form_controls)

            # 追加・キャンセルボタン
            save_button = ft.ElevatedButton(
                t("form.add_item"),
                icon=ft.Icons.ADD,
                on_click=self.commit_new_node
            )

            cancel_button = ft.OutlinedButton(
                t("form.cancel"),
                icon=ft.Icons.CANCEL_OUTLINED,
                on_click=lambda e: self._toggle_add_mode(e)
            )

            controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(expand=True),  # スペーサー
                            save_button,
                            cancel_button
                        ],
                        alignment=ft.MainAxisAlignment.END,
                        spacing=10
                    ),
                    margin=ft.margin.only(top=15)
                )
            )

            # 構築したコントロールでフォームを更新
            detail_form_column.controls = controls
            detail_form_column.update()
            print(f"[OK] Add form updated with {len(form_controls)} controls")

        except Exception as ex:
            print(f"[ERROR] Error updating add form: {ex}")
            import traceback
            print(traceback.format_exc())
            controls.append(ft.Text(t("error.general").format(error=str(ex)), color=Colors.RED))
            detail_form_column.update()

    def _toggle_add_mode(self, e: ft.ControlEvent):
        """追加モードを切り替える"""
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager:
            ui_state_manager.set_add_mode(not self.app_state.get("add_mode", False))
        else:
            # フォールバック
            self.app_state["add_mode"] = not self.app_state.get("add_mode", False)
            # editバッファをクリア
            self.app_state["edit_buffer"].clear()
            # update_detail_formを呼び出す
            if self.app_state.get("add_mode"):
                self.update_add_form()
            else:
                self.update_detail_form(self.app_state.get("selected_node_id"))
    
    def toggle_add_mode(self, e: ft.ControlEvent):
        """
        追加モードを切り替える(パブリックAPI)
        
        Args:
            e: コントロールイベント
        """
        print("[UPDATE] Toggling add mode...")
        
        # 現在のモードを反転
        current_mode = self.app_state.get("add_mode", False)
        new_mode = not current_mode
        
        # UIStateManagerと連携
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager:
            ui_state_manager.set_add_mode(new_mode)
        else:
            # フォールバック
            self.app_state["add_mode"] = new_mode
        
        # UIコントロールの状態を更新
        if "add_data_button" in self.ui_controls and self.ui_controls["add_data_button"]:
            self.ui_controls["add_data_button"].selected = new_mode
            self.ui_controls["add_data_button"].update()
        
        # エディットバッファをクリア
        self.app_state["edit_buffer"] = {}
        
        # 現在選択されているノードを保存
        previously_selected = self.app_state.get("selected_node_id")
        
        if new_mode:  # 通常モード → 追加モード
            print("  Entering add mode")
            # 追加モード用のフォームを表示
            self.update_add_form()
            # スナックバー表示
            if self.page:
                self.page.snack_bar = ft.SnackBar(ft.Text(t("notification.add_mode_started")), open=True, duration=2000)
                self.page.update()
        else:  # 追加モード → 通常モード
            print("  Exiting add mode")
            # 以前選択していたノードのフォームを表示
            self.update_detail_form(previously_selected)
            # スナックバー表示
            if self.page:
                self.page.snack_bar = ft.SnackBar(ft.Text(t("notification.add_mode_ended")), open=True, duration=2000)
                self.page.update()
        
        print(f"[OK] Add mode toggled: {new_mode}")
    
    def build_add_form_controls(self, data_obj: dict, field_details_map: dict, key_prefix: str = "") -> list[ft.Control]:
        """
        新規追加フォーム用のフォームコントロールを再帰的に構築する

        Args:
            data_obj: フォームに表示するデータオブジェクト
            field_details_map: フィールド情報を含む辞書
            key_prefix: キーパスのプレフィックス

        Returns:
            構築されたコントロールのリスト
        """
        # UIManagerのtoggle_expansion関数を取得
        ui_manager = self.app_state.get("ui_manager")
        toggle_expansion_func = getattr(ui_manager, "toggle_expansion", None) if ui_manager else None
        if not toggle_expansion_func:
            # フォールバック: 簡単なダミー関数を定義
            def toggle_expansion_func(e):
                print("[WARNING] toggle_expansion機能が利用できません")
                pass

        controls = []
        id_key = self.app_state["analysis_results"]["heuristic_suggestions"].get("identifier", "id")
        keys_order = list(data_obj.keys())

        # IDキーを先頭に移動
        if id_key in keys_order:
            keys_order.remove(id_key)
            keys_order.insert(0, id_key)

        for key in keys_order:
            value = data_obj[key]
            current_key_path = f"{key_prefix}.{key}" if key_prefix else key
            is_id_field = (current_key_path == id_key)

            # フィールド情報の取得とタイプの判定
            field_info = field_details_map.get(current_key_path)
            field_type = "unknown"
            if field_info and field_info["types"]:
                field_type = field_info["types"][0][0]
            elif isinstance(value, bool): field_type = "bool"
            elif isinstance(value, int): field_type = "int"
            elif isinstance(value, float): field_type = "float"
            elif isinstance(value, list): field_type = "list"
            elif isinstance(value, dict): field_type = "dict"
            elif isinstance(value, str): field_type = "string"

            # 各フィールドの右側に削除ボタンを追加
            field_container = ft.Container(
                content=ft.Row(
                    [
                        # フィールドのコントロール（後で追加）
                        ft.Container(expand=True),  # プレースホルダー
                        # 削除ボタン
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            icon_size=16,
                            tooltip=t("tooltip.delete_field").format(field=key),
                            data={"key_path": current_key_path, "key": key},
                            on_click=lambda e: self.confirm_delete_field(e, e.control.data["key_path"], e.control.data["key"])
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.START
                ),
                padding=ft.padding.only(bottom=5)
            )

            control_to_add = None

            # 辞書型の場合は再帰的に処理
            if field_type == "dict":
                nested_controls = self.build_add_form_controls(value, field_details_map, current_key_path)
                if nested_controls:
                    header_content = ft.Row(
                        [
                            ft.Icon(ft.Icons.SETTINGS_INPUT_COMPONENT),
                            ft.Text(key, weight=ft.FontWeight.W_500)
                        ],
                    )
                    clickable_header = ft.Container(
                        content=header_content,
                        on_click=toggle_expansion_func,
                        ink=True,
                        border_radius=ft.border_radius.all(4),
                    )
                    control_to_add = ft.ExpansionPanelList(
                        expand_icon_color=Colors.with_opacity(0.5, Colors.ON_SURFACE),
                        elevation=0,
                        divider_color=Colors.with_opacity(0.3, Colors.OUTLINE),
                        controls=[
                            ft.ExpansionPanel(
                                header=clickable_header,
                                content=ft.Container(
                                    content=ft.Column(nested_controls, spacing=8),
                                    padding=ft.padding.only(left=10, top=5, bottom=5)
                                ),
                                bgcolor=Colors.with_opacity(0.03, Colors.ON_SURFACE_VARIANT),
                                expanded=True,  # デフォルトで展開
                            )
                        ],
                        data=current_key_path
                    )
                else:
                    text_area = ft.TextField(
                        label=key,
                        value=str(value),
                        multiline=True,
                        min_lines=3,
                        max_lines=10,
                        dense=True,
                        data={"path": current_key_path, "type": "dict"},
                        on_change=self.on_form_field_change,
                        hint_text=t("form.dict_json_hint")
                    )
                    control_to_add = ft.Container(
                        content=ft.Column([
                            ft.Text(t("form.dict_type"), size=12, color=Colors.ON_SURFACE_VARIANT),
                            text_area
                        ]),
                        data={"path": current_key_path, "type": "dict"}
                    )

            # リスト型の場合
            elif field_type.startswith("list"):
                if isinstance(value, list):
                    list_items_controls = []
                    for index, item in enumerate(value):
                        item_prefix = f"{current_key_path}[{index}]"
                        if isinstance(item, dict):
                            dict_header = ft.Row([
                                ft.Text(f"[{index}]", weight=ft.FontWeight.W_500),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_size=16,
                                    tooltip=t("form.delete_item_tooltip").format(index=index),
                                    data={"key_path": current_key_path, "index": index},
                                    on_click=lambda e: self.delete_list_item_in_add_mode(e, e.control.data["key_path"], e.control.data["index"])
                                )
                            ])
                            list_items_controls.append(dict_header)
                            nested_item_controls = self.build_add_form_controls(item, field_details_map, item_prefix)
                            list_items_controls.append(
                                ft.Container(
                                    content=ft.Column(nested_item_controls, spacing=5),
                                    padding=ft.padding.only(left=15),
                                    border=ft.border.all(1, Colors.OUTLINE_VARIANT),
                                    border_radius=5,
                                    margin=ft.margin.only(bottom=10)
                                )
                            )
                        else:
                            item_row = ft.Row([
                                ft.Text(f"[{index}]"),
                                ft.TextField(
                                    value=str(item),
                                    expand=True,
                                    dense=True,
                                    data={"path": item_prefix, "type": "list_item"},
                                    on_change=self.on_form_field_change
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_size=16,
                                    tooltip=t("form.delete_item_tooltip").format(index=index),
                                    data={"key_path": current_key_path, "index": index},
                                    on_click=lambda e: self.delete_list_item_in_add_mode(e, e.control.data["key_path"], e.control.data["index"])
                                )
                            ])
                            list_items_controls.append(item_row)

                    add_item_button = ft.TextButton(
                        t("form.add_item_button"),
                        icon=ft.Icons.ADD,
                        on_click=lambda e, kp=current_key_path: self.add_list_item_in_add_mode(e, kp),
                        data=current_key_path
                    )

                    header_content = ft.Row(
                        [
                            ft.Icon(ft.Icons.FORMAT_LIST_NUMBERED),
                            ft.Text(f"{key} [{len(value)} items]", weight=ft.FontWeight.W_500)
                        ],
                    )
                    clickable_header = ft.Container(
                        content=header_content,
                        on_click=toggle_expansion_func,
                        ink=True,
                        border_radius=ft.border_radius.all(4),
                    )
                    control_to_add = ft.ExpansionPanelList(
                        expand_icon_color=Colors.with_opacity(0.5, Colors.ON_SURFACE),
                        elevation=0,
                        divider_color=Colors.with_opacity(0.3, Colors.OUTLINE),
                        controls=[
                            ft.ExpansionPanel(
                                header=clickable_header,
                                content=ft.Container(
                                    content=ft.Column(
                                        list_items_controls + [add_item_button],
                                        spacing=5
                                    ),
                                    padding=ft.padding.only(left=10, top=5, bottom=5)
                                ),
                                bgcolor=Colors.with_opacity(0.03, Colors.ON_SURFACE_VARIANT),
                                expanded=True,  # デフォルトで展開
                            )
                        ],
                        data=current_key_path
                    )
                else:
                    text_area = ft.TextField(
                        label=key,
                        value=str(value),
                        multiline=True,
                        min_lines=3,
                        max_lines=10,
                        dense=True,
                        data=current_key_path,
                        on_change=self.on_form_field_change,
                        hint_text=t("form.list_json_hint")
                    )
                    control_to_add = ft.Container(
                        content=ft.Column([
                            ft.Text(t("form.list_type"), size=12, color=Colors.ON_SURFACE_VARIANT),
                            text_area
                        ]),
                        data=current_key_path
                    )

            # ブール型の場合
            elif field_type == "bool":
                bool_control = ft.RadioGroup(
                    content=ft.Row(
                        [
                            ft.Radio(value="true", label="True"),
                            ft.Radio(value="false", label="False"),
                        ]
                    ),
                    value="true" if bool(value) else "false",
                    data={"path": current_key_path, "type": "bool"},
                    on_change=self.on_form_field_change
                )

                field_container.content.controls[0] = ft.Column([
                    ft.Text(key, size=14, weight=ft.FontWeight.W_500),
                    bool_control
                ])
                control_to_add = field_container

            # 数値型の場合
            elif field_type == "int" or field_type == "float":
                number_field = ft.TextField(
                    label=key,
                    value=str(value),
                    keyboard_type=ft.KeyboardType.NUMBER,
                    data={"path": current_key_path, "is_id": is_id_field},
                    dense=True,
                    hint_text=t("form.id_field_hint") if is_id_field else None,
                    on_change=self.on_id_field_change if is_id_field else self.on_form_field_change,
                    expand=True
                )

                field_container.content.controls[0] = number_field
                control_to_add = field_container

            # その他の型（文字列など）の場合
            else:
                text_field = ft.TextField(
                    label=key,
                    value=str(value) if value is not None else "",
                    multiline=isinstance(value, str) and (len(value) > 60 or '\n' in value),
                    min_lines=1,
                    max_lines=5 if isinstance(value, str) and (len(value) > 60 or '\n' in value) else 1,
                    dense=True,
                    data={"path": current_key_path, "is_id": is_id_field},
                    hint_text=t("form.id_field_hint") if is_id_field else None,
                    on_change=self.on_id_field_change if is_id_field else self.on_form_field_change,
                    expand=True
                )

                field_container.content.controls[0] = text_field
                control_to_add = field_container

            if control_to_add:
                controls.append(control_to_add)

        return controls
    
    # ----- フォームイベント処理メソッド -----
    
    def on_form_field_change(self, e: ft.ControlEvent):
        """
        フォームのフィールド値が変更されたときに呼び出される

        Args:
            e: コントロールイベント
        """
        control = e.control
        field_data = control.data
        new_value = control.value

        # データ形式の正規化と型情報の取得
        key_path = None
        field_type = None
        if isinstance(field_data, dict):
            key_path = field_data.get("path")
            field_type = field_data.get("type")
        elif isinstance(field_data, str): # 古い形式へのフォールバック
            key_path = field_data

        if key_path:

            # DataManagerの型変換メソッドを使用
            data_manager = self.app_state.get("data_manager")
            if data_manager and hasattr(data_manager, "convert_value_based_on_type"):
                converted_value = data_manager.convert_value_based_on_type(new_value, field_type, key_path)
            else:
                # DataManagerが利用できない場合はそのまま使用
                print(f"[WARNING] DataManager not available for convert_value_based_on_type, using raw value")
                converted_value = new_value

            # edit_buffer に記録
            self.app_state["edit_buffer"][key_path] = converted_value
            
            # フィールド入力順序を記録
            self._input_counter += 1
            self._key_input_order[key_path] = self._input_counter
            
            # 自動的に親パスも記録
            parts = key_path.split('.')
            if len(parts) > 1:
                parent = parts[0]
                if parent not in self._key_input_order:
                    self._input_counter += 1
                    self._key_input_order[parent] = self._input_counter
                    
            # 配列親パスも記録
            array_match = re.match(r'^(.+)\[\d+\]$', key_path)
            if array_match:
                array_parent = array_match.group(1)
                if array_parent not in self._key_input_order:
                    self._input_counter += 1
                    self._key_input_order[array_parent] = self._input_counter
            
            if not self.app_state.get("is_dirty"):
                self.app_state["is_dirty"] = True

                # UIStateManagerと状態同期
                ui_state_manager = self.app_state.get("ui_state_manager")
                if ui_state_manager:
                    ui_state_manager.set_edit_mode(True)

                self.update_detail_buttons_state() # ボタンの状態のみ更新
                print("[UPDATE] Form state changed to dirty")
        else:
            print(f"[WARNING] Field change event without valid key_path: Control={control}, Data={field_data}")
            if hasattr(control, 'label'):
                print(f"[WARNING] Label: {control.label}")

    def on_id_field_change(self, e: ft.ControlEvent):
        """
        IDフィールドが変更されたときの処理(入力中のリアルタイム処理)

        Args:
            e: コントロールイベント
        """
        # 変更を edit_buffer に記録するのみ。実際のデータ更新は save_changes で行う。
        control = e.control
        field_data = control.data
        new_value_str = control.value # TextFieldからは文字列で取得

        key_path = None
        is_id_field = False
        if isinstance(field_data, dict):
            key_path = field_data.get("path")
            is_id_field = field_data.get("is_id", False)

        # IDフィールドでなければ通常の変更処理
        if not is_id_field or not key_path:
            self.on_form_field_change(e)
            return

        current_node_id = self.app_state.get("selected_node_id")
        id_key = self.app_state.get("id_key")

        # 状態チェック
        if not current_node_id or not id_key or key_path != id_key:
            print(f"[WARNING] ID field change detected but state is inconsistent: path={key_path}, current_id={current_node_id}, id_key={id_key}")
            self.on_form_field_change(e) # 通常の変更として処理
            return

        node_data = self.app_state["data_map"].get(current_node_id)
        if node_data is None:
            print(f"[WARNING] Cannot get original node data for ID {current_node_id}")
            self.on_form_field_change(e) # 通常の変更として処理
            return

        # 元のID値と型を取得
        data_manager = self.app_state.get("data_manager")
        if data_manager:
            original_value = data_manager.get_value_by_path(node_data, id_key)
        else:
            print("[ERROR] DataManager not available for get_value_by_path")
            original_value = None

        original_type_name = type(original_value).__name__ if original_value is not None else "string" # デフォルトはstring

        # 新しい値の型変換を試みる
        try:
            # DataManagerの型変換メソッドを使用
            if data_manager and hasattr(data_manager, "convert_value_based_on_type"):
                new_value = data_manager.convert_value_based_on_type(new_value_str, original_type_name, key_path)
            else:
                # DataManagerが利用できない場合はそのまま使用
                print(f"[WARNING] DataManager not available for convert_value_based_on_type, using raw value")
                new_value = new_value_str

            new_id_str = str(new_value)

            # IDの重複チェック（リアルタイム） - オプションでエラー表示
            if new_id_str != current_node_id and new_id_str in self.app_state["data_map"]:
                control.error_text = t("error.id_already_used")
            else:
                control.error_text = None # エラー解除
            control.update()

        except ValueError:
            # 変換エラー時はバッファには文字列のまま入れ、エラー表示
            print(f"[WARNING] Invalid ID format entered: '{new_value_str}' for type {original_type_name}")
            new_value = new_value_str # バッファには元の文字列を入れる
            control.error_text = t("error.invalid_format").format(type=original_type_name)
            control.update()

        # edit_buffer に変更を記録
        self.app_state["edit_buffer"][key_path] = new_value
        if not self.app_state.get("is_dirty"):
            self.app_state["is_dirty"] = True

            # UIStateManagerと状態同期
            ui_state_manager = self.app_state.get("ui_state_manager")
            if ui_state_manager:
                ui_state_manager.set_edit_mode(True)

            self.update_detail_buttons_state()
            print("[UPDATE] Form state changed to dirty due to ID change")

    def save_changes(self, e: ft.ControlEvent):
        """
        詳細フォームの変更を edit_buffer に基づいて data_map と raw_data に適用する

        Args:
            e: コントロールイベント
        """
        print("[SAVE] Saving changes...")
        page = e.page # スナックバー表示用に取得

        if not self.app_state.get("is_dirty") or not self.app_state["edit_buffer"]:
            print("[INFO] No changes to save.")
            page.snack_bar = ft.SnackBar(ft.Text(t("error.no_changes_to_save")), open=True, duration=2000)
            page.update()
            return

        current_node_id = self.app_state.get("selected_node_id")
        if not current_node_id:
            print("[ERROR] Error: No node selected.")
            page.show_snack_bar(ft.SnackBar(ft.Text(t("error.no_node_selected")), open=True))
            page.update()
            return

        node_data = self.app_state["data_map"].get(current_node_id)
        if node_data is None:
            print(f"[ERROR] Error: Node data not found for ID: {current_node_id}")
            page.show_snack_bar(ft.SnackBar(ft.Text(t("error.node_not_found").format(id=current_node_id)), open=True))
            page.update()
            return

        # raw_data 内の対応するオブジェクトへの参照を取得
        id_key = self.app_state.get("id_key")
        raw_obj_ref = None
        if id_key and self.app_state.get("raw_data"):
            # raw_data がリストであることを確認
            if isinstance(self.app_state["raw_data"], list):
                raw_obj_ref = next((item for item in self.app_state["raw_data"] if isinstance(item, dict) and str(item.get(id_key)) == current_node_id), None)
            elif isinstance(self.app_state["raw_data"], dict) and str(self.app_state["raw_data"].get(id_key)) == current_node_id:
                # ルートが辞書の場合（非推奨だが考慮）
                raw_obj_ref = self.app_state["raw_data"]

            if raw_obj_ref is None:
                print(f"[WARNING] Warning: Corresponding object not found in raw_data for ID: {current_node_id}")

        # ID変更の処理
        new_id = None
        original_node_id = current_node_id # ID変更があった場合に古いIDを保持
        if id_key and id_key in self.app_state["edit_buffer"]:
            new_id_value = self.app_state["edit_buffer"][id_key]
            new_id_str = str(new_id_value)
            if new_id_str != current_node_id:
                print(f"[UPDATE] ID change requested: '{current_node_id}' -> '{new_id_str}'")
                if new_id_str in self.app_state["data_map"]:
                    print(f"[ERROR] Error: New ID '{new_id_str}' already exists.")
                    # 代替通知システムを使用
                    try:
                        from notification_system import NotificationSystem
                        notification_system = NotificationSystem(page)
                        notification_system.show_error(t("error.id_already_used").format(id=new_id_str))
                    except Exception as notif_ex:
                        # フォールバック: 従来のSnackBar
                        page.snack_bar = ft.SnackBar(ft.Text(t("error.id_already_used").format(id=new_id_str)), open=True, duration=3000)
                        page.snack_bar.open = True
                        page.update()
                    # ID変更をバッファから削除して処理を続行
                    del self.app_state["edit_buffer"][id_key]
                else:
                    new_id = new_id_str # ID変更を確定

        # edit_buffer の内容を data_map (node_data) と raw_data (raw_obj_ref) に適用
        print("Applying changes from edit_buffer:")
        update_errors = {}

        # DataManagerのメソッドを使用
        data_manager = self.app_state.get("data_manager")

        # edit_buffer のキーをソート
        # 改良版: 階層レベルを考慮しつつ入力順序を優先するソート基準
        # 1. ルートレベルのフィールドは入力順序のみでソート
        # 2. 子フィールドは親の入力順序を継承しつつ、部分的に階層深さを考慮
        
        # まず、キーを階層ごとにグループ化
        root_keys = [k for k in self.app_state["edit_buffer"].keys() if '.' not in k and '[' not in k]
        nested_keys = [k for k in self.app_state["edit_buffer"].keys() if '.' in k or '[' in k]
        
        # ルートキーは入力順序だけでソート
        sorted_root_keys = sorted(root_keys, key=lambda x: self._get_key_input_order(x))
        
        # ネストされたキーは親の入力順に従ってソートしつつ、同じ親を持つキー同士では階層の浅いものを優先
        sorted_nested_keys = sorted(nested_keys, 
                          key=lambda x: (self._get_parent_order(x), x.count('.'), self._get_key_input_order(x)))
        
        # 両方を組み合わせる
        sorted_keys = sorted_root_keys + sorted_nested_keys

        for key_path in sorted_keys:
            value_to_set = self.app_state["edit_buffer"][key_path]
            # ID自体の更新は data_map キー変更後に行うためスキップ（new_id が設定されている場合）
            if key_path == id_key and new_id is not None:
                print(f"  Skipping data_map value update for ID key '{key_path}' for now.")
                # raw_data の ID はここで更新しておく
                if raw_obj_ref is not None:
                    try:
                        if data_manager:
                            data_manager.set_value_by_path(raw_obj_ref, key_path, value_to_set)
                            print(f"    [OK] Successfully set raw_data value for ID key '{key_path}'")
                    except Exception as err:
                        print(f"    [ERROR] Error setting raw_data value for ID key '{key_path}': {err}")
                        update_errors[f"{key_path} (raw_data)"] = str(err)
                continue

            print(f"  Applying: {key_path} = {repr(value_to_set)} (Type: {type(value_to_set)})")
            try:
                # data_map (node_data) を更新
                if data_manager:
                    data_manager.set_value_by_path(node_data, key_path, value_to_set)
                else:
                    
                    set_value_by_path(node_data, key_path, value_to_set)

                print(f"    [OK] Successfully set data_map value for {key_path}")

                # raw_data も更新 (参照が存在すれば)
                if raw_obj_ref is not None:
                    if data_manager:
                        data_manager.set_value_by_path(raw_obj_ref, key_path, value_to_set)
                    else:
                        
                        set_value_by_path(raw_obj_ref, key_path, value_to_set)

                    print(f"    [OK] Successfully set raw_data value for {key_path}")

            except (KeyError, IndexError, TypeError, ValueError) as err:
                print(f"    [ERROR] Error setting value for {key_path}: {err}")
                update_errors[key_path] = str(err)

        # ID変更があった場合の data_map キー更新処理
        if new_id is not None:
            print(f"  Updating data_map key from '{original_node_id}' to '{new_id}'")
            # node_data の ID キーの値を最終確認・設定
            try:
                final_id_value = self.app_state["edit_buffer"].get(id_key, node_data.get(id_key)) # バッファの値優先
                if data_manager:
                    data_manager.set_value_by_path(node_data, id_key, final_id_value)
                else:
                    
                    set_value_by_path(node_data, id_key, final_id_value)
            except Exception as err:
                print(f"    [ERROR] Error setting final ID value in node_data for '{new_id}': {err}")
                update_errors[f"{id_key} (final)"] = str(err)

            self.app_state["data_map"][new_id] = node_data # 新しいIDでデータを登録
            if original_node_id in self.app_state["data_map"]:
                del self.app_state["data_map"][original_node_id] # 古いIDのデータを削除
            self.app_state["selected_node_id"] = new_id # 選択中のノードIDも更新
            current_node_id = new_id # 後続処理のために更新
            print(f"    [OK] data_map key updated.")

        # 変更フラグとバッファをクリア
        self.app_state["edit_buffer"].clear()
        self.app_state["is_dirty"] = False

        # UIStateManagerと状態同期
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager:
            ui_state_manager.set_edit_mode(False)

        # ボタンの状態を更新
        self.update_detail_buttons_state() # is_dirty=False に基づいて更新

        # UI更新
        try:
            # UIマネージャーを取得
            ui_manager = self.app_state.get("ui_manager")

            if "tree_view" in self.ui_controls and self.ui_controls["tree_view"] is not None:
                # ツリービューのノードスタイルを更新 (更新後の current_node_id で)
                if ui_manager:
                    ui_manager.update_node_style_recursive(
                        self.ui_controls["tree_view"].controls,
                        current_node_id,
                        True,
                        force_label_update=True
                    )

            # ツリービュー全体を更新（左ペイン） - ID変更があった場合、表示が変わる
            if ui_manager:
                ui_manager.update_tree_view()

            # 詳細フォームを再表示（右ペイン） - 保存後は最新のデータで再描画 (更新後の current_node_id で)
            self.update_detail_form(current_node_id)

            # 検索インデックスを更新（検索機能が利用可能な場合）
            search_manager = self.app_state.get("search_manager")
            if search_manager:
                # 現在のノードIDの検索インデックスを更新
                search_manager.update_search_index(current_node_id)
                print(f"[OK] ノードID '{current_node_id}' の検索インデックスを更新しました")
        except Exception as ex:
            print(f"[WARNING] Warning: Error updating UI after save: {ex}")
            import traceback
            print(traceback.format_exc())

        # 結果を通知
        if not update_errors:
            print("[OK] Changes saved successfully.")
            # 代替通知システムを使用
            try:
                from notification_system import NotificationSystem
                notification_system = NotificationSystem(page)
                notification_system.show_success(t("notification.changes_saved"))
            except Exception as notif_ex:
                # フォールバック: 従来のSnackBar
                page.snack_bar = ft.SnackBar(ft.Text(t("notification.changes_saved")), open=True, duration=2000)
                page.snack_bar.open = True
                page.update()
        else:
            print(f"[WARNING] Changes saved with {len(update_errors)} errors.")
            error_keys = ", ".join(update_errors.keys())
            # 代替通知システムを使用
            try:
                from notification_system import NotificationSystem
                notification_system = NotificationSystem(page)
                notification_system.show_warning(t("notification.partial_save_warning").format(errors=error_keys))
            except Exception as notif_ex:
                # フォールバック: 従来のSnackBar
                page.snack_bar = ft.SnackBar(ft.Text(t("notification.partial_save_warning").format(errors=error_keys)), open=True, duration=4000)
                page.snack_bar.open = True
                page.update()

        page.update()

    def apply_edit_buffer_to_data(self) -> tuple[bool, dict]:
        """
        edit_bufferの内容をdata_mapとraw_dataに適用する（UIは更新しない）
        
        Returns:
            tuple[bool, dict]: (成功フラグ, エラー辞書)
        """
        print("[UPDATE] Applying edit_buffer to data...")
        
        if not self.app_state.get("edit_buffer"):
            return True, {}
            
        current_node_id = self.app_state.get("selected_node_id")
        if not current_node_id:
            print("[ERROR] Error: No node selected.")
            return False, {"general": "ノードが選択されていません"}
            
        node_data = self.app_state["data_map"].get(current_node_id)
        if node_data is None:
            print(f"[ERROR] Error: Node data not found for ID: {current_node_id}")
            return False, {"general": t("error.node_not_found_detail").format(id=current_node_id)}
            
        # raw_data 内の対応するオブジェクトへの参照を取得
        id_key = self.app_state.get("id_key")
        raw_obj_ref = None
        if id_key and self.app_state.get("raw_data"):
            if isinstance(self.app_state["raw_data"], list):
                raw_obj_ref = next((item for item in self.app_state["raw_data"] if isinstance(item, dict) and str(item.get(id_key)) == current_node_id), None)
            elif isinstance(self.app_state["raw_data"], dict) and str(self.app_state["raw_data"].get(id_key)) == current_node_id:
                raw_obj_ref = self.app_state["raw_data"]
                
            if raw_obj_ref is None:
                print(f"[WARNING] Warning: Corresponding object not found in raw_data for ID: {current_node_id}")
                
        # ID変更の処理
        new_id = None
        original_node_id = current_node_id
        if id_key and id_key in self.app_state["edit_buffer"]:
            new_id_value = self.app_state["edit_buffer"][id_key]
            new_id_str = str(new_id_value)
            if new_id_str != current_node_id:
                print(f"[UPDATE] ID change requested: '{current_node_id}' -> '{new_id_str}'")
                if new_id_str in self.app_state["data_map"]:
                    print(f"[ERROR] Error: New ID '{new_id_str}' already exists.")
                    return False, {id_key: t("error.id_already_exists").format(id=new_id_str)}
                else:
                    new_id = new_id_str
                    
        # edit_buffer の内容を適用
        print("Applying changes from edit_buffer:")
        update_errors = {}
        
        # DataManagerのメソッドを使用
        data_manager = self.app_state.get("data_manager")
        
        # キーをソート
        root_keys = [k for k in self.app_state["edit_buffer"].keys() if '.' not in k and '[' not in k]
        nested_keys = [k for k in self.app_state["edit_buffer"].keys() if '.' in k or '[' in k]
        
        sorted_root_keys = sorted(root_keys, key=lambda x: self._get_key_input_order(x))
        sorted_nested_keys = sorted(nested_keys, 
                          key=lambda x: (self._get_parent_order(x), x.count('.'), self._get_key_input_order(x)))
        
        sorted_keys = sorted_root_keys + sorted_nested_keys
        
        for key_path in sorted_keys:
            value_to_set = self.app_state["edit_buffer"][key_path]
            # ID自体の更新は data_map キー変更後に行うためスキップ
            if key_path == id_key and new_id is not None:
                print(f"  Skipping data_map value update for ID key '{key_path}' for now.")
                if raw_obj_ref is not None:
                    try:
                        if data_manager:
                            data_manager.set_value_by_path(raw_obj_ref, key_path, value_to_set)
                            print(f"    [OK] Successfully set raw_data value for ID key '{key_path}'")
                    except Exception as err:
                        print(f"    [ERROR] Error setting raw_data value for ID key '{key_path}': {err}")
                        update_errors[f"{key_path} (raw_data)"] = str(err)
                continue
                
            print(f"  Applying: {key_path} = {repr(value_to_set)} (Type: {type(value_to_set)})")
            try:
                # data_map (node_data) を更新
                if data_manager:
                    data_manager.set_value_by_path(node_data, key_path, value_to_set)
                else:
                    set_value_by_path(node_data, key_path, value_to_set)
                    
                print(f"    [OK] Successfully set data_map value for {key_path}")
                
                # raw_data も更新
                if raw_obj_ref is not None:
                    if data_manager:
                        data_manager.set_value_by_path(raw_obj_ref, key_path, value_to_set)
                    else:
                        set_value_by_path(raw_obj_ref, key_path, value_to_set)
                        
                    print(f"    [OK] Successfully set raw_data value for {key_path}")
                    
            except (KeyError, IndexError, TypeError, ValueError) as err:
                print(f"    [ERROR] Error setting value for {key_path}: {err}")
                update_errors[key_path] = str(err)
                
        # ID変更があった場合の data_map キー更新処理
        if new_id is not None:
            print(f"  Updating data_map key from '{original_node_id}' to '{new_id}'")
            try:
                final_id_value = self.app_state["edit_buffer"].get(id_key, node_data.get(id_key))
                if data_manager:
                    data_manager.set_value_by_path(node_data, id_key, final_id_value)
                else:
                    set_value_by_path(node_data, id_key, final_id_value)
            except Exception as err:
                print(f"    [ERROR] Error setting final ID value in node_data for '{new_id}': {err}")
                update_errors[f"{id_key} (final)"] = str(err)
                
            self.app_state["data_map"][new_id] = node_data
            if original_node_id in self.app_state["data_map"]:
                del self.app_state["data_map"][original_node_id]
            self.app_state["selected_node_id"] = new_id
            print(f"    [OK] data_map key updated.")
            
        # 変更フラグとバッファをクリア
        self.app_state["edit_buffer"].clear()
        self.app_state["is_dirty"] = False
        
        # UIStateManagerと状態同期
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager:
            ui_state_manager.set_edit_mode(False)
            
        if not update_errors:
            print("[OK] Edit buffer applied successfully.")
            return True, {}
        else:
            print(f"[WARNING] Edit buffer applied with {len(update_errors)} errors.")
            return True, update_errors  # 部分的成功

    def cancel_changes(self, e: ft.ControlEvent):
        """
        詳細フォームの変更をキャンセルする

        Args:
            e: コントロールイベント
        """
        print("[CANCEL] Canceling changes...")
        if not self.app_state.get("is_dirty"):
            print("[INFO] No changes to cancel.")
            return

        self.app_state["edit_buffer"].clear()
        self.app_state["is_dirty"] = False

        # UIStateManagerと状態同期
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager:
            ui_state_manager.set_edit_mode(False)

        selected_node_id = self.app_state.get("selected_node_id")
        if selected_node_id:
            # フォームを元のデータ（変更前）で再描画
            self.update_detail_form(selected_node_id)
            print(f"[CANCEL] Changes canceled. Restored form for node {selected_node_id}.")
        else:
            self.update_detail_form(None) # ノードが選択されていない場合はフォームをクリア
            print("[CANCEL] Changes canceled. No node selected, cleared form.")

        # 通知表示
        page = e.page
        try:
            from notification_system import NotificationSystem
            notification_system = NotificationSystem(page)
            notification_system.show_info(t("notification.changes_cancelled"))
        except Exception as notif_ex:
            # フォールバック: 従来のSnackBar
            page.snack_bar = ft.SnackBar(ft.Text(t("notification.changes_cancelled")), open=True, duration=2000)
            page.snack_bar.open = True
            page.update()
    
    # ----- リスト項目操作メソッド -----
    
    def add_list_item(self, e: ft.ControlEvent, key_path: str):
        """
        リストに新しい項目を追加して edit_buffer に記録する

        Args:
            e: コントロールイベント
            key_path: 対象リストのキーパス
        """
        print(f"[ADD] Request to add list item to: {key_path}")
        page = e.page
        current_node_id = self.app_state.get("selected_node_id")
        if not current_node_id:
            print("[WARNING] No node selected.")
            return

        node_data = self.app_state["data_map"].get(current_node_id)
        if node_data is None:
            print(f"[ERROR] Error: Node data not found for ID {current_node_id}")
            return

        try:
            # 現在のリストの値を取得 (edit_buffer にあればそちらを優先)
            target_list = self.app_state["edit_buffer"].get(key_path)

            # DataManagerのメソッドを使用
            data_manager = self.app_state.get("data_manager")
            if target_list is None:
                if data_manager and hasattr(data_manager, "get_value_by_path"):
                    target_list = data_manager.get_value_by_path(node_data, key_path)
                else:
                    # フォールバック
                    
                    target_list = get_value_by_path(node_data, key_path)
            else:
                print(f"  Using list from edit_buffer for {key_path}")

            # 取得したものがリストであることを確認
            if not isinstance(target_list, list):
                print(f"[ERROR] Error adding list item: Target is not a list at {key_path}.")
                page.show_snack_bar(ft.SnackBar(ft.Text(t("error.not_list").format(path=key_path)), open=True))
                page.update()
                return

            # 新しいアイテムの値を決定
            # リストに要素があるかチェックして最後の要素の構造をコピー
            if len(target_list) > 0:
                last_item = target_list[-1]
                # 辞書型の場合は構造をコピー、それ以外はデフォルト値を使用
                if isinstance(last_item, dict):
                    # 深いコピーを作成して値をリセット
                    new_item = {}
                    for key, value in last_item.items():
                        if isinstance(value, (dict, list)):
                            # 複雑な構造はディープコピー
                            import copy
                            new_item[key] = copy.deepcopy(value)
                            # オプション: 内部のリストは空にしても良い
                            if isinstance(new_item[key], list):
                                new_item[key] = []
                        elif isinstance(value, str):
                            # 文字列は空にリセット
                            new_item[key] = ""
                        elif isinstance(value, (int, float)):
                            # 数値は0にリセット
                            new_item[key] = 0 if isinstance(value, int) else 0.0
                        elif isinstance(value, bool):
                            # ブール値はFalseにリセット
                            new_item[key] = False
                        else:
                            # その他の型はNoneに
                            new_item[key] = None
                    print(f"  Created new dict item by copying structure from last item: {new_item}")
                else:
                    # 辞書型でない場合は単純なタイプなのでデフォルト値を取得
                    if data_manager and hasattr(data_manager, "get_default_value_for_list_item"):
                        new_item = data_manager.get_default_value_for_list_item(target_list)
                    else:
                        # フォールバック
                        
                        new_item = get_default_value_for_list_item(target_list)
                    print(f"  Using default value for new item: {new_item}")
            else:
                # リストが空の場合はデフォルト値
                if data_manager and hasattr(data_manager, "get_default_value_for_list_item"):
                    new_item = data_manager.get_default_value_for_list_item(target_list)
                else:
                    # フォールバック
                    
                    new_item = get_default_value_for_list_item(target_list)
                print(f"  List was empty, using default value for new item: {new_item}")

            new_index = len(target_list)

            # 新しいリストを作成して項目を追加
            # target_list は参照の場合があるのでコピーしてから追加
            new_list = list(target_list)
            new_list.append(new_item)

            # edit_buffer にリスト全体の変更として記録
            self.app_state["edit_buffer"][key_path] = new_list
            print(f"  Buffered list change for {key_path}: {len(new_list)} items. Added: {repr(new_item)}")

            # 一時的にフォームの状態を保存
            was_dirty = self.app_state.get("is_dirty", False)
            if not was_dirty:
                self.app_state["is_dirty"] = True

                # UIStateManagerと状態同期
                ui_state_manager = self.app_state.get("ui_state_manager")
                if ui_state_manager:
                    ui_state_manager.set_edit_mode(True)

            # UIを更新（フォーム全体を再描画）
            self.update_detail_form(current_node_id)

            # ボタンの状態を確実に更新
            self.update_detail_buttons_state()

            # 検索インデックスを即時更新（項目追加後にすぐ検索できるようにするため）
            search_manager = self.app_state.get("search_manager")
            if search_manager:
                # バッファに変更を適用した一時的なノードデータを作成し、それを使って検索インデックスを更新
                import copy
                temp_node_data = copy.deepcopy(node_data)
                # 変更を反映
                if data_manager and hasattr(data_manager, "set_value_by_path"):
                    data_manager.set_value_by_path(temp_node_data, key_path, new_list)
                else:
                    # フォールバック
                    
                    set_value_by_path(temp_node_data, key_path, new_list)

                # 一時的に更新
                self.app_state["data_map"][current_node_id] = temp_node_data
                search_manager.update_search_index(current_node_id)
                # 元に戻す
                self.app_state["data_map"][current_node_id] = node_data
                print(f"  [OK] Updated search index for node {current_node_id} after list item addition")

            print(f"[OK] Item addition buffered for {key_path}. Form updated.")
            # 代替通知システムを使用
            try:
                from notification_system import NotificationSystem
                notification_system = NotificationSystem(page)
                notification_system.show_success(t("notification.item_added_success").format(path=key_path))
            except Exception as notif_ex:
                # フォールバック: 従来のSnackBar
                page.snack_bar = ft.SnackBar(ft.Text(t("notification.item_added_success").format(path=key_path)), open=True, duration=2500)
                page.snack_bar.open = True
                page.update()

        except Exception as err:
            print(f"[ERROR] Error processing list item addition: {err}")
            import traceback
            print(traceback.format_exc())
            # 代替通知システムを使用
            try:
                from notification_system import NotificationSystem
                notification_system = NotificationSystem(page)
                notification_system.show_error(t("error.list_operation").format(operation="追加", error=err))
            except Exception as notif_ex:
                # フォールバック: 従来のSnackBar
                page.snack_bar = ft.SnackBar(ft.Text(t("error.list_operation").format(operation="追加", error=err)), open=True)
                page.snack_bar.open = True
                page.update()

    def delete_list_item(self, e: ft.ControlEvent, key_path: str, index: int):
        """
        リストから項目を削除して edit_buffer に記録する

        Args:
            e: コントロールイベント
            key_path: 対象リストのキーパス
            index: 削除する項目のインデックス
        """
        print(f"[DELETE] Request to delete list item: {key_path}[{index}]")
        page = e.page
        current_node_id = self.app_state.get("selected_node_id")
        if not current_node_id:
            print("[WARNING] No node selected.")
            return

        node_data = self.app_state["data_map"].get(current_node_id)
        if node_data is None:
            print(f"[ERROR] Error: Node data not found for ID {current_node_id}")
            return

        try:
            # 現在のリストの値を取得 (edit_buffer にあればそちらを優先)
            target_list = self.app_state["edit_buffer"].get(key_path)

            data_manager = self.app_state.get("data_manager")
            if target_list is None:
                if data_manager and hasattr(data_manager, "get_value_by_path"):
                    target_list = data_manager.get_value_by_path(node_data, key_path)
                else:
                    # フォールバック
                    
                    target_list = get_value_by_path(node_data, key_path)
            else:
                print(f"  Using list from edit_buffer for {key_path}")

            if isinstance(target_list, list) and 0 <= index < len(target_list):
                # 新しいリストを作成して項目を削除
                new_list = [item for i, item in enumerate(target_list) if i != index]

                # edit_buffer にリスト全体の変更として記録
                self.app_state["edit_buffer"][key_path] = new_list
                print(f"  Buffered list change for {key_path}: {len(new_list)} items")

                # 関連するバッファエントリの削除（例: list[index].field）
                prefix_to_remove = f"{key_path}[{index}]"
                keys_to_remove = [k for k in self.app_state["edit_buffer"] if k.startswith(prefix_to_remove)]
                if keys_to_remove:
                    print(f"  Removing related buffer entries: {keys_to_remove}")
                    for k in keys_to_remove:
                        # 削除対象のキーが存在するか確認してから削除
                        if k in self.app_state["edit_buffer"]:
                            del self.app_state["edit_buffer"][k]

                if not self.app_state.get("is_dirty"):
                    self.app_state["is_dirty"] = True

                    # UIStateManagerと状態同期
                    ui_state_manager = self.app_state.get("ui_state_manager")
                    if ui_state_manager:
                        ui_state_manager.set_edit_mode(True)

                # UIを更新（フォーム全体を再描画）
                self.update_detail_form(current_node_id)
                print(f"[OK] Item deletion buffered for {key_path}[{index}]. Form updated.")
                # 代替通知システムを使用
                try:
                    from notification_system import NotificationSystem
                    notification_system = NotificationSystem(page)
                    notification_system.show_success(t("notification.item_delete_recorded").format(index=index))
                except Exception as notif_ex:
                    # フォールバック: 従来のSnackBar
                    page.snack_bar = ft.SnackBar(ft.Text(t("notification.item_delete_recorded").format(index=index)), open=True, duration=2500)
                    page.snack_bar.open = True
                    page.update()

            else:
                print(f"[ERROR] Error deleting list item: List not found or index out of bounds at {key_path}")

        except Exception as err:
            print(f"[ERROR] Error processing list item deletion: {err}")
            import traceback
            print(traceback.format_exc())
            # 代替通知システムを使用
            try:
                from notification_system import NotificationSystem
                notification_system = NotificationSystem(page)
                notification_system.show_error(t("error.list_operation").format(operation="削除", error=err))
            except Exception as notif_ex:
                # フォールバック: 従来のSnackBar
                page.snack_bar = ft.SnackBar(ft.Text(t("error.list_operation").format(operation="削除", error=err)), open=True)
                page.snack_bar.open = True
                page.update()

    def add_list_item_in_add_mode(self, e: ft.ControlEvent, key_path: str):
        """
        追加モードでリストに新しいアイテムを追加する

        Args:
            e: コントロールイベント
            key_path: 対象リストのキーパス
        """
        print(f"[ADD] Request to add list item to: {key_path}")
        page = e.page

        try:
            # edit_bufferから該当キーパスのリスト情報を取得
            target_list = []
            prefix = f"{key_path}["
            list_items = {}

            # edit_bufferからリストの内容を収集
            for buffer_key in self.app_state["edit_buffer"].keys():
                if buffer_key.startswith(prefix) and "]" in buffer_key:
                    try:
                        # インデックスを抽出 (例: "items[0]" -> 0)
                        index_str = buffer_key[len(prefix):buffer_key.index("]", len(prefix))]
                        if index_str.isdigit():
                            index = int(index_str)
                            if index not in list_items:
                                list_items[index] = True  # 存在確認用
                    except ValueError:
                        pass

            # 現在のリストの最大インデックスを計算
            new_index = max(list_items.keys()) + 1 if list_items else 0

            # 既存アイテムの構造を確認
            template_item = None
            template_index = -1

            # 既存のリストアイテムから最後のアイテムをテンプレートとして使用
            if list_items:
                max_index = max(list_items.keys())

                # edit_bufferから最後のアイテムの構造を再構築
                template_item = {}
                for buffer_key, buffer_value in self.app_state["edit_buffer"].items():
                    if buffer_key.startswith(f"{key_path}[{max_index}]"):
                        # サブフィールドを持つ辞書アイテムの場合
                        if "." in buffer_key[buffer_key.index("]")+1:]:
                            field_parts = buffer_key.split(f"{key_path}[{max_index}].")
                            if len(field_parts) > 1:
                                field_name = field_parts[1]

                                if template_index == -1:
                                    template_index = max_index

                                template_item[field_name] = buffer_value
                        else:
                            # 単純な値の場合
                            template_item = buffer_value
                            template_index = max_index

                # 空の辞書の場合は単純値と判断
                if isinstance(template_item, dict) and not template_item:
                    template_item = ""

            # テンプレートが見つかった場合、それに基づいて新しいアイテムを作成
            if template_item is not None:
                if isinstance(template_item, dict):
                    # 辞書型の場合は構造をコピーして値をリセット
                    new_item = {}
                    for key, value in template_item.items():
                        if isinstance(value, str):
                            new_item[key] = ""
                        elif isinstance(value, int):
                            new_item[key] = 0
                        elif isinstance(value, float):
                            new_item[key] = 0.0
                        elif isinstance(value, bool):
                            new_item[key] = False
                        elif isinstance(value, (list, dict)):
                            # 複雑な構造はリセット
                            new_item[key] = [] if isinstance(value, list) else {}
                        else:
                            new_item[key] = None

                    # 新しいアイテムの各フィールドをedit_bufferに追加
                    for sub_key, sub_value in new_item.items():
                        full_key_path = f"{key_path}[{new_index}].{sub_key}"
                        self.app_state["edit_buffer"][full_key_path] = sub_value
                        print(f"  Added {full_key_path} = {sub_value} to edit_buffer")
                else:
                    # 単純型の場合
                    default_value = ""
                    if isinstance(template_item, int):
                        default_value = 0
                    elif isinstance(template_item, float):
                        default_value = 0.0
                    elif isinstance(template_item, bool):
                        default_value = False

                    # edit_bufferに直接追加
                    new_key_path = f"{key_path}[{new_index}]"
                    self.app_state["edit_buffer"][new_key_path] = default_value
                    print(f"  Added {new_key_path} = {default_value} to edit_buffer")
            else:
                # テンプレートがない場合は空の文字列アイテムを追加
                new_key_path = f"{key_path}[{new_index}]"
                self.app_state["edit_buffer"][new_key_path] = ""
                print(f"  Added {new_key_path} = \"\" to edit_buffer")

            # 重要：フォーム状態の保存
            # 現在のフォーム状態を一時的にバックアップ
            form_state_backup = dict(self.app_state["edit_buffer"])

            print(f"Added {key_path}[{new_index}] to edit_buffer")

            # フォームを更新
            self.update_add_form()

            # 重要：バックアップしたフォーム状態を復元
            # update_add_form()で空になったフィールドを元の値で復元する
            for key, value in form_state_backup.items():
                if key not in self.app_state["edit_buffer"]:
                    self.app_state["edit_buffer"][key] = value
                    print(f"  Restored form field: {key}")

            # dirtyフラグを設定
            self.app_state["is_dirty"] = True

            # 完了通知
            page.snack_bar = ft.SnackBar(
                content=ft.Text(t("notification.new_item_added").format(path=key_path)),
                action=t("dialog.close"),
                duration=2000
            )
            page.update()

        except Exception as ex:
            print(f"[ERROR] Error adding list item in add mode: {ex}")
            import traceback
            print(traceback.format_exc())
            page.snack_bar = ft.SnackBar(
                content=ft.Text(t("notification.item_add_failed").format(error=str(ex))),
                action=t("dialog.close"),
                duration=3000,
                bgcolor=ft.Colors.RED
            )
            page.update()

    def delete_list_item_in_add_mode(self, e: ft.ControlEvent, key_path: str, index: int):
        """
        追加モードでリストから項目を削除する

        Args:
            e: コントロールイベント
            key_path: 対象リストのキーパス
            index: 削除する項目のインデックス
        """
        print(f"[DELETE] Request to delete list item: {key_path}[{index}]")
        page = e.page

        try:
            # edit_bufferから該当する項目を削除
            prefix = f"{key_path}[{index}]"
            keys_to_delete = [k for k in self.app_state["edit_buffer"].keys() if k.startswith(prefix)]

            if keys_to_delete:
                for k in keys_to_delete:
                    del self.app_state["edit_buffer"][k]
                    print(f"  Deleted {k} from edit_buffer")

                # 後続のインデックスを更新
                for buffer_key in list(self.app_state["edit_buffer"].keys()):
                    if buffer_key.startswith(f"{key_path}["):
                        try:
                            start_idx = len(f"{key_path}[")
                            end_idx = buffer_key.index("]", start_idx)
                            idx_str = buffer_key[start_idx:end_idx]

                            if idx_str.isdigit():
                                idx = int(idx_str)
                                if idx > index:
                                    # 新しいキーパスを作成
                                    remaining = buffer_key[end_idx:]
                                    new_key = f"{key_path}[{idx-1}]{remaining}"
                                    self.app_state["edit_buffer"][new_key] = self.app_state["edit_buffer"][buffer_key]
                                    del self.app_state["edit_buffer"][buffer_key]
                                    print(f"  Updated index: {buffer_key} -> {new_key}")
                        except ValueError:
                            pass

                # フォームを更新
                self.update_add_form()

                # 完了通知（代替システム）
                try:
                    from notification_system import NotificationSystem
                    notification_system = NotificationSystem(page)
                    notification_system.show_info(t("notification.item_deleted").format(index=index))
                except Exception as notif_ex:
                    print(f"代替通知システムエラー: {notif_ex}")
                    try:
                        page.snack_bar = ft.SnackBar(
                            content=ft.Text(t("notification.item_deleted").format(index=index)),
                            action=t("dialog.close"),
                            duration=2000
                        )
                        page.update()
                    except:
                        print("[WARNING] 全ての通知方法が失敗しました")
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(t("notification.item_not_found").format(path=key_path, index=index)),
                    action=t("dialog.close"),
                    duration=2000
                )
                page.update()

        except Exception as ex:
            print(f"[ERROR] Error deleting list item in add mode: {ex}")
            import traceback
            print(traceback.format_exc())
            page.snack_bar = ft.SnackBar(
                content=ft.Text(t("notification.item_delete_failed").format(error=str(ex))),
                action=t("dialog.close"),
                duration=3000,
                bgcolor=ft.Colors.RED
            )
            page.update()
    
    # ----- ノード追加・削除関連メソッド -----
    
    def commit_new_node(self, e: ft.ControlEvent):
        """
        新規追加モードでのデータ保存処理

        Args:
            e: コントロールイベント
        """
        print("[SAVE] Committing new node...")
        page = e.page

        if not self.app_state["edit_buffer"]:
            page.snack_bar = ft.SnackBar(
                content=ft.Text(t("notification.no_data_to_add")),
                action=t("dialog.close"),
                duration=2000
            )
            page.update()
            return

        try:
            # IDフィールドの確認
            id_key = self.app_state["analysis_results"]["heuristic_suggestions"].get("identifier", "id")

            # edit_bufferからIDを取得
            node_id = None
            if id_key in self.app_state["edit_buffer"]:
                node_id = self.app_state["edit_buffer"][id_key]

                # ID値の妥当性チェック
                if not node_id or str(node_id).strip() == "":
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(t("notification.id_field_required").format(field=id_key)),
                        action=t("dialog.close"),
                        duration=3000
                    )
                    page.update()
                    return

                # ID重複チェック
                node_id_str = str(node_id)
                if node_id_str in self.app_state["data_map"]:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(t("notification.id_already_exists").format(id=node_id_str)),
                        action=t("dialog.close"),
                        duration=3000
                    )
                    page.update()
                    return
            else:
                # IDが指定されていない場合は自動生成
                existing_ids = list(self.app_state["data_map"].keys())

                # プレフィックス付きIDの生成を試みる
                data_manager = self.app_state.get("data_manager")
                if data_manager and hasattr(data_manager, "generate_next_prefixed_id"):
                    node_id = data_manager.generate_next_prefixed_id(existing_ids)
                else:
                    # データマネージャーが利用できない場合はNoneを返す
                    node_id = None
                    print("[WARNING] DataManagerが利用できないため、プレフィックス付きID生成をスキップします")

                print(f"  Attempted prefixed ID generation for commit: result={node_id}")

                # プレフィックス付きIDが生成できなかった場合、既存のロジックを実行
                if node_id is None:
                    id_field_info = next((f for f in self.app_state["analysis_results"]["field_details"] if f["name"] == id_key), None)
                    id_type = "string" # デフォルトは文字列
                    if id_field_info and id_field_info["types"]:
                        id_type = id_field_info["types"][0][0] # 最も一般的な型を取得

                    if id_type == "int":
                        numeric_ids = [int(id_) for id_ in existing_ids if str(id_).isdigit()]
                        node_id = max(numeric_ids) + 1 if numeric_ids else 1
                    elif id_type == "string":
                         # UUID形式かどうかを簡易的にチェック
                         is_uuid_like = False
                         if existing_ids:
                             uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
                             if uuid_pattern.match(str(existing_ids[0])):
                                 is_uuid_like = True

                         if is_uuid_like:
                             node_id = str(uuid.uuid4())
                         else:
                             # UUID形式でなければ、単純な文字列IDを生成（例: "new_item_1"）
                             count = 1
                             while f"new_item_{count}" in existing_ids:
                                 count += 1
                             node_id = f"new_item_{count}"
                    else: # float や bool など、通常IDには使われない型の場合もUUIDを生成
                         node_id = str(uuid.uuid4())

                # 生成したIDをバッファに追加
                self.app_state["edit_buffer"][id_key] = node_id
                print(f"  Auto-generated ID set in edit_buffer: id = {node_id}")

            # 新しいノードオブジェクトを作成
            node_id_str = str(node_id)
            new_node = {id_key: node_id}

            # edit_bufferから値を取得して新しいノードに設定
            # 改良版: 階層レベルを考慮しつつ入力順序を優先するソート基準
            # 1. ルートレベルのフィールドは入力順序のみでソート
            # 2. 子フィールドは親の入力順序を継承しつつ、部分的に階層深さを考慮
            
            # まず、キーを階層ごとにグループ化
            root_keys = [k for k in self.app_state["edit_buffer"].keys() if '.' not in k and '[' not in k]
            nested_keys = [k for k in self.app_state["edit_buffer"].keys() if '.' in k or '[' in k]
            
            # ルートキーは入力順序だけでソート
            sorted_root_keys = sorted(root_keys, key=lambda x: self._get_key_input_order(x))
            
            # ネストされたキーは親の入力順に従ってソートしつつ、同じ親を持つキー同士では階層の浅いものを優先
            sorted_nested_keys = sorted(nested_keys, 
                               key=lambda x: (self._get_parent_order(x), x.count('.'), self._get_key_input_order(x)))
            
            # 両方を組み合わせる
            sorted_keys = sorted_root_keys + sorted_nested_keys
            
            # IDキーだけは常に最初に処理する
            if id_key in sorted_keys:
                sorted_keys.remove(id_key)
                sorted_keys.insert(0, id_key)
                
            print(f"  [UPDATE] Using input order for node construction: {sorted_keys}")

            # DataManagerのメソッドを使用
            data_manager = self.app_state.get("data_manager")

            for key_path in sorted_keys:
                value = self.app_state["edit_buffer"][key_path]
                # IDキー自体は既に設定済みなのでスキップ
                if key_path == id_key:
                    continue

                try:
                    # 修正: 空の値や空の配列であっても、そのキーを保持する
                    if data_manager and hasattr(data_manager, "set_value_by_path"):
                        data_manager.set_value_by_path(new_node, key_path, value)
                    else:
                        # フォールバック
                        
                        set_value_by_path(new_node, key_path, value)

                    print(f"  Set {key_path} = {repr(value)}")
                except Exception as err:
                    print(f"  [WARNING] Error setting value for {key_path}: {err}")

            # 新しいノードをデータモデルに追加
            self.app_state["data_map"][node_id_str] = new_node

            # raw_dataにも追加
            if isinstance(self.app_state["raw_data"], list):
                self.app_state["raw_data"].append(new_node)
                print("  Added node to raw_data")

            # ルートノードとして追加
            if "root_ids" in self.app_state:
                self.app_state["root_ids"].append(node_id_str)
                print("  Added node to root_ids")

            # UIマネージャーを使ってUIを更新
            ui_manager = self.app_state.get("ui_manager")
            if ui_manager:
                ui_manager.update_tree_view()

            # 検索インデックスを更新（重要：新規追加ノードを検索可能にする）
            search_manager = self.app_state.get("search_manager")
            if search_manager:
                # 新規ノードの場合は全インデックスを再構築する方が確実
                search_manager.update_search_index(None)  # None を渡すと全インデックスを再構築
            else:
                print("[WARNING] SearchManagerが見つからないため、検索インデックスの更新をスキップ")

            # 追加モードを終了して通常モードに戻る
            self.app_state["add_mode"] = False
            self.app_state["edit_buffer"].clear()

            # UIStateManagerと状態同期
            ui_state_manager = self.app_state.get("ui_state_manager")
            if ui_state_manager:
                ui_state_manager.set_add_mode(False)

            # 追加したノードを選択状態にする
            self.app_state["selected_node_id"] = node_id_str
            self.update_detail_form(node_id_str)

            # ボタンの状態を更新
            if "add_data_button" in self.ui_controls and self.ui_controls["add_data_button"]:
                self.ui_controls["add_data_button"].selected = False
                self.ui_controls["add_data_button"].update()

            # 完了通知
            page.snack_bar = ft.SnackBar(
                content=ft.Text(t("notification.node_added_success").format(id=node_id_str)),
                action=t("dialog.close"),
                duration=3000
            )
            page.update()
            print(f"[OK] Successfully added new node with ID: {node_id_str}")

        except Exception as ex:
            print(f"[ERROR] Error committing new node: {ex}")
            import traceback
            print(traceback.format_exc())
            page.snack_bar = ft.SnackBar(
                content=ft.Text(t("notification.new_node_add_failed").format(error=str(ex))),
                action=t("dialog.close"),
                duration=4000,
                bgcolor=ft.Colors.RED
            )
            page.update()

    def show_delete_confirmation(self, e: ft.ControlEvent):
        """
        ノード削除確認UIをフォーム内に表示する

        Args:
            e: コントロールイベント
        """
        node_id = self.app_state.get("selected_node_id")
        if not node_id:
            print("[WARNING] No node selected for deletion.")
            return

        # 現在のフォームを退避して確認UIを表示
        detail_form_column = self.ui_controls.get("detail_form_column")
        if not detail_form_column:
            print("[ERROR] Error: detail_form_column not found.")
            return

        # UIStateManagerと状態同期
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager:
            ui_state_manager.set_delete_confirm_mode(True)
        else:
            # 削除確認モードをONに
            self.app_state["delete_confirm_mode"] = True

        # ノードの表示ラベルを取得（より人間が読みやすい形で表示）
        ui_manager = self.app_state.get("ui_manager")
        node_data = self.app_state["data_map"].get(node_id, {})
        
        if ui_manager and hasattr(ui_manager, "get_node_display_label"):
            display_label = ui_manager.get_node_display_label(node_id, node_data)
        else:
            # フォールバック: 基本的な表示ラベル生成
            id_key = self.app_state.get("id_key")
            label_key = self.app_state.get("label_key")
            
            label = str(node_id)
            if label_key and isinstance(node_data, dict) and label_key in node_data:
                label_value = node_data[label_key]
                if label_value is not None:
                    if id_key and id_key != label_key and id_key in node_data:
                        label = f"{node_id}: {label_value}"
                    else:
                        label = str(label_value)
            elif isinstance(node_data, dict):
                # ラベルキー以外の候補を探す
                for potential_label in ["name", "title", "label", "description"]:
                    if potential_label in node_data and node_data[potential_label]:
                        label = f"{node_id}: {node_data[potential_label]}"
                        break
            display_label = label

        if len(display_label) > 50:
            display_label = display_label[:47] + "..."

        # 確認メッセージとボタンを作成
        confirmation_container = ft.Container(
            content=ft.Column([
                ft.Text(t("dialog.delete_confirmation"), size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
                ft.Container(height=10),  # スペーサー
                ft.Text(display_label, size=14, italic=True),
                ft.Container(height=20),  # スペーサー
                ft.Text(t("dialog.delete_warning"),
                       size=12, color=ft.Colors.RED),
                ft.Container(height=20),  # スペーサー
                ft.Row([
                    ft.ElevatedButton(
                        t("dialog.delete_button"),
                        icon=ft.Icons.DELETE_FOREVER,
                        on_click=self._delete_node,
                        style=ft.ButtonStyle(
                            color=ft.Colors.WHITE,
                            bgcolor=ft.Colors.RED
                        )
                    ),
                    ft.OutlinedButton(
                        t("dialog.cancel_button"),
                        icon=ft.Icons.CANCEL,
                        on_click=self.restore_form
                    )
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
            ]),
            padding=20,
            margin=10,
            border=ft.border.all(2, ft.Colors.RED),
            border_radius=10
        )

        # 確認UIを表示
        detail_form_column.controls = [confirmation_container]
        detail_form_column.update()

    def _delete_node(self, e: ft.ControlEvent):
        """ノードを削除する内部メソッド"""
        node_id = self.app_state.get("selected_node_id")
        if not node_id:
            print("[WARNING] No node selected for deletion.")
            return

        # DataManagerのメソッドを使用してノードを削除
        data_manager = self.app_state.get("data_manager")
        if data_manager and hasattr(data_manager, "delete_node"):
            result = data_manager.delete_node(node_id)
        else:
            # フォールバック
            
            result = delete_node(node_id, self.app_state)

        # 削除結果に応じてUIを更新
        if result:
            # 削除に成功した場合、UIを更新
            # UIマネージャーを使ってツリービューを更新
            ui_manager = self.app_state.get("ui_manager")
            if ui_manager:
                ui_manager.update_tree_view()

            # UIStateManagerと状態同期
            ui_state_manager = self.app_state.get("ui_state_manager")
            if ui_state_manager:
                ui_state_manager.set_delete_confirm_mode(False)

            # 詳細フォームをクリア
            self.clear_detail_form()

            # 完了通知（代替システム）
            try:
                from notification_system import NotificationSystem
                notification_system = NotificationSystem(e.page)
                notification_system.show_info(t("notification.node_deleted_success").format(id=node_id))
            except Exception as notif_ex:
                # フォールバック: 従来のSnackBar
                print(f"代替通知システムエラー: {notif_ex}")
                try:
                    e.page.snack_bar = ft.SnackBar(
                        content=ft.Text(t("notification.node_id_deleted").format(id=node_id)),
                        action=t("dialog.close"),
                        duration=3000
                    )
                    e.page.update()
                    print("[OK] フォールバック：従来スナックバーを表示")
                except:
                    print("[WARNING] 全ての通知方法が失敗しました")

    def restore_form(self, e: ft.ControlEvent):
        """
        削除確認をキャンセルして元のフォームに戻す

        Args:
            e: コントロールイベント
        """

        # UIStateManagerと状態同期
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager:
            ui_state_manager.set_delete_confirm_mode(False)
        else:
            # 削除確認モードをOFF
            self.app_state["delete_confirm_mode"] = False

        # 元のフォームを再表示
        selected_node_id = self.app_state.get("selected_node_id")
        self.update_detail_form(selected_node_id)

    def confirm_delete_field(self, e: ft.ControlEvent, key_path: str, key: str):
        """
        フィールド削除の確認ダイアログを表示

        Args:
            e: コントロールイベント
            key_path: 削除するフィールドのキーパス
            key: 削除するフィールドのキー名
        """
        def close_dialog(dialog_result):
            dialog.open = False
            e.page.update()

            if dialog_result:
                self.delete_field(e, key_path, key)

        dialog = ft.AlertDialog(
            title=ft.Text(t("dialog.field_delete_title")),
            content=ft.Text(t("dialog.field_delete_message").format(field=key)),
            actions=[
                ft.TextButton(t("dialog.yes"), on_click=lambda _: close_dialog(True)),
                ft.TextButton(t("dialog.no"), on_click=lambda _: close_dialog(False)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        e.page.dialog = dialog
        dialog.open = True
        e.page.update()

    def delete_field(self, e: ft.ControlEvent, key_path: str, key: str):
        """
        フィールドを削除する

        Args:
            e: コントロールイベント
            key_path: 削除するフィールドのキーパス
            key: 削除するフィールドのキー名
        """
        try:
            # キーパスを分解
            keys = key_path.split('.')

            # edit_bufferからフィールドを削除
            for buffer_key in list(self.app_state["edit_buffer"].keys()):
                if buffer_key == key_path or buffer_key.startswith(f"{key_path}.") or buffer_key.startswith(f"{key_path}["):
                    del self.app_state["edit_buffer"][buffer_key]

            # 追加モードのフォームを更新
            self.update_add_form()

            # フィールド削除通知（代替システム）
            try:
                from notification_system import NotificationSystem
                notification_system = NotificationSystem(e.page)
                notification_system.show_info(t("notification.field_deleted").format(field=key))
            except Exception as notif_ex:
                print(f"代替通知システムエラー: {notif_ex}")
                try:
                    e.page.snack_bar = ft.SnackBar(
                        content=ft.Text(t("notification.field_deleted").format(field=key)),
                        action=t("dialog.close"),
                        duration=2000
                    )
                    e.page.update()
                except:
                    print("[WARNING] 全ての通知方法が失敗しました")

        except Exception as ex:
            print(f"[ERROR] Error deleting field: {ex}")
            import traceback
            print(traceback.format_exc())
            e.page.snack_bar = ft.SnackBar(
                content=ft.Text(t("notification.field_delete_failed").format(error=str(ex))),
                action=t("dialog.close"),
                duration=4000
            )
            e.page.update()

    def _on_add_field_click(self, e):
        """新規フィールド追加ボタンのクリックハンドラ"""
        # detail_form_columnから入力フィールドを探す
        detail_form_column = self.ui_controls.get("detail_form_column")
        if not detail_form_column:
            return
            
        new_field_name = None
        for control in detail_form_column.controls:
            if isinstance(control, ft.Container):
                # コンテナ内のフィールドを探す
                content = control.content
                if isinstance(content, ft.Column):
                    for row in content.controls:
                        if isinstance(row, ft.Row):
                            for field in row.controls:
                                if isinstance(field, ft.TextField) and hasattr(field, 'data') and field.data == "new_field_name":
                                    new_field_name = field.value
                                    field.value = ""  # 入力をクリア
                                    break
        
        if new_field_name:
            # 新しいフィールドをedit_bufferに追加
            self.app_state["edit_buffer"][new_field_name] = ""
            
            # フォームを再構築
            self.update_add_form()
            
            # 通知
            notification = self.app_state.get("notification_system")
            if notification:
                notification.show_success(t("notification.field_added").format(field=new_field_name))


def create_form_manager(app_state: Dict[str, Any], ui_controls: Dict[str, Any], 
                        page: Optional[ft.Page] = None) -> FormManager:
    """FormManagerのインスタンスを作成する工場関数"""
    form_manager = FormManager(app_state, ui_controls, page)
    app_state["form_manager"] = form_manager
    return form_manager
