"""
app.py
FleDjSONのメインアプリケーションクラス

アプリケーション全体の初期化と管理を行うメインクラス
各マネージャークラスを統合し、UIの構築と制御を担当
"""
import flet as ft
import platform
from flet import (
    AppBar, ElevatedButton, FilePicker, Page, Row, Text, TextField, Theme, ThemeMode, Container,
    Icons, Colors, Draggable, DragTarget, ControlEvent, Ref, FilePickerResultEvent, Column,
    Checkbox, Divider, ScrollMode, MainAxisAlignment, CrossAxisAlignment,
    TextButton, SnackBar, Border, BorderRadius, BorderSide, Alignment, Icon
)
from debug_control import print_init
from typing import Optional, Dict, List, Any, Union, Tuple, Callable
import os
import json
import sys
import time
from collections import defaultdict
from enum import Enum

# マネージャークラスのインポート
from managers import (
    create_ui_state_manager, create_analysis_manager, create_data_manager,
    create_ui_manager, create_form_manager, create_search_manager,
    create_drag_drop_manager, SettingsManager, CopyManager, FlattenManager
)

# 翻訳システムのインポート
from translation import t, get_language

# イベントハブとイベント統合をインポート
from event_hub import EventHub, EventType, Event, EventPriority
from event_integration import setup_event_integration

# JSONTemplateをインポート
from json_template import JSONTemplate, create_json_template, FieldType, FieldRole

# フィードバックマネージャをインポート
from feedback import create_feedback_manager, with_feedback

# エラーハンドラーをインポート
from error_handling import (
    create_error_handler, with_error_handling, 
    AppError, ErrorCategory, ErrorSeverity, RecoveryAction
)

# NotificationSystemをインポート
from notification_system import NotificationSystem


class FleDjSONApp:
    """
    FleDjSONのメインアプリケーションクラス

    アプリケーション全体の初期化と管理を行い、各マネージャーを統合して
    UIの構築とイベント処理を担当する

    Attributes:
        page (ft.Page): Fletページオブジェクト
        app_state (Dict): アプリケーションの状態を保持する辞書
        ui_controls (Dict): UIコントロールを保持する辞書
        managers (Dict): 各種マネージャーのインスタンスを保持する辞書
        main_content_area (Ref): メインコンテンツエリアの参照
        file_picker (FilePicker): ファイル選択ダイアログ
        save_file_picker (FilePicker): ファイル保存ダイアログ
    """

    def __init__(self, page: ft.Page):
        """
        FleDjSONAppを初期化します。

        Args:
            page (ft.Page): Fletページオブジェクト
        """
        self.page = page
        self.app_state = {}
        self.ui_controls = {}
        self.managers = {}

        # UI参照用のRef
        self.main_content_area = Ref[Container]()

        # ファイルピッカーの初期化
        self.file_picker = None
        self.save_file_picker = None

        # ページの基本設定
        self.setup_page()

        # EventHubの早期初期化（設定読み込み用）
        self.setup_early_event_hub()
        
        # SettingsManagerの早期初期化（UI作成前に言語設定を読み込む）
        self.setup_early_settings()
        
        # UI基本コントロールの作成
        self.initialize_ui_controls()
        
        # テーマボタンの存在を確認
        if "theme_button" in self.ui_controls:
            print_init("[OK] theme_button is initialized: " + type(self.ui_controls["theme_button"]).__name__)
        else:
            print("\n" + "="*80)
            print("[CRITICAL ERROR] theme_button NOT found in ui_controls!")
            print("Available controls:", list(self.ui_controls.keys()))
            print("="*80 + "\n")
            sys.exit(1)  # 即終了

        # グローバル状態の初期化
        self.initialize_app_state()

        # ファイルピッカーの設定
        self.setup_file_pickers()

        # マネージャーの初期化
        self.initialize_managers()

        # マネージャー間の参照設定
        self.connect_managers()

        # イベントハンドラーの設定
        self.setup_event_handlers()

        # UIの構築
        self.build_ui()

        # 環境変数に基づく初期化メッセージ
        print_init("[OK] FleDjSONApp initialized.")

    def setup_early_event_hub(self):
        """EventHubの早期初期化"""
        from event_hub import EventHub
        self.app_state["event_hub"] = EventHub()
        self.app_state["event_hub"].start()
        print_init("[OK] Early EventHub initialized.")

    def setup_early_settings(self):
        """SettingsManagerの早期初期化"""
        self.managers["settings_manager"] = SettingsManager(self.app_state["event_hub"])
        self.app_state["settings_manager"] = self.managers["settings_manager"]
        
        # 保存された言語設定を読み込んで翻訳システムに反映
        current_language = self.managers["settings_manager"].get_language()
        from translation import set_language as set_global_language
        set_global_language(current_language)
        print_init(f"[OK] Early Settings initialized. Language: {current_language}")

    def setup_page(self):
        """ページの基本設定を行う"""
        self.page.title = "FleDjSON"
        self.page.theme_mode = ThemeMode.SYSTEM
        self.page.padding = 10
        self.page.window_width = 1280
        self.page.window_height = 800
        self.page.window_min_width = 800
        self.page.window_min_height = 600
        
        # アプリケーションアイコンの設定
        # PyInstallerとFletビルドの両方に対応
        if getattr(sys, 'frozen', False):
            # PyInstallerまたはFletビルドで実行されている場合
            if hasattr(sys, '_MEIPASS'):
                # PyInstallerの場合
                root_dir = sys._MEIPASS
            else:
                # Fletビルドの場合
                root_dir = os.path.dirname(sys.executable)
        else:
            # 通常のPythonスクリプトとして実行されている場合
            root_dir = os.path.dirname(os.path.abspath(__file__))
        
        icon_path = os.path.join(root_dir, "assets", "icon.png")
        if os.path.exists(icon_path):
            self.page.window.icon = icon_path
        else:
            print(f"[WARNING] アイコンファイルが見つかりません: {icon_path}")

        # ダークモードテーマのカスタマイズ
        self.page.theme = Theme(color_scheme_seed="indigo")

    def initialize_ui_controls(self):
        """UI基本コントロールを初期化する"""
        # 選択ファイルパスと解析結果のテキスト
        selected_file_path_text = Text("", size=14)
        analysis_result_summary_text = Text(t("analysis.placeholder"), size=14)

        # ツリービューと詳細フォームのコントロールを事前作成
        tree_view = Column(
            expand=True,
            auto_scroll=False,
            spacing=5,
            scroll=ScrollMode.AUTO,
            controls=[Text(t("tree.no_data"), color=ft.Colors.ON_SURFACE_VARIANT)],
            visible=True,
            height=None,
        )

        detail_form_column = Column(
            expand=2,
            spacing=10,
            scroll=ScrollMode.AUTO,
            controls=[Text(t("form.node_details"), color=ft.Colors.ON_SURFACE_VARIANT)],
        )

        # 保存ボタンを作成
        save_button = ElevatedButton(
            t("menu.file.save_as"),
            icon=Icons.SAVE_AS,
            disabled=True
        )

        # データ追加ボタンの作成
        add_data_button = TextButton(
            text=t("button.add"),
            icon=Icons.ADD_CIRCLE_OUTLINE,
            tooltip=t("tooltip.add_node"),
            data="add_data"
        )

        # 検索UI用のコンテナ
        search_ui_container = Container(
            visible=False,
            data="search_ui_container",
            expand=False,
            padding=ft.padding.only(top=10),
        )

        # ボタンコントロール
        detail_save_button = ElevatedButton(
            t("button.save"),
            icon=Icons.SAVE,
            visible=False,
            disabled=True
        )

        detail_cancel_button = TextButton(
            t("button.cancel"),
            icon=Icons.CANCEL,
            visible=False,
            disabled=True
        )

        detail_delete_button = ElevatedButton(
            t("button.delete"),
            icon=Icons.DELETE,
            visible=False,
            color=ft.Colors.RED
        )

        # 現在の言語設定に基づいてスイッチの初期値を決定
        current_language = self.managers["settings_manager"].get_language() if "settings_manager" in self.managers else "ja"
        
        # 言語切り替えスイッチ用の参照
        self.language_switch = ft.Switch(
            value=(current_language == "en"),  # 英語の場合はオン
            on_change=lambda e: None  # 後でハンドラーを設定（仮のハンドラー）
        )
        
        # テーマボタンを作成（他のボタンと同様に事前作成）
        theme_button = ft.PopupMenuButton(
            icon=Icons.SETTINGS,
            tooltip=t("menu.view.theme"),
            items=[
                ft.PopupMenuItem(
                    text=t("theme.system"),
                    icon=Icons.COMPUTER,
                    on_click=lambda _: print("システムテーマがクリックされました！")
                ),
                ft.PopupMenuItem(
                    text=t("theme.light"),
                    icon=Icons.LIGHT_MODE,
                    on_click=lambda _: print("ライトテーマがクリックされました！")
                ),
                ft.PopupMenuItem(
                    text=t("theme.dark"),
                    icon=Icons.DARK_MODE,
                    on_click=lambda _: print("ダークテーマがクリックされました！")
                ),
                ft.PopupMenuItem(
                    text=t("theme.fledjson"),
                    icon=Icons.DATA_ARRAY,
                    on_click=lambda _: print("FleDjSONテーマがクリックされました！")
                ),
                ft.Divider(),  # 区切り線
                ft.PopupMenuItem(
                    content=ft.ListTile(
                        leading=ft.Icon(Icons.LANGUAGE),
                        title=ft.Text("Language / 言語"),
                        subtitle=ft.Text(t("theme.language.current_ja") if get_language() == "ja" else t("theme.language.current_en")),
                        trailing=self.language_switch,
                        dense=True
                    )
                ),
            ],
        )
        
        # チェックボックスを作成（後で使用するため）
        self.lock_checkbox = None
        self.auto_renumber_checkbox = None
        
        # コントロールをui_controlsに登録
        self.ui_controls = {
            "tree_view": tree_view,
            "detail_form_column": detail_form_column,
            "selected_file_path_text": selected_file_path_text,
            "analysis_result_summary_text": analysis_result_summary_text,
            "save_button": save_button,
            "detail_save_button": detail_save_button,
            "detail_cancel_button": detail_cancel_button,
            "detail_delete_button": detail_delete_button,
            "add_data_button": add_data_button,
            "search_ui_container": search_ui_container,
            "theme_button": theme_button,  # テーマボタンを追加
            "loading_indicator": None,  # 後で初期化
        }

    def initialize_app_state(self):
        """アプリケーションの状態を初期化する"""
        self.app_state = {
            "page": self.page,
            "raw_data": None,
            "data_map": {},
            "children_map": {},
            "root_ids": [],
            "selected_node_id": None,
            "id_key": None,
            "children_key": None,
            "depth_key": None,
            "label_key": None,
            "edit_buffer": {},
            "is_dirty": False,
            "add_mode": False,
            "delete_confirm_mode": False,
            "tree_view_dirty": False,
            "detail_form_dirty": False,
            "is_loading": False,
            "current_file": None,
            "tree_drag_locked": True,
            "auto_renumber_enabled": True,  # 自動連番機能のフラグ（デフォルト有効）
            "node_deleted_since_last_save": False,  # ノード削除後のフラグ
            "confirmation_dialog_showing": False,  # 確認ダイアログ表示中フラグ
            "main_content_area": self.main_content_area,
            "search_results": [],
            "removed_fields": set(),
            "expanded_nodes": set(),  # 展開状態のノード追跡用
            "recently_opened_files": [],  # 最近開いたファイル履歴
            "max_recent_files": 5,  # 履歴の最大数
            "event_hub": None,  # EventHubインスタンス（後で設定）
            "json_template": None,  # JSONTemplateインスタンス（後で設定）
            "data_templates": {},  # 生成されたデータテンプレート
            "detected_patterns": {},  # 検出されたパターン
            "field_roles": {},  # フィールドの役割
        }

        # UIコントロールの参照を状態に追加
        self.app_state["ui_controls"] = self.ui_controls

    def setup_file_pickers(self):
        """ファイルピッカーを設定"""
        self.file_picker = FilePicker()
        self.save_file_picker = FilePicker()

        # オーバーレイに追加
        self.page.overlay.extend([self.file_picker, self.save_file_picker])

    def initialize_managers(self):
        """各種マネージャーを初期化する"""
        # FeedbackManager - ユーザーフィードバックを担当（最初に初期化）
        self.managers["feedback_manager"] = create_feedback_manager(
            self.app_state,
            self.ui_controls,
            self.page
        )
        
        # ErrorHandler - エラー処理を担当（FeedbackManagerの次に初期化）
        self.managers["error_handler"] = create_error_handler(
            self.app_state,
            self.ui_controls,
            self.page
        )
        
        # UIStateManager - UIの状態管理を担当
        self.managers["ui_state_manager"] = create_ui_state_manager(
            self.app_state,
            self.ui_controls,
            self.page,
            self
        )

        # AnalysisManager - JSONデータの解析を担当
        self.managers["analysis_manager"] = create_analysis_manager(
            self.app_state,
            self.ui_controls,
            self.page
        )

        # DataManager - データの読み込み、操作、保存を担当
        self.managers["data_manager"] = create_data_manager(
            self.app_state,
            self.ui_controls,
            self.page
        )

        # UIManager - ツリービューやUIレンダリングを担当
        self.managers["ui_manager"] = create_ui_manager(
            self.app_state,
            self.ui_controls,
            self.page
        )

        # FormManager - フォーム生成・操作を担当
        self.managers["form_manager"] = create_form_manager(
            self.app_state,
            self.ui_controls,
            self.page
        )

        # SearchManager - 検索機能を担当
        self.managers["search_manager"] = create_search_manager(
            self.app_state,
            self.ui_controls,
            self.page
        )

        # DragDropManager - ドラッグ＆ドロップを担当
        self.managers["drag_drop_manager"] = create_drag_drop_manager(
            self.app_state,
            self.ui_controls,
            self.page
        )
        
        # CopyManager - 深いコピー処理と配列参照の安全な処理を担当
        self.managers["copy_manager"] = CopyManager(
            self.app_state,
            self.ui_controls,
            self.page
        )
        
        # FlattenManager - ネストされたJSON構造の平坦化を担当
        self.managers["flatten_manager"] = FlattenManager(
            self.app_state,
            self.ui_controls,
            self.page
        )

        # managerへの参照をapp_stateにも登録
        self.app_state["feedback_manager"] = self.managers["feedback_manager"]
        self.app_state["error_handler"] = self.managers["error_handler"]
        self.app_state["ui_state_manager"] = self.managers["ui_state_manager"]
        self.app_state["analysis_manager"] = self.managers["analysis_manager"]
        self.app_state["data_manager"] = self.managers["data_manager"]
        self.app_state["ui_manager"] = self.managers["ui_manager"]
        self.app_state["form_manager"] = self.managers["form_manager"]
        self.app_state["search_manager"] = self.managers["search_manager"]
        self.app_state["drag_drop_manager"] = self.managers["drag_drop_manager"]
        self.app_state["copy_manager"] = self.managers["copy_manager"]
        self.app_state["flatten_manager"] = self.managers["flatten_manager"]

    def connect_managers(self):
        """マネージャー間の参照設定"""
        # UIManagerを他マネージャーに設定
        ui_manager = self.managers["ui_manager"]
        ui_state_manager = self.managers["ui_state_manager"]
        data_manager = self.managers["data_manager"]
        form_manager = self.managers["form_manager"]
        search_manager = self.managers["search_manager"]
        drag_drop_manager = self.managers["drag_drop_manager"]

        # FormManagerに他マネージャーを設定
        form_manager.set_ui_state_manager(ui_state_manager)
        form_manager.set_data_manager(data_manager)
        form_manager.set_ui_manager(ui_manager)
        form_manager.set_search_manager(search_manager)

        # SearchManagerに他マネージャーを設定
        search_manager.set_ui_state_manager(ui_state_manager)
        search_manager.set_data_manager(data_manager)
        search_manager.set_ui_manager(ui_manager)
        search_manager.set_form_manager(form_manager)

        # DragDropManagerに他マネージャーを設定
        drag_drop_manager.set_ui_state_manager(ui_state_manager)
        drag_drop_manager.set_data_manager(data_manager)
        drag_drop_manager.set_ui_manager(ui_manager)

        # UIManagerにコールバック設定
        ui_manager.set_on_tree_node_select_callback(
            lambda e: ui_state_manager.select_node(
                e.control.data if hasattr(e, 'control') else e
            )
        )
        ui_manager.set_on_drag_hover_callback(drag_drop_manager.on_drag_hover)
        ui_manager.set_on_node_drop_callback(drag_drop_manager.on_node_drop)
        ui_manager.set_theme_change_callback(self.change_theme)
        
        # テーマボタンのコールバックを設定
        if "theme_button" in self.ui_controls:
            theme_button = self.ui_controls["theme_button"]
            if theme_button and hasattr(theme_button, 'items'):
                # 各PopupMenuItemにon_clickハンドラーを設定
                def create_handler(theme_mode):
                    def handler(e):
                        self.change_theme(theme_mode)
                    return handler
                
                # 各アイテムにハンドラーを設定
                theme_button.items[0].on_click = create_handler("system")
                theme_button.items[1].on_click = create_handler("light")
                theme_button.items[2].on_click = create_handler("dark")
                theme_button.items[3].on_click = create_handler("fledjson")

        # ファイルピッカーにコールバック設定
        self.file_picker.on_result = self.on_file_selected
        self.save_file_picker.on_result = self.on_save_file_result
        
        # EventHubを設定（既に早期初期化済みの場合はスキップ）
        if "event_hub" not in self.app_state:
            self.setup_event_hub()
        
        # 保存された設定を適用（SettingsManagerは早期初期化済み）
        settings_manager = self.managers["settings_manager"]
        saved_theme_mode = settings_manager.get_setting("theme_mode", "system")
        
        # 保存されたテーマモードを適用（UIの更新はスキップ）
        self.change_theme(saved_theme_mode, skip_ui_update=True)
        
        # NotificationSystemを初期化
        self.app_state["notification_system"] = NotificationSystem(self.page)
        
        # 言語スイッチのハンドラーを設定
        self.language_switch.on_change = self.on_language_change
        
        # 保存された言語設定に基づいてスイッチの状態を設定
        current_language = settings_manager.get_language()
        self.language_switch.value = (current_language == "en")

    def setup_event_handlers(self):
        """イベントハンドラーの設定"""
        # キーボードイベントハンドラ
        self.page.on_keyboard_event = self.on_keyboard

        # ページリサイズハンドラ
        self.page.on_resize = self.on_page_resize

        # UI要素のイベントハンドラを設定
        self.ui_controls["save_button"].on_click = lambda _: self.trigger_save_as_dialog()
        self.ui_controls["add_data_button"].on_click = self.on_add_data_button_click

    def build_ui(self):
        """UIを構築する（初期設定のみ）"""
        
        # ローディングインジケータの作成
        loading_indicator = Container(
            content=Row(
                [
                    Text(t("loading.processing"), size=14, weight="bold"),
                    ft.ProgressRing(width=16, height=16, stroke_width=2)
                ],
                alignment=MainAxisAlignment.CENTER,
                spacing=10
            ),
            padding=10,
            border_radius=5,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            visible=False
        )
        
        # ローディングインジケータをUIコントロールに登録
        self.ui_controls["loading_indicator"] = loading_indicator
        
        # オーバーレイにローディングインジケータを追加
        self.page.overlay.append(loading_indicator)
        
        # 注: 実際のUI構築はrun()メソッドで行う

    @with_error_handling(
        category=ErrorCategory.FILE_IO, 
        recovery_actions=[RecoveryAction.RETRY, RecoveryAction.CANCEL]
    )
    def on_file_selected(self, e: FilePickerResultEvent):
        """ファイル選択ダイアログの結果処理"""
        if not e.files or len(e.files) == 0:
            return

        # FeedbackManagerを取得
        feedback_manager = self.managers.get("feedback_manager")
        # ErrorHandlerを取得
        error_handler = self.managers.get("error_handler")
        
        file_path = e.files[0].path
        file_name = os.path.basename(file_path)
        
        # 操作を登録して開始
        operation_id = None
        if feedback_manager:
            operation_id = feedback_manager.register_operation(
                "file_load", 
                t("loading.file_loading").format(filename=file_name), 
                total_steps=100,
                can_cancel=True
            )
            feedback_manager.start_operation(operation_id, t("loading.loading_file").format(filename=file_name))

        try:
            # ファイルの存在チェック
            if not os.path.exists(file_path):
                raise AppError(
                    t("notification.file_not_found").format(filename=file_name),
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.FILE_IO,
                    recovery_actions=[RecoveryAction.RETRY, RecoveryAction.CANCEL],
                    context={"file_path": file_path}
                )
            
            # DataManagerが利用可能ならそちらに委譲
            data_manager = self.managers.get("data_manager")
            if data_manager:
                # 中間進捗更新
                if feedback_manager:
                    feedback_manager.update_operation(operation_id, 30, t("loading.analyzing_file").format(filename=file_name))
                
                try:
                    data_manager.load_json_file(file_path)
                except json.JSONDecodeError as json_err:
                    # JSONパースエラーを詳細情報付きで処理
                    error_message = t("error.json_parse_failed").format(error=str(json_err))
                    line_col = t("error.json_parse_location").format(line=json_err.lineno, col=json_err.colno)
                    
                    # EventHub経由でエラーを通知
                    if self.app_state.get("event_hub"):
                        self.app_state["event_hub"].publish(
                            EventType.ERROR_DATA_PROCESSING,
                            {
                                "file": file_name,
                                "error": str(json_err),
                                "line": json_err.lineno,
                                "column": json_err.colno
                            },
                            "file_loader",
                            EventPriority.HIGH
                        )
                    
                    raise AppError(
                        f"{error_message} ({line_col})",
                        severity=ErrorSeverity.ERROR,
                        category=ErrorCategory.DATA_PROCESSING,
                        recovery_actions=[RecoveryAction.RETRY, RecoveryAction.CANCEL],
                        original_exception=json_err,
                        context={"file_path": file_path, "line": json_err.lineno, "column": json_err.colno}
                    )
                
                # 中間進捗更新
                if feedback_manager:
                    feedback_manager.update_operation(operation_id, 70, t("loading.processing_data"))
                
                # 最近開いたファイルリストを更新
                self.update_recent_files(file_path)
                
                # メインコンテンツエリアを表示
                main_content = self.main_content_area.current
                if main_content and not main_content.visible:
                    main_content.visible = True
                    self.page.update()
                
                # 保存ボタンを有効化
                save_button = self.ui_controls.get("save_button")
                if save_button:
                    save_button.disabled = False
                    save_button.update()
                
                # 操作完了を通知（通知は削除）
                if feedback_manager:
                    feedback_manager.complete_operation(operation_id)
                
                # 成功イベントを発行
                if self.app_state.get("event_hub"):
                    self.app_state["event_hub"].publish(
                        EventType.DATA_LOADED,
                        {"file_path": file_path, "file_name": file_name},
                        "file_loader"
                    )
        except AppError as app_err:
            # アプリケーション固有のエラーは既にAppErrorとして適切に処理されているのでそのまま
            if feedback_manager and operation_id:
                feedback_manager.error_operation(operation_id, app_err.message)
            
            # ErrorHandlerでエラーを処理
            if error_handler:
                error_handler.handle_error(app_err, operation_id)
            
            raise
        except Exception as ex:
            # その他の一般的な例外
            error_message = t("error.file_loading_error").format(error=str(ex))
            
            if feedback_manager and operation_id:
                feedback_manager.error_operation(operation_id, error_message)
            
            # ErrorHandlerでエラーを処理
            if error_handler:
                app_err = AppError.from_exception(
                    ex,
                    category=ErrorCategory.FILE_IO,
                    severity=ErrorSeverity.ERROR,
                    context={"file_path": file_path, "file_name": file_name}
                )
                error_handler.handle_error(app_err, operation_id)
            
            raise
    
    def update_recent_files(self, file_path):
        """最近開いたファイルリストを更新"""
        # 既存リストから同じパスを削除（重複を避けるため）
        if file_path in self.app_state["recently_opened_files"]:
            self.app_state["recently_opened_files"].remove(file_path)
            
        # リストの先頭に新しいパスを追加
        self.app_state["recently_opened_files"].insert(0, file_path)
        
        # 最大数を超えた場合は古いものを削除
        max_files = self.app_state.get("max_recent_files", 5)
        if len(self.app_state["recently_opened_files"]) > max_files:
            self.app_state["recently_opened_files"] = self.app_state["recently_opened_files"][:max_files]

    @with_error_handling(
        category=ErrorCategory.FILE_IO, 
        recovery_actions=[RecoveryAction.RETRY, RecoveryAction.ALTERNATIVE, RecoveryAction.CANCEL]
    )
    def on_save_file_result(self, e: FilePickerResultEvent):
        """ファイル保存ダイアログの結果処理"""
        if not e.path:
            return

        # FeedbackManagerを取得
        feedback_manager = self.managers.get("feedback_manager")
        # ErrorHandlerを取得
        error_handler = self.managers.get("error_handler")
        
        file_path = e.path
        file_name = os.path.basename(file_path)
        
        # 操作を登録して開始
        operation_id = None
        if feedback_manager:
            operation_id = feedback_manager.register_operation(
                "file_save", 
                t("loading.file_saving").format(filename=file_name), 
                total_steps=100,
                can_cancel=True
            )
            feedback_manager.start_operation(operation_id, t("loading.saving_file").format(filename=file_name))

        try:
            # フォルダの存在チェック
            dir_path = os.path.dirname(file_path)
            if not os.path.exists(dir_path):
                try:
                    # 存在しない場合はフォルダを作成
                    os.makedirs(dir_path, exist_ok=True)
                    
                    # イベント発行
                    if self.app_state.get("event_hub"):
                        self.app_state["event_hub"].publish(
                            EventType.ERROR_RECOVERY_SUCCEEDED,
                            {
                                "message": t("notification.directory_created").format(folder=os.path.basename(dir_path)),
                                "recovery_action": RecoveryAction.ALTERNATIVE.name,
                                "context": {"dir_path": dir_path}
                            },
                            "file_saver",
                            EventPriority.NORMAL
                        )
                except OSError as os_err:
                    # フォルダ作成失敗
                    raise AppError(
                        t("error.directory_create_failed").format(error=str(os_err)),
                        severity=ErrorSeverity.ERROR,
                        category=ErrorCategory.FILE_IO,
                        recovery_actions=[RecoveryAction.RETRY, RecoveryAction.ALTERNATIVE, RecoveryAction.CANCEL],
                        original_exception=os_err,
                        context={"dir_path": dir_path}
                    )
            
            # DataManagerが利用可能ならそちらに委譲
            data_manager = self.managers.get("data_manager")
            if data_manager:
                # 中間進捗更新
                if feedback_manager:
                    feedback_manager.update_operation(operation_id, 30, t("loading.validating_data"))
                
                # データの整合性を検証
                raw_data = self.app_state.get("raw_data")
                if raw_data is None:
                    raise AppError(
                        t("error.no_data_to_save"),
                        severity=ErrorSeverity.ERROR,
                        category=ErrorCategory.DATA_PROCESSING,
                        recovery_actions=[RecoveryAction.CANCEL],
                        context={"file_path": file_path}
                    )
                
                # 中間進捗更新
                if feedback_manager:
                    feedback_manager.update_operation(operation_id, 50, t("loading.writing_data"))
                
                try:
                    # バックアップの作成（既存ファイルの場合）
                    if os.path.exists(file_path):
                        backup_dir = os.path.join(os.path.dirname(os.path.dirname(file_path)), "backup")
                        os.makedirs(backup_dir, exist_ok=True)
                        
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        backup_file = os.path.join(backup_dir, f"{os.path.basename(file_path)}.{timestamp}.bak")
                        import shutil
                        shutil.copy2(file_path, backup_file)
                        
                        # バックアップ作成ログ
                        if error_handler and hasattr(error_handler, 'logger'):
                            error_handler.logger.info(f"バックアップファイルを作成しました: {backup_file}")
                    
                    # ファイル保存
                    data_manager.save_json_file(file_path)
                    
                except (IOError, PermissionError) as io_err:
                    # 書き込み関連のエラー
                    raise AppError(
                        t("error.file_write_failed").format(error=str(io_err)),
                        severity=ErrorSeverity.ERROR,
                        category=ErrorCategory.FILE_IO,
                        recovery_actions=[RecoveryAction.RETRY, RecoveryAction.ALTERNATIVE, RecoveryAction.CANCEL],
                        original_exception=io_err,
                        context={"file_path": file_path}
                    )
                
                # 操作完了を通知（通知は削除）
                if feedback_manager:
                    feedback_manager.complete_operation(operation_id)
                
                # current_fileを更新
                self.app_state["current_file"] = file_path
                
                # UIのファイル名表示を更新
                if "selected_file_path_text" in self.ui_controls:
                    self.ui_controls["selected_file_path_text"].value = file_name
                    self.ui_controls["selected_file_path_text"].update()
                
                # ファイル解析結果を更新
                analysis_manager = self.managers.get("analysis_manager")
                if analysis_manager and self.app_state.get("raw_data"):
                    analysis_results = analysis_manager.analyze_json_structure(
                        file_path=file_path,
                        data=self.app_state["raw_data"]
                    )
                    if analysis_results and "analysis_result_summary_text" in self.ui_controls:
                        # DataManagerと同じ3行形式で表示を作成
                        item_count = analysis_results.get("total_records", 0)
                        
                        # 1行目: ファイル名とレコード数
                        line1 = f"[FILE] {file_name} | [DATA] {t('analysis.record_count').format(count=item_count)}"
                        
                        # 2行目: 主要フィールド一覧（field_detailsから取得）
                        main_keys = []
                        if "field_details" in analysis_results and analysis_results["field_details"]:
                            # トップレベルのフィールド名を取得
                            for field in analysis_results["field_details"]:
                                # nameフィールドからパスを取得（"."が含まれないものがトップレベル）
                                field_path = field.get("name", "")
                                if "." not in field_path and field_path:  # トップレベルフィールドのみ
                                    field_name = field.get("display_name", field_path)
                                    
                                    # ネストしたオブジェクトの場合は子要素も表示
                                    # field_detailsから同じ親パスを持つ子要素を探す
                                    if "dict" in field.get("types", []):
                                        child_fields = []
                                        for child_field in analysis_results["field_details"]:
                                            child_path = child_field.get("name", "")
                                            # 現在のフィールドの子要素かチェック
                                            if child_path.startswith(f"{field_path}.") and child_path.count(".") == 1:
                                                child_name = child_field.get("display_name", child_path.split(".")[-1])
                                                child_fields.append(child_name)
                                        
                                        if child_fields:
                                            field_name = f"{field_name}({', '.join(child_fields[:3])})"
                                    
                                    main_keys.append(field_name)
                        
                        # フィールドがない場合はraw_dataから取得を試みる
                        if not main_keys and self.app_state.get("raw_data"):
                            raw_data = self.app_state["raw_data"]
                            if isinstance(raw_data, list) and raw_data:
                                first_item = raw_data[0] if isinstance(raw_data[0], dict) else {}
                                main_keys = list(first_item.keys())[:6]
                        
                        line2 = f"[KEY] {', '.join(main_keys[:6])}" + ("..." if len(main_keys) > 6 else "")
                        
                        # 3行目: キー設定情報
                        key_info_parts = []
                        id_key = analysis_results.get("id_key", "不明")
                        label_key = analysis_results.get("label_key", "不明")
                        children_key = analysis_results.get("children_key", "不明")
                        
                        key_info_parts.append(f"ID={id_key}")
                        key_info_parts.append(f"Label={label_key}")
                        if children_key != "不明":
                            key_info_parts.append(f"Children={children_key}")
                        
                        line3 = f"[TARGET] {', '.join(key_info_parts)}"
                        
                        # 3行に分けて表示
                        self.ui_controls["analysis_result_summary_text"].value = f"{line1}\n{line2}\n{line3}"
                        self.ui_controls["analysis_result_summary_text"].update()
                
                # 成功イベントを発行
                if self.app_state.get("event_hub"):
                    self.app_state["event_hub"].publish(
                        EventType.DATA_SAVED,
                        {"file_path": file_path, "file_name": file_name},
                        "file_saver"
                    )
                    
        except AppError as app_err:
            # アプリケーション固有のエラーは既にAppErrorとして適切に処理されているのでそのまま
            if feedback_manager and operation_id:
                feedback_manager.error_operation(operation_id, app_err.message)
            
            # ErrorHandlerでエラーを処理
            if error_handler:
                error_handler.handle_error(app_err, operation_id)
            
            raise
        except Exception as ex:
            # その他の一般的な例外
            error_message = t("error.file_saving_error").format(error=str(ex))
            
            if feedback_manager and operation_id:
                feedback_manager.error_operation(operation_id, error_message)
            else:
                # FeedbackManagerがない場合は従来のSnackBarを使用
                self.page.snack_bar = SnackBar(
                    content=Text(error_message),
                    action=t("dialog.close"),
                    bgcolor=ft.Colors.RED,
                    open=True
                )
                self.page.update()
            
            # ErrorHandlerでエラーを処理
            if error_handler:
                app_err = AppError.from_exception(
                    ex,
                    category=ErrorCategory.FILE_IO,
                    severity=ErrorSeverity.ERROR,
                    context={"file_path": file_path, "file_name": file_name}
                )
                error_handler.handle_error(app_err, operation_id)
            
            raise

    def trigger_save_as_dialog(self):
        """名前を付けて保存ダイアログを表示"""
        if self.app_state.get("raw_data") is None:
            self.page.snack_bar = SnackBar(
                content=Text(t("error.no_data_to_save")),
                open=True
            )
            self.page.update()
            return

        suggested_filename = os.path.basename(self.app_state.get("current_file", "")) or "data.json"
        self.save_file_picker.save_file(
            dialog_title=t("dialog.save_as_title"),
            file_name=suggested_filename,
            allowed_extensions=["json"]
        )

    def on_add_data_button_click(self, e: ControlEvent):
        """データ追加ボタンクリック時の処理"""
        # UIStateManagerが利用可能ならそちらに委譲
        ui_state_manager = self.managers.get("ui_state_manager")
        if ui_state_manager:
            add_mode = not ui_state_manager.is_add_mode()
            ui_state_manager.set_add_mode(add_mode)
            
            # 追加モードで、JSONTemplateを使用して新規データのテンプレートを提供
            if add_mode:
                data_manager = self.managers.get("data_manager")
                form_manager = self.managers.get("form_manager")
                
                if data_manager and form_manager:
                    # テンプレートから初期データを生成する
                    template = self.app_state.get("data_templates", {}).get("main")
                    
                    if template:
                        # テンプレートを使って新規データを作成
                        json_template = self.app_state.get("json_template")
                        if json_template:
                            # テンプレートに基づく空オブジェクトを作成
                            empty_data = {}
                            
                            # 必須と推奨フィールドを追加
                            if "fields" in template:
                                for field_name, field_info in template["fields"].items():
                                    if field_info.get("importance") in ["required", "recommended"]:
                                        empty_data[field_name] = None
                            
                            # FormManagerに渡して追加モードのフォームを更新
                            form_manager.update_add_form_with_template(empty_data)

    def on_page_resize(self, e):
        """ページサイズ変更時のイベントハンドラ"""
        # レスポンシブなUIの調整が必要な場合に実装
        pass

    def on_keyboard(self, e: ft.KeyboardEvent):
        """キーボードイベントハンドラ"""
        
        # 検索マネージャーのキーボードイベントハンドラを呼び出し
        search_manager = self.managers.get("search_manager")
        if search_manager and search_manager.handle_keyboard_event(e):
            return  # 検索マネージャーがイベントを処理した場合は終了

        # 他のキーボードショートカットを実装
        # Ctrl+S/Cmd+S: 保存
        if (e.ctrl or e.meta) and e.key.lower() == "s" and not e.shift:
            print("[KEY] 保存ショートカット(Ctrl+S/Cmd+S)が検出されました")
            
            # ファイルが指定されていない場合
            file_path = self.app_state.get("current_file")
            if not file_path:
                feedback_manager = self.managers.get("feedback_manager")
                if feedback_manager:
                    feedback_manager.show_warning(t("error.no_file_to_save"))
                return True
            
            # ノード削除後の場合は確認ダイアログを表示
            if self.app_state.get("node_deleted_since_last_save", False):
                print("[IMPORTANT] ノード削除後の保存には確認が必要です")
                self.show_save_confirmation_dialog(file_path)
            else:
                # 通常の保存処理
                self.save_file_directly(file_path)
            return True

    def setup_event_hub(self):
        """EventHubを設定し、マネージャーと統合する"""
        event_hub = setup_event_integration(self, self.managers)
        self.app_state["event_hub"] = event_hub
        print("[OK] EventHub setup complete")
        
        # JSONTemplateの初期化
        self.setup_json_template(event_hub)
        
        # イベントハンドラーの登録
        event_hub.subscribe(EventType.DATA_LOADED, self.on_data_loaded_event)
        event_hub.subscribe(EventType.NODE_SELECTED, self.on_node_selected_event)
        # TODO: TEMPLATE_GENERATED, TEMPLATE_APPLIEDイベントが定義されたら有効化
        # event_hub.subscribe(EventType.TEMPLATE_GENERATED, self.on_template_generated_event)
        # event_hub.subscribe(EventType.TEMPLATE_APPLIED, self.on_template_applied_event)
        
    def setup_json_template(self, event_hub):
        """JSONTemplateを設定する"""
        json_template = create_json_template(event_hub)
        self.app_state["json_template"] = json_template
        print("[OK] JSONTemplate setup complete")
        
    def on_data_loaded_event(self, event: Event):
        """データロード完了時のイベントハンドラー"""
        if event.source != "app":  # 自分が発行したイベントは無視
            # メインコンテンツエリアを表示
            main_content = self.main_content_area.current
            if main_content and not main_content.visible:
                main_content.visible = True
                # 保存ボタンを有効化
                save_button = self.ui_controls.get("save_button")
                if save_button:
                    save_button.disabled = False
                self.page.update()
            
            # JSONテンプレートの生成
            self.generate_templates()
    
    def on_node_selected_event(self, event: Event):
        """ノード選択時のイベントハンドラー"""
        if event.source != "app" and event.data and "node_id" in event.data:
            node_id = event.data["node_id"]
            # ここでノード選択時の追加処理を行う（必要に応じて）
    
    def on_template_generated_event(self, event: Event):
        """テンプレート生成完了時のイベントハンドラー"""
        if event.source != "app" and event.data:
            # テンプレート生成の通知や処理
            print(f"[OK] Template generated for {event.data.get('source_data_type', 'unknown')}")
    
    def on_template_applied_event(self, event: Event):
        """テンプレート適用完了時のイベントハンドラー"""
        if event.source != "app" and event.data:
            # テンプレート適用の通知や処理
            print(f"[OK] Template applied to {event.data.get('source_data_type', 'unknown')}")
    
    def generate_templates(self):
        """JSONデータからテンプレートを生成する"""
        json_template = self.app_state.get("json_template")
        raw_data = self.app_state.get("raw_data")
        
        if not json_template or raw_data is None:
            return
        
        # テンプレートの生成
        try:
            template = json_template.generate_template(raw_data)
            self.app_state["data_templates"]["main"] = template
            
            # フィールドの役割を推測
            if isinstance(raw_data, dict):
                field_roles = json_template.suggest_field_roles(raw_data)
                self.app_state["field_roles"] = field_roles
            
            # パターンの検出（リスト型データの場合）
            if isinstance(raw_data, list) and raw_data and all(isinstance(item, dict) for item in raw_data):
                patterns = json_template.detect_patterns(raw_data)
                self.app_state["detected_patterns"] = patterns
            
            print(f"[OK] Templates generated successfully")
        except Exception as e:
            import traceback
            print(f"[ERROR] Error generating templates: {e}")
            traceback.print_exc()
    
    def apply_template_to_data(self, data, template_name="main"):
        """テンプレートをデータに適用する"""
        json_template = self.app_state.get("json_template")
        template = self.app_state.get("data_templates", {}).get(template_name)
        
        if not json_template or not template or data is None:
            return data
        
        try:
            result = json_template.apply_template(template, data)
            return result
        except Exception as e:
            print(f"[ERROR] Error applying template: {e}")
            return data
    
    def run(self):
        """アプリケーションを実行する"""
        
        # アプリケーションアイコンを設定（冗長なので削除またはコメントアウト）
        # アイコンはsetup_page()で既に設定済み
        
        # 最終的なUI構築
        self.complete_ui_setup()
        print("[OK] FleDjSONApp running.")

    def complete_ui_setup(self):
        """最終的なUI構築を行う"""
        
        # テーマボタンの存在チェック
        if "theme_button" not in self.ui_controls:
            print("[CRITICAL ERROR] theme_button not found in ui_controls!")
            print(f"Available controls: {list(self.ui_controls.keys())}")
            import sys
            sys.exit(1)
        
        theme_button = self.ui_controls["theme_button"]
        
        # 既存のUIを削除
        self.page.controls.clear()

        # 検索UIの作成
        search_manager = self.managers.get("search_manager")
        if search_manager:
            search_ui = search_manager.create_search_ui()
            self.ui_controls["search_ui_container"].content = search_ui

        # トップコントロールセクションの作成
        top_controls = self.build_top_controls()
        
        # メインコンテンツエリアの作成
        main_content = self.build_main_content()
        
        # ページにコントロールを追加（AppBarを除外）
        self.page.add(top_controls, main_content)
        self.page.update()
        

    def build_top_controls(self):
        """トップコントロールセクションを構築"""
        # ファイル選択UIの作成
        file_operations = Row(
            [
                Row(
                    [
                        ElevatedButton(
                            t("button.select_file"),
                            icon=Icons.UPLOAD_FILE,
                            on_click=lambda _: self.file_picker.pick_files(
                                dialog_title=t("dialog.open_file", "JSONファイルを開く"),
                                allow_multiple=False,
                                allowed_extensions=["json"]
                            )
                        ),
                        self.ui_controls["save_button"],
                        self.ui_controls["selected_file_path_text"],
                    ],
                    spacing=10,
                ),
                self.ui_controls["theme_button"],  # 設定ボタンを右端に配置
            ],
            alignment=MainAxisAlignment.SPACE_BETWEEN,
            expand=True,
        )

        # 解析情報と検索UIの作成
        analysis_search = Row(
            [
                Container(
                    content=self.ui_controls["analysis_result_summary_text"],
                    padding=10,
                    border=Border(
                        left=BorderSide(1, ft.Colors.OUTLINE),
                        top=BorderSide(1, ft.Colors.OUTLINE),
                        right=BorderSide(1, ft.Colors.OUTLINE),
                        bottom=BorderSide(1, ft.Colors.OUTLINE)
                    ),
                    border_radius=BorderRadius(5, 5, 5, 5),
                    width=300,
                    expand=False,
                ),
                self.ui_controls["search_ui_container"],
            ],
            spacing=10,
            alignment=MainAxisAlignment.START,
            vertical_alignment=CrossAxisAlignment.CENTER,
        )

        # トップコントロールをまとめる
        return Column(
            [
                file_operations,
                analysis_search,
            ],
            spacing=10,
        )

    def build_main_content(self):
        """メインコンテンツエリアを構築"""
        # ロックアイコンを作成
        lock_icon = ft.Icon(
            name=Icons.LOCK if self.app_state["tree_drag_locked"] else Icons.LOCK_OPEN,
            size=16,
            tooltip=t("tooltip.lock_on", "ロック中 (移動不可)") if self.app_state["tree_drag_locked"] else t("tooltip.lock_off", "解除中 (移動可能)")
        )

        # ロックチェックボックスの作成
        self.lock_checkbox = Checkbox(
            label=t("checkbox.move_lock", "移動ロック"),
            value=self.app_state["tree_drag_locked"],
            tooltip=t("tooltip.move_lock", "ツリーノードのドラッグ＆ドロップによる移動をロック/解除します"),
            data=lock_icon,
            on_change=self.on_lock_change,
        )
        
        # 自動連番チェックボックスの作成
        self.auto_renumber_checkbox = Checkbox(
            label=t("checkbox.auto_renumber", "自動連番"),
            value=self.app_state.get("auto_renumber_enabled", True),
            tooltip=t("tooltip.auto_renumber", "ドラッグ＆ドロップ後に兄弟ノードのIDを自動的に連番に整列します"),
            on_change=self.on_auto_renumber_change,
        )

        # ツリーコントロールローの作成
        tree_controls = Row(
            [
                lock_icon,
                self.lock_checkbox,
                Icon(
                    name=Icons.HELP_OUTLINE,
                    size=16,
                    tooltip="移動ロック: ツリーのドラッグ＆ドロップ機能のオン/オフを切り替えします。\n\nロック中（オン）: ノードの編集が可能\n解除中（オフ）: ノードの移動が可能",
                    color=ft.Colors.ON_SURFACE_VARIANT
                ),
                Container(width=20),  # スペーサー
                self.auto_renumber_checkbox,
                Icon(
                    name=Icons.HELP_OUTLINE,
                    size=16,
                    tooltip="自動連番: ドラッグ＆ドロップ後に兄弟ノードのIDを自動的に連番に整列します。\n\n数値接尾辞を持つIDが自動的に1から順番に振り直されます。",
                    color=ft.Colors.ON_SURFACE_VARIANT
                ),
                Container(width=20),  # スペーサー
                self.ui_controls["add_data_button"],
            ],
            alignment=MainAxisAlignment.START,
            spacing=5,
        )

        # ツリーパネルを作成
        tree_panel = Column(
            [
                tree_controls,
                Container(
                    content=self.ui_controls["tree_view"],
                    border=Border(
                        left=BorderSide(1, ft.Colors.OUTLINE),
                        top=BorderSide(1, ft.Colors.OUTLINE),
                        right=BorderSide(1, ft.Colors.OUTLINE),
                        bottom=BorderSide(1, ft.Colors.OUTLINE)
                    ),
                    border_radius=BorderRadius(5, 5, 5, 5),
                    padding=5,
                    expand=True,
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                ),
            ],
            expand=1,
            alignment=MainAxisAlignment.START,
            horizontal_alignment=CrossAxisAlignment.STRETCH,
        )

        # 詳細パネルを作成
        detail_panel = Container(
            content=self.ui_controls["detail_form_column"],
            border=Border(
                left=BorderSide(1, ft.Colors.OUTLINE),
                top=BorderSide(1, ft.Colors.OUTLINE),
                right=BorderSide(1, ft.Colors.OUTLINE),
                bottom=BorderSide(1, ft.Colors.OUTLINE)
            ),
            border_radius=BorderRadius(5, 5, 5, 5),
            padding=10,
            expand=2,
        )

        # 2カラムレイアウトの作成
        main_layout = Row(
            [
                tree_panel,
                detail_panel,
            ],
            expand=True,
            vertical_alignment=CrossAxisAlignment.START,
        )

        # メインコンテンツエリアをコンテナで包む
        main_content = Container(
            ref=self.main_content_area,
            visible=False,  # 初期状態は非表示に設定
            expand=True,
            content=Column(
                [
                    Divider(),
                    main_layout,
                ],
                expand=True,
            )
        )

        return main_content

    def on_lock_change(self, e: ControlEvent):
        """ツリービューのロック状態変更時の処理"""
        lock_icon = e.control.data
        lock_icon.name = Icons.LOCK if e.control.value else Icons.LOCK_OPEN
        lock_icon.tooltip = "ロック中 (移動不可)" if e.control.value else "解除中 (移動可能)"
        lock_icon.update()

        # ロック状態を更新
        self.app_state["tree_drag_locked"] = e.control.value

        # UIManagerに通知
        ui_manager = self.managers.get("ui_manager")
        if ui_manager:
            ui_manager.on_lock_change(e)
    
    def on_auto_renumber_change(self, e: ControlEvent):
        """自動連番機能の有効/無効を切り替える"""
        self.app_state["auto_renumber_enabled"] = e.control.value
        print(f"[NUMBER] 自動連番機能: {'有効' if e.control.value else '無効'}")
        
        # FeedbackManagerでユーザーに通知
        feedback_manager = self.managers.get("feedback_manager")
        if feedback_manager:
            if e.control.value:
                feedback_manager.show_info(t("feature.auto_renumber_enabled"))
            else:
                feedback_manager.show_info(t("feature.auto_renumber_disabled"))
    
    def on_language_change(self, e: ControlEvent):
        """言語を切り替える
        
        Args:
            e: Switch変更イベント
        """
        settings_manager = self.managers.get("settings_manager")
        if not settings_manager:
            return
        
        # スイッチの状態に基づいて言語を設定（オフ=日本語、オン=英語）
        new_language = "en" if e.control.value else "ja"
        settings_manager.set_language(new_language)
        
        # サブタイトルを更新
        if "theme_button" in self.ui_controls:
            theme_button = self.ui_controls["theme_button"]
            if theme_button and hasattr(theme_button, 'items') and len(theme_button.items) > 5:
                language_item = theme_button.items[5]  # 言語メニュー項目
                if hasattr(language_item, 'content') and hasattr(language_item.content, 'subtitle'):
                    # 新しい言語に基づいて適切なテキストを設定
                    language_item.content.subtitle.value = t("theme.language.current_ja") if new_language == "ja" else t("theme.language.current_en")
                    language_item.update()
        
        # 全体のUIを再構築して即座に反映
        self.rebuild_ui_for_language_change()
        
        # 通知を表示
        notification_system = self.app_state.get("notification_system")
        if notification_system:
            notification_system.show_info(t("notification.language_changed"))
    
    def rebuild_ui_for_language_change(self):
        """言語変更時にUIを再構築"""
        # 既存のUIを保持しながら更新
        # トップコントロールセクションのテキストを更新
        if "save_button" in self.ui_controls:
            self.ui_controls["save_button"].text = t("menu.file.save_as")
            self.ui_controls["save_button"].update()
        
        # ファイル選択ボタンの更新
        top_controls = self.page.controls[0] if len(self.page.controls) > 0 else None
        if top_controls and hasattr(top_controls, 'controls'):
            # ファイル選択ボタンを探して更新
            for control in top_controls.controls:
                if isinstance(control, ft.Row):
                    for row_control in control.controls:
                        if isinstance(row_control, ft.Row):
                            for btn in row_control.controls:
                                if isinstance(btn, ft.ElevatedButton) and hasattr(btn, 'icon') and btn.icon == Icons.UPLOAD_FILE:
                                    btn.text = t("button.select_file")
                                    btn.update()
        
        # 全体的なpage.update()で変更を反映
        self.page.update()
    
    def change_theme(self, theme_mode: str, skip_ui_update: bool = False):
        """テーマを変更する
        
        Args:
            theme_mode: "system", "light", "dark", "fledjson"のいずれか
            skip_ui_update: UIの更新をスキップするか（初期化時用）
        """
        print(f"[THEME] change_theme called with: {theme_mode}, skip_ui_update: {skip_ui_update}")
        
        settings_manager = self.managers.get("settings_manager")
        if settings_manager:
            # テーマモードを設定
            settings_manager.set_theme_mode(theme_mode)
            
            # FleDjSONカスタムテーマの場合
            if theme_mode == "fledjson":
                # ダークモードをベースにカスタムテーマを適用
                self.page.theme_mode = ft.ThemeMode.DARK
                
                # カスタムカラースキーム
                self.page.theme = ft.Theme(
                    color_scheme=ft.ColorScheme(
                        primary="#7C3AED",  # 明るい紫
                        on_primary="#84CC16",  # ライムグリーン（アイコンと同じ）
                        primary_container="#5B21B6",  # 濃い紫
                        on_primary_container="#A3E635",  # 明るいライムグリーン
                        secondary="#84CC16",  # ライムグリーン
                        on_secondary="#1E1B4B",  # 濃い紫
                        secondary_container="#65A30D",  # 濃いライムグリーン
                        on_secondary_container="#F0FDF4",  # 薄い緑
                        surface="#1E1B4B",  # 濃い紫（背景）
                        on_surface="#84CC16",  # ライムグリーン（テキスト）
                        surface_variant="#2E1A47",  # やや明るい紫
                        on_surface_variant="#A3E635",  # 明るいライムグリーン
                        background="#0F0E1F",  # より濃い紫（最背面）
                        on_background="#84CC16",  # ライムグリーン
                        error="#FF6B6B",
                        on_error="#1E1B4B",
                        outline="#8B5CF6",  # 明るい紫（境界線）
                        shadow="#000000",
                        surface_tint="#7C3AED",  # サーフェスのティント色
                    ),
                    use_material3=True
                )
                
                # ページの背景色も設定
                self.page.bgcolor = "#0F0E1F"
                
                # 特定のUI要素の色を更新
                if "selected_file_path_text" in self.ui_controls:
                    self.ui_controls["selected_file_path_text"].color = "#84CC16"
                if "analysis_result_summary_text" in self.ui_controls:
                    self.ui_controls["analysis_result_summary_text"].color = "#84CC16"
                
                # ツリービューとフォームの初期メッセージの色を更新
                if "tree_view" in self.ui_controls:
                    tree_view = self.ui_controls["tree_view"]
                    if tree_view.controls and len(tree_view.controls) == 1:
                        # 初期メッセージの場合
                        if hasattr(tree_view.controls[0], 'value') and tree_view.controls[0].value == "ツリービューがここに表示されます...":
                            tree_view.controls[0].color = "#A3E635"  # 明るいライムグリーン
                
                if "detail_form_column" in self.ui_controls:
                    form_column = self.ui_controls["detail_form_column"]
                    if form_column.controls and len(form_column.controls) == 1:
                        # 初期メッセージの場合
                        if hasattr(form_column.controls[0], 'value') and form_column.controls[0].value == "ノードを選択してください":
                            form_column.controls[0].color = "#A3E635"  # 明るいライムグリーン
                
                # SearchManagerの検索結果カウンターの色を更新
                search_manager = self.managers.get("search_manager")
                if search_manager and hasattr(search_manager, 'result_counter') and search_manager.result_counter:
                    search_manager.result_counter.color = "#A3E635"  # 明るいライムグリーン
                    if search_manager.result_counter.page:
                        search_manager.result_counter.update()
                
                # チェックボックスのラベル色を更新
                if self.lock_checkbox:
                    self.lock_checkbox.label_style = ft.TextStyle(color="#A3E635")
                if self.auto_renumber_checkbox:
                    self.auto_renumber_checkbox.label_style = ft.TextStyle(color="#A3E635")
                
                # 新規追加ボタンの色を更新
                if "add_data_button" in self.ui_controls:
                    self.ui_controls["add_data_button"].style = ft.ButtonStyle(
                        color={"": "#84CC16"}  # ライムグリーン
                    )
                
                # 現在のフォーム内容をチェックして初期メッセージの色を更新
                if not skip_ui_update:
                    form_manager = self.managers.get("form_manager")
                    if form_manager and "detail_form_column" in self.ui_controls:
                        form_column = self.ui_controls["detail_form_column"]
                        # フォームの全てのテキストコントロールを確認
                        for control in form_column.controls:
                            if isinstance(control, ft.Text) and control.value == "ノードを選択してください":
                                control.color = "#A3E635"
                                control.update()
            else:
                # 通常のテーマモード
                theme_mode_map = {
                    "system": ft.ThemeMode.SYSTEM,
                    "light": ft.ThemeMode.LIGHT,
                    "dark": ft.ThemeMode.DARK
                }
                
                # ページのテーマを更新
                new_theme_mode = theme_mode_map.get(theme_mode, ft.ThemeMode.SYSTEM)
                self.page.theme_mode = new_theme_mode
                
                # 背景色をリセット
                self.page.bgcolor = None
                
                # UI要素の色もリセット
                if "selected_file_path_text" in self.ui_controls:
                    self.ui_controls["selected_file_path_text"].color = None
                if "analysis_result_summary_text" in self.ui_controls:
                    self.ui_controls["analysis_result_summary_text"].color = None
                
                # SearchManagerの検索結果カウンターの色をリセット
                search_manager = self.managers.get("search_manager")
                if search_manager and hasattr(search_manager, 'result_counter') and search_manager.result_counter:
                    search_manager.result_counter.color = None
                    if search_manager.result_counter.page:
                        search_manager.result_counter.update()
                
                # チェックボックスのラベル色をリセット
                if self.lock_checkbox:
                    self.lock_checkbox.label_style = None
                if self.auto_renumber_checkbox:
                    self.auto_renumber_checkbox.label_style = None
                
                # 新規追加ボタンの色をリセット
                if "add_data_button" in self.ui_controls:
                    self.ui_controls["add_data_button"].style = None
                
                # カラースキームシードも更新（Material 3 テーマ）
                if theme_mode != "system":
                    # ライト/ダークに応じて異なるカラースキームを設定
                    if theme_mode == "light":
                        self.page.theme = ft.Theme(
                            color_scheme_seed=ft.Colors.BLUE,
                            use_material3=True
                        )
                    else:  # dark
                        self.page.theme = ft.Theme(
                            color_scheme_seed=ft.Colors.INDIGO,
                            use_material3=True
                        )
                else:
                    # システムテーマの場合はデフォルトに戻す
                    self.page.theme = ft.Theme(use_material3=True)
            
            self.page.update()
            print(f"[OK] テーマを {theme_mode} に変更しました")
            
            # 通知は削除：ビジュアル変更で明確なため不要
    
    def save_file_directly(self, file_path: str) -> bool:
        """ファイルを直接保存する
        
        Args:
            file_path: 保存先のファイルパス
            
        Returns:
            bool: 保存が成功したかどうか
        """
        data_manager = self.managers.get("data_manager")
        if not data_manager:
            return False
        
        # フォームマネージャーで編集中のデータがある場合は先に適用
        form_manager = self.managers.get("form_manager")
        if form_manager and self.app_state.get("is_dirty", False):
            print("[NOTE] 編集中のデータを保存前に適用します")
            # save_changesメソッドを呼び出すためのダミーイベントを作成
            dummy_event = type('Event', (), {'page': self.page})()
            form_manager.save_changes(dummy_event)
        
        try:
            data_manager.save_json_file(file_path)
            
            # 削除フラグをリセット
            self.app_state["node_deleted_since_last_save"] = False
            
            # 編集状態をリセットして保存ボタンを無効化
            self.app_state["is_dirty"] = False
            
            # 詳細フォームの保存ボタンを無効化
            detail_save_button = self.ui_controls.get("detail_save_button")
            if detail_save_button:
                detail_save_button.disabled = True
                # ボタンがページに追加されている場合のみupdate()を呼ぶ
                try:
                    if hasattr(detail_save_button, 'page') and detail_save_button.page is not None:
                        detail_save_button.update()
                except Exception as update_ex:
                    print(f"[WARNING] 保存ボタンの更新に失敗: {update_ex}")
            
            # フィードバック表示
            # NotificationSystemを優先的に使用
            try:
                from notification_system import NotificationSystem
                notification_system = NotificationSystem(self.page)
                notification_system.show_ctrl_s_save()
                print("[OK] Ctrl+S保存の通知を表示しました（NotificationSystem）")
            except Exception as notif_ex:
                # フォールバック: FeedbackManagerを使用
                print(f"NotificationSystemエラー: {notif_ex}")
                feedback_manager = self.managers.get("feedback_manager")
                if feedback_manager:
                    feedback_manager.show_success(t("notification.file_saved_success").format(filename=os.path.basename(file_path)))
            
            return True
        except Exception as e:
            print(f"[ERROR] 保存エラー: {e}")
            feedback_manager = self.managers.get("feedback_manager")
            if feedback_manager:
                feedback_manager.show_error(t("error.save_failed").format(error=str(e)))
            return False
    
    def show_save_confirmation_dialog(self, file_path: str):
        """ノード削除後の保存確認ダイアログを表示する
        
        Args:
            file_path: 保存先のファイルパス
        """
        
        # 既にダイアログが表示されている場合は何もしない
        if self.app_state.get("confirmation_dialog_showing", False):
            print("[WARNING] ダイアログは既に表示されています")
            return
        
        self.app_state["confirmation_dialog_showing"] = True
        print("[OK] ダイアログ表示フラグをTrueに設定")
        
        def handle_confirm(e):
            """確認ボタンが押された時の処理"""
            self.app_state["confirmation_dialog_showing"] = False
            # オーバーレイから削除
            if overlay_container in self.page.overlay:
                self.page.overlay.remove(overlay_container)
            self.page.update()
            
            # 保存処理を実行
            if self.save_file_directly(file_path):
                # UIを更新
                ui_manager = self.managers.get("ui_manager")
                if ui_manager:
                    ui_manager.update_tree_view()
        
        def handle_cancel(e):
            """キャンセルボタンが押された時の処理"""
            self.app_state["confirmation_dialog_showing"] = False
            # オーバーレイから削除
            if overlay_container in self.page.overlay:
                self.page.overlay.remove(overlay_container)
            self.page.update()
        
        # ダイアログコンテナの作成（オーバーレイ用）
        dialog_content = ft.Container(
            content=ft.Column([
                ft.Text(t("dialog.confirm_save"), size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text(
                    t("dialog.confirm_save_message"),
                    size=14
                ),
                ft.Row([
                    ft.TextButton(t("dialog.cancel_button"), on_click=handle_cancel),
                    ft.ElevatedButton(
                        t("dialog.save_button"),
                        on_click=handle_confirm,
                        color=ft.Colors.RED
                    ),
                ], alignment=ft.MainAxisAlignment.END),
            ], spacing=10),
            padding=20,
            bgcolor=ft.Colors.SURFACE,
            border_radius=10,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            width=400,
            height=200,
        )
        
        # 背景を暗くするためのオーバーレイ
        overlay_container = ft.Container(
            content=ft.Stack([
                ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
                    expand=True,
                ),
                ft.Container(
                    content=dialog_content,
                    alignment=ft.alignment.center,
                    expand=True,
                ),
            ]),
            expand=True,
        )
        
        # オーバーレイに追加して表示
        try:
            self.page.overlay.append(overlay_container)
            self.page.update()
            print("[OK] オーバーレイを表示しました")
        except Exception as e:
            print(f"[ERROR] オーバーレイ表示エラー: {e}")
            import traceback
            traceback.print_exc()


def main(page: ft.Page):
    """
    アプリケーションのエントリーポイント

    Args:
        page (ft.Page): Fletページオブジェクト
    """
    app = FleDjSONApp(page)
    app.run()


# Fletアプリとして実行する場合のエントリーポイント
if __name__ == "__main__":
    import sys
    
    print("Starting FleDjSON...")
    print(f"System: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    
    # Python環境チェック
    if sys.version_info < (3, 12):
        print("\n[WARNING] このアプリケーションはPython 3.12以上が必要です")
        print("[ERROR] アプリケーションの起動に失敗しました")
        print("\n[CONFIG] 修正するには、以下のコマンドを実行してください:")
        print("1. pyenv global 3.12.3")
        print("2. poetry env use python3.12.3")
        print("3. poetry install")
        print("4. poetry run python src/app.py")
        sys.exit(1)
    
    print("[OK] Environment check passed")
    print("Launching application...\n")
    
    ft.app(target=main)