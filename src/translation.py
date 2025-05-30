"""
翻訳システムモジュール

アプリケーション全体の多言語対応を管理します。
日本語と英語の翻訳辞書を提供し、動的な言語切り替えをサポートします。
"""

from typing import Dict, Optional, Any
from logging_config import get_logger

logger = get_logger(__name__)


class TranslationSystem:
    """翻訳システムのシングルトンクラス"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._current_language = "ja"  # デフォルトは日本語
        
        # 翻訳辞書
        self._translations: Dict[str, Dict[str, str]] = {
            # メニュー項目
            "menu.file": {"ja": "ファイル", "en": "File"},
            "menu.file.open": {"ja": "開く", "en": "Open"},
            "menu.file.save": {"ja": "保存", "en": "Save"},
            "menu.file.save_as": {"ja": "名前を付けて保存", "en": "Save As"},
            "menu.file.export": {"ja": "エクスポート", "en": "Export"},
            "menu.file.recent": {"ja": "最近使用したファイル", "en": "Recent Files"},
            
            "menu.edit": {"ja": "編集", "en": "Edit"},
            "menu.edit.undo": {"ja": "元に戻す", "en": "Undo"},
            "menu.edit.redo": {"ja": "やり直し", "en": "Redo"},
            "menu.edit.copy": {"ja": "コピー", "en": "Copy"},
            "menu.edit.paste": {"ja": "貼り付け", "en": "Paste"},
            "menu.edit.delete": {"ja": "削除", "en": "Delete"},
            
            "menu.view": {"ja": "表示", "en": "View"},
            "menu.view.expand_all": {"ja": "すべて展開", "en": "Expand All"},
            "menu.view.collapse_all": {"ja": "すべて折りたたむ", "en": "Collapse All"},
            "menu.view.theme": {"ja": "テーマ", "en": "Theme"},
            
            # テーマ関連
            "theme.system": {"ja": "システム", "en": "System"},
            "theme.light": {"ja": "ライト", "en": "Light"},
            "theme.dark": {"ja": "ダーク", "en": "Dark"},
            "theme.fledjson": {"ja": "FleDjSON", "en": "FleDjSON"},
            "theme.language": {"ja": "Language / 言語", "en": "Language / 言語"},
            "theme.language.current_ja": {"ja": "日本語", "en": "日本語"},
            "theme.language.current_en": {"ja": "English", "en": "English"},
            
            # ボタンラベル
            "button.save": {"ja": "保存", "en": "Save"},
            "button.cancel": {"ja": "キャンセル", "en": "Cancel"},
            "button.add": {"ja": "項目を追加", "en": "Add Item"},
            "button.delete": {"ja": "削除", "en": "Delete"},
            "button.copy": {"ja": "コピー", "en": "Copy"},
            "button.edit": {"ja": "編集", "en": "Edit"},
            "button.close": {"ja": "閉じる", "en": "Close"},
            "button.ok": {"ja": "OK", "en": "OK"},
            "button.apply": {"ja": "適用", "en": "Apply"},
            "button.search": {"ja": "検索", "en": "Search"},
            "button.clear": {"ja": "クリア", "en": "Clear"},
            "button.select_file": {"ja": "ファイルを選択", "en": "Select File"},
            
            # フォームラベル
            "form.add_new_node": {"ja": "新規ノードを追加", "en": "Add New Node"},
            "form.edit_node": {"ja": "ノードを編集", "en": "Edit Node"},
            "form.node_details": {"ja": "ノードの詳細", "en": "Node Details"},
            "form.field_name": {"ja": "フィールド名", "en": "Field Name"},
            "form.field_value": {"ja": "値", "en": "Value"},
            "form.field_type": {"ja": "型", "en": "Type"},
            "form.add_field": {"ja": "フィールドを追加", "en": "Add Field"},
            "form.remove_field": {"ja": "フィールドを削除", "en": "Remove Field"},
            "form.select_node": {"ja": "ノードを選択してください", "en": "Please select a node"},
            
            # 編集画面のボタン
            "form.button.add_item": {"ja": "項目を追加", "en": "Add Item"},
            "form.button.save_changes": {"ja": "変更を保存", "en": "Save Changes"},
            "form.button.delete_node": {"ja": "ノードを削除", "en": "Delete Node"},
            "form.button.cancel": {"ja": "キャンセル", "en": "Cancel"},
            
            # 通知メッセージ
            "notification.file_loaded": {"ja": "ファイルを読み込みました", "en": "File loaded successfully"},
            "notification.file_saved": {"ja": "ファイルを保存しました", "en": "File saved successfully"},
            "notification.changes_saved": {"ja": "変更を保存しました", "en": "Changes saved"},
            "notification.changes_cancelled": {"ja": "変更をキャンセルしました", "en": "Changes cancelled"},
            "notification.add_mode_started": {"ja": "データ追加モードを開始しました", "en": "Add mode started"},
            "notification.add_mode_ended": {"ja": "データ追加モードを終了しました", "en": "Add mode ended"},
            "notification.item_added": {"ja": "項目を {path} に追加しました (保存が必要です)", "en": "Item added to {path} (save required)"},
            "notification.add_failed": {"ja": "項目の追加に失敗しました", "en": "Failed to add item"},
            
            # フォーム関連の詳細メッセージ
            "form.select_node_message": {"ja": "ノードを選択してください", "en": "Please select a node"},
            "form.node_data_error": {"ja": "ノードデータ表示エラー", "en": "Node data display error"},
            "form.dict_json_hint": {"ja": "辞書型JSONを入力 ({...})", "en": "Enter dictionary JSON ({...})"},
            "form.list_json_hint": {"ja": "リスト型JSONを入力 ([...])", "en": "Enter list JSON ([...])"},
            "form.dict_type": {"ja": "辞書型", "en": "Dictionary"},
            "form.list_type": {"ja": "リスト型", "en": "List"},
            "form.id_field_hint": {"ja": "IDフィールド", "en": "ID Field"},
            "form.delete_item_tooltip": {"ja": "項目{index}を削除", "en": "Delete item {index}"},
            "form.add_item_button": {"ja": "項目を追加", "en": "Add Item"},
            "form.add_item": {"ja": "ノードを追加", "en": "Add Node"},
            "form.field_name_label": {"ja": "フィールド名", "en": "Field Name"},
            "form.add_field_tooltip": {"ja": "フィールドを追加", "en": "Add Field"},
            "form.add_field_title": {"ja": "フィールドを追加", "en": "Add Field"},
            "form.delete_field_tooltip": {"ja": "{key}フィールドを削除", "en": "Delete {key} field"},
            "form.input_hint": {"ja": "入力: {type}", "en": "Input: {type}"},
            "form.enter_value": {"ja": "値を入力", "en": "Enter value"},
            "form.error": {"ja": "エラー", "en": "Error"},
            
            # エラーメッセージ
            "error.file_not_selected": {"ja": "JSONファイルを選択してから新規追加を行ってください", "en": "Please select a JSON file before adding new data"},
            "error.id_already_used": {"ja": "このIDは既に使用されています", "en": "This ID is already in use"},
            "error.invalid_format": {"ja": "無効な形式 ({type}型)", "en": "Invalid format ({type} type)"},
            "error.no_changes_to_save": {"ja": "保存する変更がありません", "en": "No changes to save"},
            "error.no_node_selected": {"ja": "エラー: ノードが選択されていません", "en": "Error: No node selected"},
            "error.node_data_not_found": {"ja": "エラー: ノードデータが見つかりません", "en": "Error: Node data not found"},
            "error.id_in_use": {"ja": "エラー: ID '{id}' は既に使用されています", "en": "Error: ID '{id}' is already in use"},
            "error.not_list_type": {"ja": "エラー: {path} はリストではありません", "en": "Error: {path} is not a list"},
            "error.list_item_add": {"ja": "リスト項目追加中にエラー: {error}", "en": "Error adding list item: {error}"},
            "error.list_item_delete": {"ja": "リスト項目削除中にエラー: {error}", "en": "Error deleting list item: {error}"},
            "error.field_delete_failed": {"ja": "フィールドの削除に失敗しました: {error}", "en": "Failed to delete field: {error}"},
            "error.node_add_failed": {"ja": "新規ノードの追加に失敗しました: {error}", "en": "Failed to add new node: {error}"},
            "error.no_data_to_add": {"ja": "追加するデータがありません", "en": "No data to add"},
            "error.invalid_id_value": {"ja": "IDフィールド '{field}' に有効な値を設定してください", "en": "Please set a valid value for ID field '{field}'"},
            "error.id_duplicate": {"ja": "ID '{id}' は既に使用されています。別のIDを指定してください。", "en": "ID '{id}' is already in use. Please specify a different ID."},
            
            # フォームタイトル・説明
            "form.new_node_title": {"ja": "新規ノードの作成", "en": "Create New Node"},
            "form.new_node_description": {"ja": "下記フォームに入力して「追加」ボタンをクリックしてください", "en": "Fill out the form below and click the 'Add' button"},
            "form.template_title": {"ja": "新規データ作成 (テンプレート使用)", "en": "Create New Data (Using Template)"},
            "form.template_description": {"ja": "テンプレートに基づいて新しいデータを作成します。必須フィールドと推奨フィールドが事前入力されています。", "en": "Create new data based on template. Required and recommended fields are pre-filled."},
            "form.save_changes": {"ja": "変更を保存", "en": "Save Changes"},
            "form.cancel": {"ja": "取り消し", "en": "Cancel"},
            "form.delete_node": {"ja": "ノードを削除", "en": "Delete Node"},
            
            # 通知メッセージの詳細
            "notification.auto_align_ids": {"ja": "ノードを並び替え、{count}個のIDを自動的に整列しました", "en": "Reordered nodes and automatically aligned {count} IDs"},
            "notification.field_added": {"ja": "フィールド '{field}' を追加しました", "en": "Field '{field}' added"},
            "notification.auto_renumber_enabled": {"ja": "自動連番機能を有効にしました", "en": "Auto renumbering enabled"},
            "notification.auto_renumber_disabled": {"ja": "自動連番機能を無効にしました", "en": "Auto renumbering disabled"},
            "notification.save_failed": {"ja": "保存に失敗しました: {error}", "en": "Failed to save: {error}"},
            "notification.file_save_failed_detail": {"ja": "ファイル保存に失敗: {filename}", "en": "Failed to save file: {filename}"},
            "notification.directory_created": {"ja": "保存先フォルダ '{folder}' を作成しました", "en": "Created destination folder '{folder}'"},
            "notification.backup_created": {"ja": "バックアップファイルを作成しました: {filename}", "en": "Created backup file: {filename}"},
            "notification.file_not_found": {"ja": "ファイル '{filename}' が見つかりません。", "en": "File '{filename}' not found."},
            "notification.partial_save_warning": {"ja": "一部エラーがありましたが保存しました ({errors})", "en": "Saved with some errors ({errors})"},
            "notification.item_added_success": {"ja": "項目を {path} に追加しました (保存が必要です)", "en": "Item added to {path} (save required)"},
            "notification.item_delete_recorded": {"ja": "項目 {index} の削除を記録しました (保存が必要です)", "en": "Recorded deletion of item {index} (save required)"},
            "notification.new_item_added": {"ja": "新しい項目を {path} に追加しました", "en": "New item added to {path}"},
            "notification.item_add_failed": {"ja": "項目の追加に失敗しました: {error}", "en": "Failed to add item: {error}"},
            "notification.item_deleted": {"ja": "項目 {index} を削除しました", "en": "Deleted item {index}"},
            "notification.item_not_found": {"ja": "削除する項目が見つかりませんでした: {path}[{index}]", "en": "Item to delete not found: {path}[{index}]"},
            "notification.item_delete_failed": {"ja": "項目の削除に失敗しました: {error}", "en": "Failed to delete item: {error}"},
            "notification.node_added_success": {"ja": "新しいノードを追加しました (ID: {id})", "en": "New node added (ID: {id})"},
            "notification.node_deleted_success": {"ja": "ノード '{id}' を削除しました", "en": "Node '{id}' deleted"},
            "notification.node_deleted_with_children": {"ja": "ノード '{id}' とその子孫 ({count}個) を削除しました", "en": "Node '{id}' and its {count} descendants deleted"},
            "notification.node_id_deleted": {"ja": "ノードID '{id}' を削除しました", "en": "Node ID '{id}' deleted"},
            "notification.field_deleted": {"ja": "'{field}' フィールドを削除しました", "en": "'{field}' field deleted"},
            "notification.field_added": {"ja": "フィールド '{field}' を追加しました", "en": "Field '{field}' added"},
            
            # ダイアログ
            "dialog.field_delete_title": {"ja": "フィールドの削除", "en": "Delete Field"},
            "dialog.field_delete_message": {"ja": "'{field}'フィールドを削除しますか？", "en": "Delete '{field}' field?"},
            "dialog.yes": {"ja": "はい", "en": "Yes"},
            "dialog.no": {"ja": "いいえ", "en": "No"},
            "dialog.close": {"ja": "閉じる", "en": "Close"},
            
            # UI Manager関連
            "ui.move_mode_warning": {"ja": "移動モード中は編集できません。編集するには移動ロックをオンにしてください。", "en": "Cannot edit while in move mode. Turn on move lock to edit."},
            "ui.drag_drop_unavailable": {"ja": "ドラッグ＆ドロップ機能は現在利用できません。", "en": "Drag & drop functionality is currently unavailable."},
            "ui.no_data_loaded": {"ja": "データがロードされていません。JSONファイルを選択してください。", "en": "No data loaded. Please select a JSON file."},
            "ui.select_node": {"ja": "ノードを選択してください", "en": "Please select a node"},
            "ui.tree_display_error": {"ja": "[WARNING] データ構造を表示できませんでした", "en": "[WARNING] Failed to display data structure"},
            "ui.move_mode_add_disabled": {"ja": "移動モード中は追加モードを使用できません。編集モードに切り替えてください。", "en": "Cannot use add mode while in move mode. Please switch to edit mode."},
            "notification.node_added": {"ja": "ノードを追加しました", "en": "Node added"},
            "notification.node_deleted": {"ja": "ノードを削除しました", "en": "Node deleted"},
            "notification.node_copied": {"ja": "ノードをコピーしました", "en": "Node copied"},
            "notification.error_occurred": {"ja": "エラーが発生しました", "en": "An error occurred"},
            "notification.operation_cancelled": {"ja": "操作がキャンセルされました", "en": "Operation cancelled"},
            "notification.ctrl_s_save": {"ja": "上書き保存しました", "en": "Overwrite Saved"},
            "notification.language_changed": {"ja": "言語を変更しました", "en": "Language changed"},
            "notification.file_load_cancelled": {"ja": "ファイル読み込みがキャンセルされました", "en": "File loading was cancelled"},
            "notification.file_save_cancelled": {"ja": "ファイル保存がキャンセルされました", "en": "File saving was cancelled"},
            "notification.file_save_success": {"ja": "ファイルを保存しました", "en": "File saved successfully"},
            "notification.file_save_error": {"ja": "ファイルの保存中にエラーが発生しました", "en": "An error occurred while saving the file"},
            "notification.file_saved": {"ja": "ファイルを保存しました: {filename}", "en": "File saved: {filename}"},
            "notification.file_save_failed": {"ja": "ファイルの保存に失敗しました: {error}", "en": "Failed to save file: {error}"},
            "notification.file_loaded": {"ja": "ファイル '{filename}' を読み込みました", "en": "File '{filename}' loaded"},
            "notification.no_data_to_add": {"ja": "追加するデータがありません", "en": "No data to add"},
            "notification.id_field_required": {"ja": "IDフィールド '{field}' に有効な値を設定してください", "en": "Please set a valid value for ID field '{field}'"},
            "notification.id_already_exists": {"ja": "ID '{id}' は既に使用されています。別のIDを指定してください。", "en": "ID '{id}' is already in use. Please specify a different ID."},
            "notification.new_node_add_failed": {"ja": "新規ノードの追加に失敗しました: {error}", "en": "Failed to add new node: {error}"},
            "notification.field_delete_failed": {"ja": "フィールドの削除に失敗しました: {error}", "en": "Failed to delete field: {error}"},
            
            # エラーメッセージ
            "error.file_not_found": {"ja": "ファイルが見つかりません", "en": "File not found"},
            "error.invalid_json": {"ja": "無効なJSONフォーマットです", "en": "Invalid JSON format"},
            "error.save_failed": {"ja": "保存に失敗しました", "en": "Failed to save"},
            "error.load_failed": {"ja": "読み込みに失敗しました", "en": "Failed to load"},
            "error.file_load_failed": {"ja": "ファイルの読み込みに失敗しました: {error}", "en": "Failed to load file: {error}"},
            "error.json_load_failed": {"ja": "JSONファイルの読み込みに失敗しました: {error}", "en": "Failed to load JSON file: {error}"},
            "error.json_processing_failed": {"ja": "JSONファイルの処理に失敗しました: {error}", "en": "Failed to process JSON file: {error}"},
            "error.file_loading_error": {"ja": "ファイルの読み込み中にエラーが発生しました: {error}", "en": "An error occurred while loading the file: {error}"},
            "error.file_saving_error": {"ja": "ファイル保存中にエラーが発生しました: {error}", "en": "An error occurred while saving the file: {error}"},
            "error.json_parse_failed": {"ja": "JSONの解析に失敗しました: {error}", "en": "Failed to parse JSON: {error}"},
            "error.json_parse_location": {"ja": "行 {line}, 列 {col}", "en": "Line {line}, Column {col}"},
            "error.file_write_failed": {"ja": "ファイルの書き込みに失敗しました: {error}", "en": "Failed to write file: {error}"},
            "error.directory_create_failed": {"ja": "保存先フォルダの作成に失敗しました: {error}", "en": "Failed to create destination folder: {error}"},
            "error.analysis_structure_failed": {"ja": "データ構造の解析に失敗しました。IDフィールドなどが正しく特定できていない可能性があります。", "en": "Failed to analyze data structure. ID fields may not be correctly identified."},
            "error.json_analysis_failed": {"ja": "JSONの解析に失敗しました: {error}", "en": "Failed to analyze JSON: {error}"},
            "error.general_error": {"ja": "エラーが発生しました: {error}", "en": "An error occurred: {error}"},
            "error.settings_save_failed": {"ja": "設定の保存に失敗しました: {error}", "en": "Failed to save settings: {error}"},
            "error.io_failed": {"ja": "JSONファイルの読み込みに失敗しました: {error}", "en": "Failed to read JSON file: {error}"},
            "error.partial_load_failed": {"ja": "部分読み込みに失敗しました: {error}", "en": "Failed to load partial data: {error}"},
            "error.permission_denied": {"ja": "アクセスが拒否されました", "en": "Permission denied"},
            "error.unknown_error": {"ja": "不明なエラーが発生しました", "en": "Unknown error occurred"},
            "error.no_data_to_save": {"ja": "保存するデータがありません", "en": "No data to save"},
            "error.no_file_to_save": {"ja": "保存するファイルがありません", "en": "No file to save"},
            "error.no_data": {"ja": "エラー: データがありません。", "en": "Error: No data available."},
            "error.structure_build_failed": {"ja": "エラー: データ構造を構築できませんでした。", "en": "Error: Failed to build data structure."},
            "error.tree_build_failed": {"ja": "ツリービューの構築エラー", "en": "Tree view build error"},
            "error.tree_display_failed": {"ja": "ツリー表示エラー", "en": "Tree display error"},
            "error.analysis_failed": {"ja": "エラー: {error}", "en": "Error: {error}"},
            "error.node_not_found": {"ja": "エラー: ノードデータが見つかりません (ID: {id})", "en": "Error: Node data not found (ID: {id})"},
            "error.id_already_used": {"ja": "エラー: ID '{id}' は既に使用されています", "en": "Error: ID '{id}' is already in use"},
            "error.not_list": {"ja": "エラー: {path} はリストではありません", "en": "Error: {path} is not a list"},
            "error.list_operation": {"ja": "リスト項目{operation}中にエラー: {error}", "en": "Error during list item {operation}: {error}"},
            "error.field_info_missing": {"ja": "フィールド情報が不足しています", "en": "Field information is missing"},
            "error.general": {"ja": "エラーが発生しました: {error}", "en": "An error occurred: {error}"},
            "error.cannot_drop_self": {"ja": "自分自身の上にはドロップできません", "en": "Cannot drop on itself"},
            "error.cannot_drop_descendant": {"ja": "自分の子孫ノードを親にすることはできません", "en": "Cannot make a descendant node a parent"},
            
            # ダイアログ
            "dialog.confirm_delete": {"ja": "削除の確認", "en": "Confirm Delete"},
            "dialog.confirm_delete_message": {"ja": "このノードを削除してもよろしいですか？", "en": "Are you sure you want to delete this node?"},
            "dialog.confirm_delete_question": {"ja": "本当にこのノードを削除しますか？", "en": "Are you sure you want to delete this node?"},
            "dialog.delete_warning": {"ja": "注意: この操作は元に戻せません。このノードの子ノードもすべて削除されます。", "en": "Warning: This operation cannot be undone. All child nodes will also be deleted."},
            "dialog.delete_button": {"ja": "はい、削除します", "en": "Yes, Delete"},
            "dialog.unsaved_changes": {"ja": "未保存の変更", "en": "Unsaved Changes"},
            "dialog.unsaved_changes_message": {"ja": "保存されていない変更があります。保存しますか？", "en": "You have unsaved changes. Do you want to save them?"},
            "dialog.save_as_title": {"ja": "名前を付けて保存", "en": "Save As"},
            "dialog.open_file": {"ja": "JSONファイルを開く", "en": "Open JSON File"},
            "dialog.confirm_save": {"ja": "保存の確認", "en": "Confirm Save"},
            "dialog.confirm_save_message": {"ja": "データが削除されています。\nこのまま保存すると、削除した内容が確定されます。\n本当に保存しますか？", "en": "Data has been deleted.\nSaving now will confirm the deletion.\nAre you sure you want to save?"},
            "dialog.save_button": {"ja": "保存する", "en": "Save"},
            "dialog.cancel_button": {"ja": "キャンセル", "en": "Cancel"},
            "dialog.delete_confirmation": {"ja": "ノードを削除しますか？", "en": "Are you sure you want to delete this node?"},
            "dialog.delete_warning": {"ja": "この操作は取り消せません。", "en": "This action cannot be undone."},
            "dialog.delete_button": {"ja": "削除", "en": "Delete"},
            
            # ステータス
            "status.ready": {"ja": "準備完了", "en": "Ready"},
            "status.loading": {"ja": "読み込み中...", "en": "Loading..."},
            "status.saving": {"ja": "保存中...", "en": "Saving..."},
            "status.editing": {"ja": "編集中", "en": "Editing"},
            "status.saved": {"ja": "保存済み", "en": "Saved"},
            
            # ローディング
            "loading.processing": {"ja": "処理中...", "en": "Processing..."},
            "loading.starting": {"ja": "を開始しています...", "en": " starting..."},
            "loading.completed": {"ja": "が完了しました", "en": " completed"},
            "loading.cancelled": {"ja": "キャンセルされました", "en": "Cancelled"},
            "loading.error": {"ja": "でエラーが発生しました", "en": " error occurred"},
            "loading.file_loading": {"ja": "ファイルの読み込み: {filename}", "en": "Loading file: {filename}"},
            "loading.file_saving": {"ja": "ファイルの保存: {filename}", "en": "Saving file: {filename}"},
            "loading.loading_file": {"ja": "{filename}を読み込んでいます...", "en": "Loading {filename}..."},
            "loading.saving_file": {"ja": "{filename}を保存しています...", "en": "Saving {filename}..."},
            "loading.analyzing_file": {"ja": "{filename}を解析しています...", "en": "Analyzing {filename}..."},
            "loading.processing_data": {"ja": "データを処理しています...", "en": "Processing data..."},
            "loading.validating_data": {"ja": "データを検証しています...", "en": "Validating data..."},
            "loading.writing_data": {"ja": "データを書き込んでいます...", "en": "Writing data..."},
            "loading.analyzing": {"ja": "解析中... ファイルサイズ: {size} MB, 推定アイテム数: {items}", "en": "Analyzing... File size: {size} MB, Estimated items: {items}"},
            
            # 基本UI要素
            "tree.no_data": {"ja": "ツリービューがここに表示されます...", "en": "Tree view will appear here..."},
            
            # 解析結果
            "analysis.json_data": {"ja": "件のJSONデータ", "en": "JSON data items"},
            "analysis.record_count": {"ja": "{count}件のJSONデータ", "en": "{count} JSON data items"},
            "analysis.placeholder": {"ja": "json解析結果を表示", "en": "Display JSON analysis results"},
            "analysis.complete_no_data": {"ja": "[FILE] {filename} | 解析完了: ID={id}, データなし", "en": "[FILE] {filename} | Analysis complete: ID={id}, No data"},
            "analysis.result_summary": {"ja": "[DATA] 解析結果: {data_count} 件のデータ、{node_count} ノード、最大深さ {max_depth}、{field_count} フィールド", "en": "[DATA] Analysis result: {data_count} data items, {node_count} nodes, max depth {max_depth}, {field_count} fields"},
            "analysis.key_info": {"ja": "[KEY] ID: {id_key}, ラベル: {label_key}, 子要素: {children_key}", "en": "[KEY] ID: {id_key}, Label: {label_key}, Children: {children_key}"},
            
            # チェックボックス
            "checkbox.move_lock": {"ja": "移動ロック", "en": "Move Lock"},
            "checkbox.auto_renumber": {"ja": "自動連番", "en": "Auto Renumber"},
            
            # ツールチップ
            "tooltip.open_file": {"ja": "JSONファイルを開く", "en": "Open JSON file"},
            "tooltip.move_lock": {"ja": "ツリーノードのドラッグ＆ドロップによる移動をロック/解除します", "en": "Lock/unlock drag & drop movement of tree nodes"},
            "tooltip.auto_renumber": {"ja": "ドラッグ＆ドロップ後に兄弟ノードのIDを自動的に連番に整列します", "en": "Automatically renumber sibling node IDs after drag & drop"},
            "tooltip.lock_on": {"ja": "ロック中 (移動不可)", "en": "Locked (movement disabled)"},
            "tooltip.lock_off": {"ja": "解除中 (移動可能)", "en": "Unlocked (movement enabled)"},
            "tooltip.save_file": {"ja": "変更を保存", "en": "Save changes"},
            "tooltip.add_node": {"ja": "新しいノードを追加", "en": "Add new node"},
            "tooltip.delete_node": {"ja": "選択したノードを削除", "en": "Delete selected node"},
            "tooltip.expand_all": {"ja": "すべてのノードを展開", "en": "Expand all nodes"},
            "tooltip.collapse_all": {"ja": "すべてのノードを折りたたむ", "en": "Collapse all nodes"},
            "tooltip.search": {"ja": "ノードを検索", "en": "Search nodes"},
            
            # プレースホルダー
            "placeholder.search": {"ja": "検索", "en": "Search"},
            "placeholder.field_name": {"ja": "フィールド名を入力", "en": "Enter field name"},
            "placeholder.field_value": {"ja": "値を入力", "en": "Enter value"},
            
            # 検索関連
            "search.window_title": {"ja": "検索", "en": "Search"},
            "search.results_count": {"ja": "{count}件の結果", "en": "{count} results"},
            "search.no_results": {"ja": "結果が見つかりません", "en": "No results found"},
            
            # その他
            "app.title": {"ja": "FleDjSON - JSONエディタ", "en": "FleDjSON - JSON Editor"},
            "tree.root": {"ja": "ルート", "en": "Root"},
            "tree.array_item": {"ja": "要素", "en": "Item"},
            "tree.empty": {"ja": "(空)", "en": "(empty)"},
            "tree.no_data": {"ja": "データがありません", "en": "No data"},
            "tooltip.delete_field": {"ja": "{field}フィールドを削除", "en": "Delete {field} field"},
            "search.result_count": {"ja": "{count}件", "en": "{count} items"},
            "field.recommended": {"ja": "{field} (推奨)", "en": "{field} (Recommended)"},
            "event.error_category": {"ja": "{category}エラーが発生しました", "en": "{category} error occurred"},
            "event.error_recovery": {"ja": "エラー回復が{status}されました", "en": "Error recovery {status}"},
            "dialog.save_question": {"ja": "ファイル '{filename}' に保存しますか？", "en": "Save to file '{filename}'?"},
            "error.node_not_found_detail": {"ja": "ノードデータが見つかりません (ID: {id})", "en": "Node data not found (ID: {id})"},
            "error.id_already_exists": {"ja": "ID '{id}' は既に使用されています", "en": "ID '{id}' is already in use"},
            
            # チェックボックス
            "checkbox.move_lock": {"ja": "移動ロック", "en": "Move Lock"},
            "checkbox.auto_renumber": {"ja": "自動連番", "en": "Auto Renumber"},
            
            # 追加のツールチップ
            "tooltip.move_lock": {"ja": "ツリーノードのドラッグ＆ドロップによる移動をロック/解除します", "en": "Lock/unlock drag-and-drop movement of tree nodes"},
            "tooltip.auto_renumber": {"ja": "ドラッグ＆ドロップ後に兄弟ノードのIDを自動的に連番に整列します", "en": "Automatically renumber sibling node IDs after drag-and-drop"},
            "tooltip.lock_on": {"ja": "ロック中 (移動不可)", "en": "Locked (cannot move)"},
            "tooltip.lock_off": {"ja": "解除中 (移動可能)", "en": "Unlocked (can move)"},
            
            # 自動連番機能
            "feature.auto_renumber_enabled": {"ja": "自動連番機能を有効にしました", "en": "Auto renumber enabled"},
            "feature.auto_renumber_disabled": {"ja": "自動連番機能を無効にしました", "en": "Auto renumber disabled"},
            
            # ファイル保存通知
            "notification.file_saved_success": {"ja": "ファイル '{filename}' を保存しました", "en": "File '{filename}' saved successfully"},
            "error.save_failed": {"ja": "保存に失敗しました: {error}", "en": "Failed to save: {error}"},
            
            # 最適化関連
            "error.json_load_failed": {"ja": "JSONファイルの読み込みに失敗しました: {error}", "en": "Failed to load JSON file: {error}"},
            "error.partial_load_failed": {"ja": "部分読み込みに失敗しました: {error}", "en": "Failed to load partial data: {error}"},
        }
        
        logger.info(f"Translation system initialized with language: {self._current_language}")
    
    def set_language(self, language: str) -> None:
        """言語を設定"""
        if language not in ["ja", "en"]:
            logger.warning(f"Invalid language code: {language}, defaulting to 'ja'")
            language = "ja"
        
        self._current_language = language
        logger.info(f"Language changed to: {language}")
    
    def get_language(self) -> str:
        """現在の言語を取得"""
        return self._current_language
    
    def t(self, key: str, default: Optional[str] = None) -> str:
        """
        翻訳を取得
        
        Args:
            key: 翻訳キー（ドット記法）
            default: 翻訳が見つからない場合のデフォルト値
        
        Returns:
            翻訳されたテキスト
        """
        if key in self._translations:
            translation = self._translations[key].get(self._current_language)
            if translation:
                return translation
            
            # 現在の言語で翻訳が見つからない場合は日本語にフォールバック
            japanese = self._translations[key].get("ja")
            if japanese:
                logger.debug(f"Translation not found for key '{key}' in '{self._current_language}', falling back to Japanese")
                return japanese
        
        # 翻訳が見つからない場合
        if default:
            return default
        
        logger.warning(f"Translation not found for key: {key}")
        return key  # キーをそのまま返す
    
    def get_all_by_prefix(self, prefix: str) -> Dict[str, str]:
        """
        指定されたプレフィックスで始まるすべての翻訳を取得
        
        Args:
            prefix: キーのプレフィックス
        
        Returns:
            プレフィックスに一致する翻訳の辞書
        """
        result = {}
        for key, translations in self._translations.items():
            if key.startswith(prefix):
                result[key] = translations.get(self._current_language, key)
        return result


# シングルトンインスタンスを作成
_translation_system = TranslationSystem()


# 便利な関数を公開
def t(key: str, default: Optional[str] = None) -> str:
    """翻訳を取得するショートカット関数"""
    return _translation_system.t(key, default)


def set_language(language: str) -> None:
    """言語を設定"""
    _translation_system.set_language(language)


def get_language() -> str:
    """現在の言語を取得"""
    return _translation_system.get_language()


def get_translation_system() -> TranslationSystem:
    """翻訳システムのインスタンスを取得"""
    return _translation_system