"""
data_manager.py
JSONデータの読み込み・操作・保存関連のマネージャークラス

FleDjSONのJSONデータ管理を担当する
データの読み込み、更新、保存、構造マッピングなどの機能を提供する
"""
import flet as ft
from flet import Colors
from typing import Optional, Any, Dict, List, Union, Tuple, Callable, Set
import json
import os
import uuid
import copy
import gc
import time
from datetime import datetime
import re
import traceback
from collections import defaultdict

# 最適化モジュールをインポート
from optimizations import (
    LazyJSONLoader, CachedDataManager, BackgroundProcessor,
    memoize, performance_log
)

# ロギング設定をインポート
from logging_config import get_logger

# 翻訳システムをインポート
from translation import t

# JSON平坦化モジュールをインポート
from flatten_json import try_flatten_json

# ロガーの取得
logger = get_logger(__name__)


class DataManager:
    """
    JSONデータの読み込み、操作、保存を担当するマネージャークラス
    
    JSONデータの読み込み、パース、更新、保存などのデータ操作を一元管理する
    データマップとツリー構造の構築と管理も担当する
    
    Attributes:
        app_state (Dict): アプリケーションの状態を保持する辞書
        ui_controls (Dict): UIコントロールを保持する辞書
        page (ft.Page): Fletページオブジェクト
    """
    
    def __init__(self, app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None):
        """
        DataManagerを初期化します。

        Args:
            app_state (Dict): アプリケーションの状態を保持する辞書
            ui_controls (Dict): UIコントロールを保持する辞書
            page (ft.Page, optional): Fletページオブジェクト
        """
        self.app_state = app_state
        self.ui_controls = ui_controls
        self.page = page or app_state.get("page")
        
        # パス解決用の正規表現
        self.key_path_regex = re.compile(r'\.|\[(\d+)\]')
        
        # 最適化のためのコンポーネント
        self.cache_manager = CachedDataManager(cache_size=500)
        self.background_processor = BackgroundProcessor()
        self._lazy_loaders = {}
        
        # ステータス変数
        self._is_large_file = False
        self._loading_canceled = False
        self._loading_task_id = None
        
        # イベント通知のためのコールバック
        self._on_data_loaded_callback = None
        self._on_data_updated_callback = None
        
        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] DataManager initialized with optimizations enabled.")
    
    @performance_log(label="Load JSON File")
    def load_json_file(self, file_path: str) -> bool:
        """
        JSONファイルを読み込み、解析する
        
        Args:
            file_path: 読み込むJSONファイルのパス
            
        Returns:
            成功した場合はTrue、失敗した場合はFalse
        """
        try:
            logger.info(f"Loading JSON file: {file_path}")
            
            # UIの読み込み状態を更新
            self._set_loading_state(True, "JSONファイルを読み込み中...")
            
            # ファイルサイズを確認して読み込み方法を決定
            file_size = os.path.getsize(file_path)
            self._is_large_file = file_size > 10 * 1024 * 1024  # 10MB以上を大きなファイルとみなす
            
            if self._is_large_file:
                # 大きなファイルの場合、LazyJSONLoaderを使用
                logger.info(f"Large file detected ({file_size / 1024 / 1024:.2f} MB). Using optimized loading.")
                
                # LazyJSONLoaderの作成
                loader = LazyJSONLoader(file_path)
                self._lazy_loaders[file_path] = loader
                
                # 構造情報を取得
                structure = loader.get_structure()
                
                if "error" in structure:
                    raise ValueError(f"Failed to analyze file structure: {structure['error']}")
                
                # バックグラウンドで読み込みを開始
                self._loading_task_id = self.background_processor.submit(
                    self._load_large_file_async,
                    self._on_large_file_loaded,
                    self._on_loading_error,
                    file_path, loader
                )
                
                # 一時的な状態を設定
                self.app_state["current_file"] = file_path
                self.app_state["selected_node_id"] = None
                self.app_state["is_loading"] = True
                
                # UIコントロールの状態更新
                if "selected_file_path_text" in self.ui_controls and self.ui_controls["selected_file_path_text"]:
                    self.ui_controls["selected_file_path_text"].value = os.path.basename(file_path)
                    self.ui_controls["selected_file_path_text"].update()
                
                # 最初のメタデータをもとに仮の解析結果を生成
                self._set_preliminary_analysis(structure)
                
                return True
                
            else:
                # 通常のファイルの場合、直接読み込む
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                return self._process_loaded_data(file_path, data)
                
        except Exception as e:
            self._set_loading_state(False)
            error_message = t("error.json_load_failed").format(error=str(e))
            logger.error(error_message)
            
            # エラーメッセージを表示
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(error_message),
                    bgcolor=ft.Colors.RED,
                    action=t("dialog.close")
                )
                self.page.snack_bar.open = True
                self.page.update()
            
            return False
        finally:
            # 最後に読み込み状態を解除
            self._set_loading_state(False)
    
    def _load_large_file_async(self, file_path: str, loader: LazyJSONLoader) -> Dict[str, Any]:
        """バックグラウンドで大きなJSONファイルを読み込む"""
        # スレッドでの処理なので、UIを直接更新しないよう注意
        try:
            # キャンセルフラグのチェック
            if self._loading_canceled:
                return {"status": "canceled", "file_path": file_path}
            
            # データを読み込む
            data = loader.load_full()
            
            # メモリ使用量を削減するためにキャッシュをクリア
            gc.collect()
            
            return {
                "status": "success",
                "file_path": file_path,
                "data": data
            }
            
        except Exception as e:
            return {
                "status": "error",
                "file_path": file_path,
                "error": str(e)
            }
    
    def _on_large_file_loaded(self, result: Dict[str, Any]) -> None:
        """大きなファイルの読み込みが完了したときに呼び出されるコールバック"""
        if result["status"] == "canceled":
            logger.info("File loading was canceled.")
            return
            
        if result["status"] == "error":
            self._set_loading_state(False)
            error_message = t("error.json_load_failed").format(error=result['error'])
            logger.error(error_message)
            
            # エラーメッセージを表示
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(error_message),
                    bgcolor=ft.Colors.RED,
                    action=t("dialog.close")
                )
                self.page.snack_bar.open = True
                self.page.update()
            
            return
        
        # データの処理を続行
        self._process_loaded_data(result["file_path"], result["data"])
    
    def _on_loading_error(self, error: Exception) -> None:
        """読み込み中にエラーが発生したときに呼び出されるコールバック"""
        self._set_loading_state(False)
        error_message = t("error.file_loading_error").format(error=str(error))
        logger.error(error_message)
        
        # エラーメッセージを表示
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(error_message),
                bgcolor=ft.Colors.RED,
                action=t("dialog.close")
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    def _set_loading_state(self, is_loading: bool, message: str = None) -> None:
        """読み込み状態を設定する"""
        self.app_state["is_loading"] = is_loading
        
        # ローディングインジケータの表示/非表示
        loading_indicator = self.ui_controls.get("loading_indicator")
        if loading_indicator:
            if message and is_loading:
                # メッセージ内容を更新
                if isinstance(loading_indicator.content, ft.Row) and len(loading_indicator.content.controls) > 0:
                    loading_indicator.content.controls[0].value = message
            
            loading_indicator.visible = is_loading
            loading_indicator.update()
    
    def _set_preliminary_analysis(self, structure: Dict[str, Any]) -> None:
        """大きなファイルの読み込み中に仮の解析結果を設定する"""
        preliminary_analysis = {
            "structure_type": structure.get("type", "unknown"),
            "file_size": structure.get("file_size", 0),
            "estimated_items": structure.get("estimated_items"),
            "preliminary": True
        }
        
        self.app_state["preliminary_analysis"] = preliminary_analysis
        
        # 解析結果のテキストを更新
        analysis_text = self.ui_controls.get("analysis_result_summary_text")
        if analysis_text:
            file_size_mb = structure.get("file_size", 0) / 1024 / 1024
            estimated_items = structure.get("estimated_items", "不明")
            
            analysis_text.value = t("loading.analyzing").format(size=f"{file_size_mb:.2f}", items=estimated_items)
            analysis_text.update()
    
    def _update_analysis_result_display(self, analysis_results: Dict[str, Any]) -> None:
        """解析結果をUIに表示する"""
        analysis_text = self.ui_controls.get("analysis_result_summary_text")
        if analysis_text and analysis_results:
            # データ構造からキー一覧を生成
            data_map = self.app_state.get("data_map", {})
            
            
            if data_map:
                # 最初のアイテムからキー構造を取得
                first_item = next(iter(data_map.values()), {})
                
                # 構造解析結果を生成
                structure_info = []
                
                # 基本統計
                item_count = len(data_map)
                root_count = len(self.app_state.get("root_ids", []))
                
                # キー情報
                id_key = analysis_results.get("id_key", "不明")
                label_key = analysis_results.get("label_key", "不明") 
                children_key = analysis_results.get("children_key", "不明")
                
                # 主要フィールド一覧（最初のアイテムから）
                main_keys = []
                if isinstance(first_item, dict):
                    for key in list(first_item.keys())[:6]:  # 最大6個のキーを表示
                        if isinstance(first_item[key], dict):
                            # ネストしたオブジェクトの場合
                            nested_keys = list(first_item[key].keys())[:3]  # 最大3個
                            nested_str = ', '.join(nested_keys)
                            if len(first_item[key]) > 3:
                                nested_str += "..."
                            main_keys.append(f"{key}({nested_str})")
                        elif isinstance(first_item[key], list):
                            # 配列の場合
                            array_len = len(first_item[key])
                            main_keys.append(f"{key}[{array_len}]")
                        else:
                            # プリミティブ値の場合
                            main_keys.append(key)
                
                # 複数行の構造化表示を構成
                # 現在のファイル名を取得
                current_file = self.app_state.get("current_file", "")
                file_name = os.path.basename(current_file) if current_file else "不明"
                
                line1 = f"[FILE] {file_name} | [DATA] {t('analysis.record_count').format(count=item_count)}"
                line2 = f"[KEY] {', '.join(main_keys[:6])}" + ("..." if len(main_keys) > 6 else "")
                
                # 3行目: キー設定情報
                key_info_parts = [f"ID={id_key}", f"Label={label_key}"]
                if children_key != "不明":
                    key_info_parts.append(f"Children={children_key}")
                line3 = f"[TARGET] {', '.join(key_info_parts)}"
                
                # 3行に分けて表示
                analysis_text.value = f"{line1}\n{line2}\n{line3}"
            else:
                # データマップが空の場合、raw_dataから直接構造情報を取得
                raw_data = self.app_state.get("raw_data", [])
                
                if raw_data and isinstance(raw_data, list) and len(raw_data) > 0:
                    first_item = raw_data[0] if isinstance(raw_data[0], dict) else {}
                    
                    # 基本統計
                    item_count = len(raw_data)
                    
                    # キー情報
                    id_key = analysis_results.get("id_key", "不明")
                    label_key = analysis_results.get("label_key", "不明") 
                    children_key = analysis_results.get("children_key", "不明")
                    
                    # 主要フィールド一覧（最初のアイテムから）
                    main_keys = []
                    if isinstance(first_item, dict):
                        for key in list(first_item.keys())[:6]:  # 最大6個のキーを表示
                            if isinstance(first_item[key], dict):
                                # ネストしたオブジェクトの場合
                                nested_keys = list(first_item[key].keys())[:3]  # 最大3個
                                nested_str = ', '.join(nested_keys)
                                if len(first_item[key]) > 3:
                                    nested_str += "..."
                                main_keys.append(f"{key}({nested_str})")
                            elif isinstance(first_item[key], list):
                                # 配列の場合
                                array_len = len(first_item[key])
                                main_keys.append(f"{key}[{array_len}]")
                            else:
                                # プリミティブ値の場合
                                main_keys.append(key)
                    
                    # 複数行の構造化表示を構成（raw_dataから）
                    # 現在のファイル名を取得
                    current_file = self.app_state.get("current_file", "")
                    file_name = os.path.basename(current_file) if current_file else "不明"
                    
                    line1 = f"[FILE] {file_name} | [DATA] {t('analysis.record_count').format(count=item_count)}"
                    line2 = f"[KEY] {', '.join(main_keys[:6])}" + ("..." if len(main_keys) > 6 else "")
                    
                    # 3行目: キー設定情報
                    key_info_parts = [f"ID={id_key}", f"Label={label_key}"]
                    if children_key != "不明":
                        key_info_parts.append(f"Children={children_key}")
                    line3 = f"[TARGET] {', '.join(key_info_parts)}"
                    
                    # 3行に分けて表示
                    analysis_text.value = f"{line1}\n{line2}\n{line3}"
                    logger.debug("raw_dataから構造情報を取得して表示しました")
                else:
                    # raw_dataも空の場合
                    current_file = self.app_state.get("current_file", "")
                    file_name = os.path.basename(current_file) if current_file else "不明"
                    analysis_text.value = t("analysis.complete_no_data").format(filename=file_name, id=analysis_results.get('id_key', '不明'))
            
            analysis_text.update()
            logger.debug(f"解析結果をUIに表示: {analysis_text.value}")
        else:
            logger.warning("解析結果表示の更新に失敗: analysis_textまたはanalysis_resultsが見つかりません")
    
    def _process_loaded_data(self, file_path: str, data: Any) -> bool:
        """読み込まれたデータを処理する"""
        try:
            self.app_state["raw_data"] = data
            self.app_state["current_file"] = file_path
            self.app_state["selected_node_id"] = None
            
            # 右ペインの状態をリセット（FormManagerを使用）
            form_manager = self.app_state.get("form_manager")
            if form_manager:
                form_manager.clear_detail_form()
                logger.debug("右ペインの状態をリセットしました")
            
            # UIコントロールの状態更新
            if "selected_file_path_text" in self.ui_controls and self.ui_controls["selected_file_path_text"]:
                self.ui_controls["selected_file_path_text"].value = os.path.basename(file_path)
                self.ui_controls["selected_file_path_text"].update()
            
            # AnalysisManagerを使って解析を実行
            analysis_manager = self.app_state.get("analysis_manager")
            if analysis_manager:
                analysis_results = analysis_manager.analyze_json_structure(data=data)
                self.app_state["analysis_results"] = analysis_results
                
                # 空のリスト[dict]に初期テンプレートを追加
                data = self.prepare_empty_arrays(data, analysis_results)
                self.app_state["raw_data"] = data  # 更新されたデータを保存
            else:
                logger.warning("AnalysisManager not found. Skipping JSON analysis.")
            
            # データマップとツリー構造を構築
            self.build_data_map_and_tree()
            
            # データマップ構築後に解析結果をUIに表示
            if analysis_manager and "analysis_results" in self.app_state:
                self._update_analysis_result_display(self.app_state["analysis_results"])
            
            # 新ファイル読み込み時は既存のTreeOptimizerと状態をクリア
            if "tree_optimizer" in self.app_state:
                del self.app_state["tree_optimizer"]
                logger.debug("既存のTreeOptimizerをクリアしました")
            
            # ツリービューの展開状態もリセット
            if "expanded_nodes" in self.app_state:
                self.app_state["expanded_nodes"] = set()
                logger.debug("ツリービュー展開状態をリセットしました")
            
            # UIManager必須キーの初期化
            if "tree_drag_locked" not in self.app_state:
                self.app_state["tree_drag_locked"] = False
            
            # ファイルパスをapp_stateに保存（UIManager.update_ui_save_state用）
            self.app_state["file_path"] = file_path
            logger.info(f"ファイルパスをapp_stateに保存: {file_path}")
            
            # UIを更新（ファイル切り替え時は完全再構築）
            ui_manager = self.app_state.get("ui_manager")
            if ui_manager:
                # ファイル切り替えの場合は最適化なしで完全再構築
                ui_manager.update_tree_view(optimize=False)
                logger.debug("ツリービューの完全再構築を実行しました")
                
                # 検索マネージャーのインデックス更新
                search_manager = self.app_state.get("search_manager")
                if search_manager:
                    search_manager.update_search_index()
                    logger.debug("検索インデックスを更新しました")
                
                # メインコンテンツと検索UIを表示
                ui_manager.ensure_main_content_visible()
                
                # 検索UIコンテナの表示
                search_ui_container = self.ui_controls.get("search_ui_container")
                if search_ui_container:
                    search_ui_container.visible = True
                    logger.debug("検索UIコンテナを表示に設定")
            
            # UIStateManagerを使ってUI状態を更新
            ui_state_manager = self.app_state.get("ui_state_manager")
            if ui_state_manager:
                ui_state_manager.set_file_loaded(file_path)
            
            # UIManagerの保存状態も更新
            ui_manager = self.app_state.get("ui_manager")
            if ui_manager and hasattr(ui_manager, 'update_ui_save_state'):
                ui_manager.update_ui_save_state()
                logger.debug("ファイル読み込み後にUI保存状態を更新しました")
            
            # イベント通知
            if self._on_data_loaded_callback:
                self._on_data_loaded_callback(file_path, data)
            
            # 最近使用したファイルリストを更新
            self._update_recent_files(file_path)
            
            return True
            
        except Exception as e:
            error_message = t("error.json_processing_failed").format(error=str(e))
            logger.error(error_message)
            
            # エラーメッセージを表示
            if self.page:
                try:
                    from notification_system import NotificationSystem
                    notification_system = NotificationSystem(self.page)
                    notification_system.show_error(error_message)
                except Exception:
                    # フォールバック: 従来のSnackBar
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(error_message),
                        bgcolor=ft.Colors.RED,
                        action=t("dialog.close")
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
            
            return False
    
    def _update_recent_files(self, file_path: str) -> None:
        """最近使用したファイルリストを更新する"""
        try:
            recent_files = self.app_state.get("recently_opened_files", [])
            
            # 既存の場合は削除して先頭に追加
            if file_path in recent_files:
                recent_files.remove(file_path)
            
            # 先頭に追加
            recent_files.insert(0, file_path)
            
            # 最大数に制限
            max_recent = self.app_state.get("max_recent_files", 5)
            self.app_state["recently_opened_files"] = recent_files[:max_recent]
            
            # ページタイトルを更新
            if self.page:
                self.page.title = f"FleDjSON - {os.path.basename(file_path)}"
                self.page.update()
        except Exception as e:
            import traceback
            logger.error(f"Error updating recent files: {str(e)}")
            logger.debug(traceback.format_exc())
    
    def save_json_file(self, file_path: str) -> bool:
        """
        現在のデータをJSONファイルとして保存する
        
        Args:
            file_path: 保存先のファイルパス
            
        Returns:
            成功した場合はTrue、失敗した場合はFalse
        """
        try:
            logger.info(f"Saving to JSON file: {file_path}")
            
            if not self.app_state.get("raw_data"):
                logger.error("No data to save.")
                return False
            
            # 保存前に現在のツリー構造に基づいてデータを並べ替え
            self.reorder_raw_data()
            
            # 保存前に空のテンプレートアイテムを削除
            clean_data = self.remove_template_items(self.app_state["raw_data"])
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(clean_data, f, ensure_ascii=False, indent=2)
            
            self.app_state["current_file"] = file_path
            
            # ノード削除フラグをリセット（重要）
            self.app_state["node_deleted_since_last_save"] = False
            logger.debug("[保存成功] node_deleted_since_last_save フラグを False にリセットしました")
            
            # UIコントロールを更新
            if "status_bar" in self.ui_controls and self.ui_controls["status_bar"]:
                self.ui_controls["status_bar"].content.controls[0].value = os.path.basename(file_path)
                self.ui_controls["status_bar"].update()
            
            # ページタイトルを更新
            if self.page:
                self.page.title = f"FleDjSON - {os.path.basename(file_path)}"
                self.page.update()
                
                # 保存成功メッセージ
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(t("notification.file_saved").format(filename=os.path.basename(file_path))),
                    bgcolor=ft.Colors.GREEN_700,
                )
                self.page.snack_bar.open = True
                self.page.update()
            
            return True
        except Exception as e:
            logger.error(f"Error saving JSON file: {str(e)}")
            
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(t("notification.file_save_failed").format(error=str(e))),
                    bgcolor=ft.Colors.RED,
                )
                self.page.snack_bar.open = True
                self.page.update()
                
            return False
    
    @performance_log(label="Build Data Map and Tree")
    def build_data_map_and_tree(self) -> bool:
        """
        解析結果に基づいてデータマップとツリー構造を構築する
        
        Returns:
            構築が成功した場合はTrue、失敗した場合はFalse
        """
        logger.debug("Building data map and tree structure...")
        
        # 処理中の表示
        self._set_loading_state(True, "データマップとツリー構造を構築中...")

        if not self.app_state.get("analysis_results") or not self.app_state.get("raw_data"):
            logger.error("No data available for building data map and tree.")
            self._set_loading_state(False)
            return False

        # [CONFIG] 新ファイル読み込み時に既存の状態を完全にクリア
        logger.debug("Clearing existing data structures for new file...")
        self.app_state["data_map"] = {}
        self.app_state["children_map"] = {}
        self.app_state["root_ids"] = []
        self.app_state["selected_node_id"] = None
        self.app_state["edit_buffer"] = {}
        self.app_state["is_dirty"] = False
        
        # UI関連の状態もクリア
        if "expanded_nodes" in self.app_state:
            self.app_state["expanded_nodes"] = set()
        if "tree_optimizer" in self.app_state:
            del self.app_state["tree_optimizer"]
        if "search_results" in self.app_state:
            self.app_state["search_results"] = set()
            
        logger.debug("Previous data structures and UI states cleared")

        try:
            analysis = self.app_state["analysis_results"]
            raw_data = self.app_state["raw_data"]
            
            # 単一オブジェクトの場合はリストに変換
            if isinstance(raw_data, dict):
                raw_data = [raw_data]
                self.app_state["raw_data"] = raw_data
                logger.debug("単一オブジェクトをリスト形式に変換してdata_mapを構築します")

            id_key = analysis["heuristic_suggestions"].get("identifier")
            children_key = analysis["heuristic_suggestions"].get("children_link")
            depth_key = next((f["name"] for f in analysis["field_details"] if f["name"].endswith("depth")), None)
            label_key = analysis["heuristic_suggestions"].get("label")

            # キー情報をapp_stateに保存
            self.app_state["id_key"] = id_key
            self.app_state["children_key"] = children_key
            self.app_state["depth_key"] = depth_key
            self.app_state["label_key"] = label_key


            # IDキーが見つからない場合の処理（単一オブジェクトや非階層データ用）
            if not id_key:
                logger.warning("ID key not found. Building flat structure for non-hierarchical data...")
                return self._build_flat_data_structure(raw_data)

            # データマップとルートIDsをクリア
            self.app_state["data_map"] = {}
            self.app_state["children_map"] = {}
            self.app_state["root_ids"] = []
            all_child_ids = set()

            # データマップを構築
            for item in raw_data:
                if isinstance(item, dict) and id_key in item:
                    item_id = str(item[id_key])
                    self.app_state["data_map"][item_id] = item.copy()  # itemのコピーをdata_mapに格納

                    # children_map の構築
                    if children_key and children_key in item and isinstance(item[children_key], list):
                        child_ids = [str(c_id) for c_id in item[children_key] if c_id is not None]
                        self.app_state["children_map"][item_id] = child_ids
                        all_child_ids.update(child_ids)
                else:
                    logger.warning(f"Skipping item due to missing ID key ('{id_key}') or not a dict: {item}")

            # ルートノードの特定
            min_depth = float('inf')
            potential_roots_by_depth = []
            
            # 深さキーが存在する場合は、最小深さのノードをルートとする
            if depth_key:
                for item_id, item_data in self.app_state["data_map"].items():
                    if depth_key in item_data:
                        try:
                            depth = int(item_data[depth_key])
                            if depth < min_depth:
                                min_depth = depth
                                potential_roots_by_depth = [item_id]
                            elif depth == min_depth:
                                potential_roots_by_depth.append(item_id)
                        except (ValueError, TypeError):
                            pass

            if potential_roots_by_depth:
                self.app_state["root_ids"] = potential_roots_by_depth
                logger.debug(f"Found {len(self.app_state['root_ids'])} root nodes based on minimum depth ({min_depth}).")
            elif children_key:
                # 子供でないノードをルートとする
                all_ids = set(self.app_state["data_map"].keys())
                self.app_state["root_ids"] = list(all_ids - all_child_ids)
                logger.debug(f"Found {len(self.app_state['root_ids'])} root nodes based on children link (not being a child).")
            else:
                # 階層構造が特定できない場合は全ノードをルートとする
                self.app_state["root_ids"] = list(self.app_state["data_map"].keys())
                logger.warning(f"Could not determine hierarchy reliably. Displaying all nodes as roots.")

            # 全てのノードが表示されるようにする
            if children_key:
                all_ids = set(self.app_state["data_map"].keys())
                missing_root_ids = all_ids - all_child_ids - set(self.app_state["root_ids"])
                if missing_root_ids:
                    self.app_state["root_ids"].extend(list(missing_root_ids))

            # 元のデータ順を保持するようにソート
            original_order_map = {str(item.get(id_key)): index for index, item in enumerate(raw_data) if isinstance(item, dict) and id_key in item}
            self.app_state["root_ids"].sort(key=lambda root_id: original_order_map.get(root_id, float('inf')))
            
            logger.info(f"Loaded {len(self.app_state['data_map'])} items into data_map.")
            logger.info(f"Identified {len(self.app_state['root_ids'])} root nodes: {self.app_state['root_ids'][:5]}...")
            logger.info(f"Built children map for {len(self.app_state['children_map'])} parents.")
            
            
            if not self.app_state["data_map"] or not self.app_state["root_ids"]:
                logger.error("Failed to build data map or find root nodes.")
                return False
                
            return True

        except Exception as e:
            import traceback
            logger.error(f"Error building data map and tree: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    def _build_flat_data_structure(self, raw_data: List[Dict]) -> bool:
        """
        IDベースの階層構造ではないデータを平坦な構造として構築する.

        complex_nested_structure.jsonのような単一オブジェクトや非階層データ用。
        flatten_json.pyの平坦化機能を使用して、深くネストされた構造を
        検索可能な形式に変換する。

        Args:
            raw_data: 処理対象のraw_data

        Returns:
            構築が成功した場合はTrue
        """
        # 定数定義
        DEFAULT_ID_KEY = "id"
        DEFAULT_CHILDREN_KEY = "children"
        LABEL_CANDIDATES = ["name", "title", "label", "description", "id"]

        try:
            logger.debug("Building flat structure for non-hierarchical data...")

            # データマップとツリー構造をクリア
            self.app_state["data_map"] = {}
            self.app_state["children_map"] = {}
            self.app_state["root_ids"] = []

            # raw_dataがリストの場合、各アイテムを処理
            # raw_dataが単一オブジェクトの場合、そのまま平坦化
            if isinstance(raw_data, list) and len(raw_data) == 1:
                # 単一オブジェクトのリストの場合、中身を取り出して平坦化
                flattened_data, was_flattened = try_flatten_json(raw_data[0])
            else:
                # 複数アイテムまたは辞書の場合
                flattened_data, was_flattened = try_flatten_json(raw_data)

            if was_flattened and flattened_data:
                logger.debug(f"Data was flattened: {len(flattened_data)} nodes extracted")

                # 平坦化されたデータからdata_mapとchildren_mapを構築
                all_child_ids: Set[str] = set()
                auto_id_counter = 0  # 安定したカウンター

                for item in flattened_data:
                    if isinstance(item, dict):
                        # IDを取得(既存のIDまたはパスベースのID)
                        item_id = item.get(DEFAULT_ID_KEY) or item.get("_path")
                        if not item_id:
                            # 自動生成IDが衝突しないようにチェック
                            while f"auto_{auto_id_counter}" in self.app_state["data_map"]:
                                auto_id_counter += 1
                            item_id = f"auto_{auto_id_counter}"
                            auto_id_counter += 1
                        item_id = str(item_id)

                        # data_mapに追加
                        self.app_state["data_map"][item_id] = item.copy()

                        # children_mapの構築
                        children = item.get(DEFAULT_CHILDREN_KEY)
                        if isinstance(children, list):
                            child_ids = [str(c_id) for c_id in children if c_id is not None]
                            self.app_state["children_map"][item_id] = child_ids
                            all_child_ids.update(child_ids)

                # ルートノードの特定(子ノードとして参照されていないノード)
                all_ids = set(self.app_state["data_map"].keys())
                self.app_state["root_ids"] = list(all_ids - all_child_ids)

                # ルートノードがない場合は最初のノードをルートとする
                if not self.app_state["root_ids"] and self.app_state["data_map"]:
                    first_id = next(iter(self.app_state["data_map"].keys()))
                    self.app_state["root_ids"] = [first_id]

                # キー設定を更新
                self.app_state["id_key"] = DEFAULT_ID_KEY
                self.app_state["children_key"] = DEFAULT_CHILDREN_KEY

                # ラベルキーの推定
                label_key = DEFAULT_ID_KEY  # デフォルト
                if self.app_state["data_map"]:
                    first_item = next(iter(self.app_state["data_map"].values()))
                    for candidate in LABEL_CANDIDATES:
                        if candidate in first_item:
                            label_key = candidate
                            break
                self.app_state["label_key"] = label_key

                # raw_dataを平坦化後のデータで更新
                self.app_state["raw_data"] = flattened_data

                logger.info(
                    f"Flat structure built with flattening: "
                    f"{len(self.app_state['data_map'])} items, "
                    f"{len(self.app_state['root_ids'])} roots"
                )
            else:
                # 平坦化されなかった場合は従来の方法でフォールバック
                logger.debug("Data was not flattened, using fallback method")

                for i, item in enumerate(raw_data):
                    if isinstance(item, dict):
                        # 仮想IDを生成(衝突チェック付き)
                        virtual_id = f"item_{i}"
                        while virtual_id in self.app_state["data_map"]:
                            virtual_id = f"item_{i}_{uuid.uuid4().hex[:8]}"

                        # data_mapに追加
                        self.app_state["data_map"][virtual_id] = item.copy()

                        # ルートノードとして扱う
                        self.app_state["root_ids"].append(virtual_id)

                        logger.debug(f"Added flat item: {virtual_id}")

                # 仮想的なキー設定を更新
                self.app_state["id_key"] = "virtual_id"
                self.app_state["label_key"] = "virtual_id"
                self.app_state["children_key"] = None

                logger.info(f"Flat structure built (fallback): {len(self.app_state['data_map'])} items")

            # 解析結果表示を更新
            if self.app_state.get("analysis_results"):
                self._update_analysis_result_display(self.app_state["analysis_results"])

            self._set_loading_state(False)
            return True

        except (KeyError, TypeError, ValueError):
            logger.exception("Data structure error in flat structure building")
            self._set_loading_state(False)
            return False
        except Exception:
            logger.exception("Unexpected error building flat structure")
            self._set_loading_state(False)
            return False
    
    def update_data(self, key_path: str, new_value: Any) -> bool:
        """
        指定されたキーパスのデータを更新する
        
        Args:
            key_path: 更新するデータのキーパス（例：'field.subfield[0].name'）
            new_value: 設定する新しい値
            
        Returns:
            更新が成功した場合はTrue、失敗した場合はFalse
        """
        if "selected_node_id" not in self.app_state or self.app_state["selected_node_id"] is None:
            logger.warning("No node selected for update.")
            return False

        try:
            node_data_map = self.app_state["data_map"].get(self.app_state["selected_node_id"])
            if not node_data_map:
                logger.error(f"Error updating data_map: Node data not found for ID {self.app_state['selected_node_id']}")
                return False

            keys = self.key_path_regex.split(key_path)
            keys = [k for k in keys if k is not None and k != '']

            target_map = node_data_map
            original_value_map = None

            # ターゲットマップへの参照を取得
            for i, key in enumerate(keys[:-1]):
                if key.isdigit():
                    idx = int(key)
                    if isinstance(target_map, list) and 0 <= idx < len(target_map):
                        target_map = target_map[idx]
                    else:
                        logger.error(f"Error updating data_map: Invalid list index {key} in path {key_path}")
                        return False
                elif isinstance(target_map, dict):
                    if key in target_map:
                        target_map = target_map[key]
                    else:
                        logger.error(f"Error updating data_map: Key {key} not found in path {key_path}")
                        return False
                else:
                    logger.error(f"Error updating data_map: Cannot access key {key} in non-dict/list object at path {key_path}")
                    return False

            last_key = keys[-1]

            converted_value = new_value
            original_type = None

            # 元の値と型を取得
            try:
                if last_key.isdigit():
                    idx = int(last_key)
                    if isinstance(target_map, list) and 0 <= idx < len(target_map):
                        original_value_map = target_map[idx]
                        original_type = type(original_value_map)
                    else:
                        logger.error(f"Error updating data_map: Invalid list index {last_key} in path {key_path}")
                        return False
                elif isinstance(target_map, dict) and last_key in target_map:
                    original_value_map = target_map[last_key]
                    original_type = type(original_value_map)
                else:
                    # キーが存在しない場合（新規フィールド）
                    logger.info(f"[情報] キー {last_key} が存在しません。新規フィールドとして追加します。")
                    # 値の型から適切な変換を試みる
                    if isinstance(new_value, str):
                        # 数値文字列かどうか判定
                        if new_value.strip().isdigit() or (new_value.strip() and new_value.strip().replace('.', '', 1).isdigit() and new_value.strip().count('.') <= 1):
                            if '.' in new_value:
                                converted_value = float(new_value)
                            else:
                                converted_value = int(new_value)
                        # 真偽値文字列かどうか判定
                        elif new_value.strip().lower() in ["true", "false"]:
                            converted_value = new_value.strip().lower() == "true"
                        # リスト/辞書文字列の判定
                        elif new_value.strip().startswith('[') and new_value.strip().endswith(']'):
                            converted_value = self.try_parse_json(new_value, list)
                        elif new_value.strip().startswith('{') and new_value.strip().endswith('}'):
                            converted_value = self.try_parse_json(new_value, dict)

                # 型変換処理
                if original_type is not None and original_type != type(new_value):
                    # try_parse_jsonはクラスメソッドとして実装済み
                    
                    if original_type == int:
                        try:
                            converted_value = int(float(new_value))
                        except (ValueError, TypeError) as e:
                            logger.error(f"[エラー] int変換失敗: {e}")
                            return False
                    elif original_type == float:
                        try:
                            converted_value = float(new_value)
                        except (ValueError, TypeError) as e:
                            logger.error(f"[エラー] float変換失敗: {e}")
                            return False
                    elif original_type == bool:
                        if isinstance(new_value, str):
                            lower_val = new_value.lower()
                            converted_value = lower_val in ["true", "1", "yes", "y", "on"]
                        else:
                            converted_value = bool(new_value)
                    elif original_type == str:
                        converted_value = str(new_value)
                    elif original_type in (list, dict) and isinstance(new_value, str):
                        converted_value = try_parse_json(new_value, original_type)
                    
            except (ValueError, TypeError) as e:
                logger.warning(f"Type conversion failed for {key_path}: Cannot convert '{new_value}' to {original_type}. Error: {e}")
                return False

            # 値の更新
            if last_key.isdigit():
                idx = int(last_key)
                target_map[idx] = converted_value
            elif isinstance(target_map, dict):
                target_map[last_key] = converted_value
            else:
                logger.error(f"Error updating data_map: Cannot set final key {last_key} in non-dict object at path {key_path}")
                return False

            # raw_dataの更新処理
            id_key = self.app_state.get("id_key")
            target_raw_obj = None

            if id_key and self.app_state["selected_node_id"] is not None:
                selected_id_value_str = self.app_state["selected_node_id"]
                for item in self.app_state["raw_data"]:
                    if isinstance(item, dict) and id_key in item and str(item[id_key]) == selected_id_value_str:
                        target_raw_obj = item
                        break
            else:
                logger.error(f"Error finding object in raw_data: ID key ('{id_key}') not available or no node selected ('{self.app_state['selected_node_id']}')")

            if target_raw_obj is not None:
                target_raw = target_raw_obj
                for i, key in enumerate(keys[:-1]):
                    if key.isdigit():
                        idx = int(key)
                        if isinstance(target_raw, list) and 0 <= idx < len(target_raw):
                            target_raw = target_raw[idx]
                        else:
                            logger.error(f"Error updating raw_data: Invalid list index {key} in path {key_path}")
                            return False
                    elif isinstance(target_raw, dict):
                        if key in target_raw:
                            target_raw = target_raw[key]
                        else:
                            logger.error(f"Error updating raw_data: Key {key} not found in path {key_path}")
                            return False
                    else:
                        print(f"[ERROR] Error updating raw_data: Cannot access key {key} in non-dict/list object at path {key_path}")
                        return False

                if last_key.isdigit():
                    idx = int(last_key)
                    if isinstance(target_raw, list) and 0 <= idx < len(target_raw):
                        target_raw[idx] = converted_value
                    else:
                        print(f"[ERROR] Error updating raw_data: Invalid list index {last_key} in path {key_path}")
                        return False
                elif isinstance(target_raw, dict):
                    target_raw[last_key] = converted_value
                else:
                    print(f"[ERROR] Error updating raw_data: Cannot set final key {last_key} in non-dict/list object at path {key_path}")
                    return False
                
                return True
            else:
                print(f"[ERROR] Error updating raw_data: Could not find corresponding object in raw_data for node ID {self.app_state['selected_node_id']}")
                return False

        except Exception as e:
            import traceback
            print(f"[ERROR] Error updating data for key '{key_path}': {e}")
            print(traceback.format_exc())
            return False
    
    def add_new_node(self, parent_id: Optional[str], node_data: Dict[str, Any]) -> bool:
        """
        新しいノードをデータに追加する
        
        Args:
            parent_id: 親ノードのID（ルートノードの場合はNone）
            node_data: 追加するノードのデータ
            
        Returns:
            追加が成功した場合はTrue、失敗した場合はFalse
        """
        
        # 状態チェック
        
        if not (self.app_state.get("raw_data") is not None and self.app_state.get("analysis_results") is not None):
            print("[ERROR] Error: No data or analysis results available for adding new node.")
            return False
        
        try:
            id_key = self.app_state["analysis_results"]["heuristic_suggestions"].get("identifier")
            if not id_key or id_key not in node_data:
                print(f"[ERROR] Error: Cannot add node without ID field. id_key={id_key}")
                return False
            
            # ノードID（文字列に統一）
            new_node_id = str(node_data[id_key])
            
            # IDの重複チェック
            if new_node_id in self.app_state["data_map"]:
                print(f"[ERROR] Error: Node ID {new_node_id} already exists in data_map.")
                return False
            
            
            # 必要に応じて深さ設定
            depth_key = self.app_state.get("depth_key")
            if depth_key and depth_key not in node_data:
                if parent_id:
                    parent_data = self.app_state["data_map"].get(parent_id)
                    if parent_data and depth_key in parent_data:
                        node_data[depth_key] = parent_data[depth_key] + 1
                    else:
                        node_data[depth_key] = 1  # 親の深さが不明な場合は1
                else:
                    node_data[depth_key] = 0  # ルートノードの場合
            
            # 親子関係の設定
            children_key = self.app_state.get("children_key")
            if parent_id and children_key:
                # 親ノードの子リストに追加
                parent_data = self.app_state["data_map"].get(parent_id)
                if parent_data:
                    if children_key not in parent_data:
                        parent_data[children_key] = []
                    
                    # IDの型を親の子リストに合わせる（文字列か数値か）
                    child_id_to_add = node_data[id_key]
                    if parent_data[children_key]:
                        first_child = parent_data[children_key][0]
                        if isinstance(first_child, int) and not isinstance(child_id_to_add, int):
                            try:
                                child_id_to_add = int(child_id_to_add)
                                # ノードデータのIDも更新
                                node_data[id_key] = child_id_to_add
                                # 新しいノードIDも更新
                                new_node_id = str(child_id_to_add)
                            except (ValueError, TypeError):
                                print(f"[WARNING] Warning: Could not convert node ID {child_id_to_add} to int to match parent's children.")
                        
                    parent_data[children_key].append(child_id_to_add)
                    
                    # raw_dataの親も更新
                    parent_raw = next((item for item in self.app_state["raw_data"] if isinstance(item, dict) and 
                                  str(item.get(id_key)) == parent_id), None)
                    if parent_raw:
                        if children_key not in parent_raw:
                            parent_raw[children_key] = []
                        parent_raw[children_key].append(child_id_to_add)
                    else:
                        print(f"[WARNING] Warning: Parent node {parent_id} not found in raw_data.")
            
            # データをdata_mapとraw_dataに追加するが、raw_dataへの追加位置を工夫する
            self.app_state["data_map"][new_node_id] = node_data
            
            # raw_dataへの追加方法を改善: 順序を考慮して追加
            if parent_id:
                # 親ノードのraw_data内での位置を特定
                parent_index = -1
                for i, item in enumerate(self.app_state["raw_data"]):
                    if isinstance(item, dict) and id_key in item and str(item[id_key]) == parent_id:
                        parent_index = i
                        break
                
                if parent_index >= 0:
                    # 親ノードの子要素がある場合、その子要素の後に配置
                    if children_key and children_key in self.app_state["raw_data"][parent_index]:
                        children_ids = self.app_state["raw_data"][parent_index][children_key]
                        if children_ids and len(children_ids) > 0:
                            # 子ノードのIDをすべて文字列化して比較
                            str_children_ids = [str(cid) for cid in children_ids]
                            # 最後の子ノードの位置を見つける
                            last_child_index = -1
                            for i, item in enumerate(self.app_state["raw_data"]):
                                if isinstance(item, dict) and id_key in item:
                                    item_id = str(item[id_key])
                                    if item_id in str_children_ids:
                                        last_child_index = max(last_child_index, i)
                            
                            if last_child_index >= 0:
                                # 最後の子ノードの後に挿入
                                self.app_state["raw_data"].insert(last_child_index + 1, node_data)
                            else:
                                # 子ノードが見つからなければ親の直後に挿入
                                self.app_state["raw_data"].insert(parent_index + 1, node_data)
                        else:
                            # 子ノードがなければ親の直後に挿入
                            self.app_state["raw_data"].insert(parent_index + 1, node_data)
                    else:
                        # children_keyがなければ親の直後に挿入
                        self.app_state["raw_data"].insert(parent_index + 1, node_data)
                else:
                    # 親が見つからない場合は末尾に追加
                    self.app_state["raw_data"].append(node_data)
            else:
                # ルートノードの場合、他のルートノードの後に追加
                if self.app_state["root_ids"]:
                    last_root_index = -1
                    for i, item in enumerate(self.app_state["raw_data"]):
                        if isinstance(item, dict) and id_key in item:
                            item_id = str(item[id_key])
                            if item_id in self.app_state["root_ids"]:
                                last_root_index = max(last_root_index, i)
                    
                    if last_root_index >= 0:
                        # 最後のルートノードの後に挿入
                        self.app_state["raw_data"].insert(last_root_index + 1, node_data)
                    else:
                        # ルートノードが見つからなければ末尾に追加
                        self.app_state["raw_data"].append(node_data)
                else:
                    # ルートノードがない場合は末尾に追加
                    self.app_state["raw_data"].append(node_data)
            
            # 親がなければroot_idsに追加
            if not parent_id:
                self.app_state["root_ids"].append(new_node_id)
            
            # children_mapを更新
            if parent_id:
                if parent_id not in self.app_state["children_map"]:
                    self.app_state["children_map"][parent_id] = []
                self.app_state["children_map"][parent_id].append(new_node_id)
            
            # UIの更新
            ui_manager = self.app_state.get("ui_manager")
            if ui_manager:
                # 最適化された更新を使用
                ui_manager.update_tree_view(optimize=True)
                print(f"[OK] ツリービューの更新を実行しました（最適化モード）")
            else:
                print(f"[WARNING] ui_managerが見つかりません")
            
            # 検索インデックスの更新を追加
            try:
                print("[UPDATE] 検索マネージャー取得とインデックス更新を開始...")
                search_manager = self.app_state.get("search_manager")
                if not search_manager:
                    # 検索マネージャーがない場合は作成
                    print("[WARNING] app_stateに検索マネージャーが存在しないため、新規に作成します")
                    
                    search_manager = SearchManager(self.app_state, self.app_state.get("ui_controls", {}))
                    self.app_state["search_manager"] = search_manager
                
                # raw_dataの現在の内容を確認
                
                # 検索インデックスの状態を確認
                if not hasattr(search_manager, 'search_index'):
                    print("[WARNING] search_managerにsearch_index属性がありません")
                
                # 完全なインデックス再構築
                search_manager.build_search_index()
                print(f"[OK] 検索インデックスの完全再構築を実行しました")
                
                # 念のため、追加したノードが検索インデックスに含まれているか確認
                node_indexed = False
                for item in search_manager.search_index:
                    if item.get("id") == new_node_id:
                        node_indexed = True
                        break
                
                if node_indexed:
                    print(f"[OK] ノードID '{new_node_id}' は検索インデックスに含まれています")
                else:
                    # インデックスに含まれていなければ個別に追加
                    print(f"[WARNING] ノードID '{new_node_id}' が検索インデックスに見つからないため、個別に追加します")
                    search_manager.update_search_index(node_id=new_node_id)
                    print(f"[OK] ノードID '{new_node_id}' の検索インデックスを個別に更新しました")
                
                # 特定のキーワード('dev')が検索できることを確認
                dev_found = False
                for item in search_manager.search_index:
                    if 'dev' in item.get('text', '').lower() and item.get('id') == new_node_id:
                        dev_found = True
                        print(f"[OK] キーワード 'dev' がノード '{new_node_id}' の検索テキストに含まれています")
                        break
                if not dev_found:
                    print(f"[WARNING] キーワード 'dev' がノード '{new_node_id}' の検索テキストに含まれていません")
            except Exception as search_ex:
                # エラーがあってもノード追加自体は成功とする
                print(f"[WARNING] 検索インデックス更新中にエラーが発生: {search_ex}")
                import traceback
                print(traceback.format_exc())
            
            return True
            
        except Exception as ex:
            print(f"[ERROR] Error adding new node: {ex}")
            import traceback
            print(traceback.format_exc())
            return False
    
    def delete_node(self, node_id: str) -> bool:
        """
        指定されたノードIDとその子孫を削除する
        
        Args:
            node_id: 削除するノードのID
            
        Returns:
            削除が成功した場合はTrue、失敗した場合はFalse
        """
        print(f"[DELETE] Deleting node: {node_id}")
        if not node_id or node_id not in self.app_state.get("data_map", {}):
            print(f"[WARNING] Node ID {node_id} not found for deletion.")
            return False

        id_key = self.app_state.get("id_key")
        if not id_key:
            print("[ERROR] Error: ID key not found in app_state.")
            return False

        nodes_to_delete = {node_id}
        queue = [node_id]

        # 削除対象ノードとその子孫を特定
        while queue:
            current_id = queue.pop(0)
            if current_id in self.app_state.get("children_map", {}):
                children = self.app_state["children_map"][current_id]
                for child_id in children:
                    if child_id not in nodes_to_delete:
                        nodes_to_delete.add(child_id)
                        queue.append(child_id)

        print(f"  Nodes to delete (including descendants): {nodes_to_delete}")

        # 削除実行
        deleted_count = 0
        new_raw_data = []
        original_raw_data_count = len(self.app_state.get("raw_data", []))

        # 1. raw_data から削除
        for item in self.app_state.get("raw_data", []):
            item_id_str = str(item.get(id_key)) if isinstance(item, dict) else None
            if item_id_str not in nodes_to_delete:
                new_raw_data.append(item)
            else:
                deleted_count += 1
        self.app_state["raw_data"] = new_raw_data
        print(f"  raw_data count: {original_raw_data_count} -> {len(self.app_state['raw_data'])}")

        # 2. data_map から削除
        for del_id in nodes_to_delete:
            if del_id in self.app_state["data_map"]:
                del self.app_state["data_map"][del_id]

        # 3. children_map から削除 (キーとして、および値として)
        new_children_map = {}
        for parent_id, children in self.app_state.get("children_map", {}).items():
            if parent_id not in nodes_to_delete:
                new_children = [child for child in children if child not in nodes_to_delete]
                if new_children: # 子が残っている場合のみマップに追加
                     new_children_map[parent_id] = new_children
        self.app_state["children_map"] = new_children_map
        print(f"  - Cleaned children_map")

        # 4. root_ids から削除
        self.app_state["root_ids"] = [root_id for root_id in self.app_state.get("root_ids", []) if root_id not in nodes_to_delete]
        print(f"  - Cleaned root_ids")

        # 5. 選択状態を解除し、関連状態をリセット
        self.app_state["selected_node_id"] = None
        if "edit_buffer" in self.app_state:
            self.app_state["edit_buffer"].clear()
        self.app_state["is_dirty"] = False
        self.app_state["delete_confirm_mode"] = False # 削除確認モードも解除
        
        # ノード削除後のフラグを設定（重要）
        self.app_state["node_deleted_since_last_save"] = True
        print("[IMPORTANT] node_deleted_since_last_save フラグを True に設定しました")

        print(f"[OK] Node deletion complete. Total nodes removed: {len(nodes_to_delete)}")

        # UI更新
        ui_state_manager = self.app_state.get("ui_state_manager")
        if ui_state_manager:
            # UIStateManagerを通じてUI状態を更新
            ui_state_manager.set_tree_view_dirty(True)
            ui_state_manager.deselect_node()
            ui_state_manager.refresh_ui()
        else:
            # 個別にUI要素を更新（UIStateManagerが利用できない場合のフォールバック）
            ui_manager = self.app_state.get("ui_manager")
            form_manager = self.app_state.get("form_manager")
            if ui_manager:
                ui_manager.update_tree_view()
            if form_manager:
                form_manager.clear_detail_form()
                form_manager.update_detail_buttons_state()

        # 削除成功メッセージ（代替システム）
        if self.page:
            try:
                from notification_system import NotificationSystem
                notification_system = NotificationSystem(self.page)
                child_count = len(nodes_to_delete) - 1
                if child_count > 0:
                    notification_system.show_info(t("notification.node_deleted_with_children", default=f"ノード '{node_id}' とその子孫 ({child_count}個) を削除しました").format(id=node_id, count=child_count))
                else:
                    notification_system.show_info(t("notification.node_deleted_success").format(id=node_id))
            except Exception as notif_ex:
                # フォールバック: 従来のSnackBar
                print(f"代替通知システムエラー: {notif_ex}")
                try:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(t("notification.node_deleted_with_children", default=f"ノード '{node_id}' とその子孫 ({len(nodes_to_delete) -1}個) を削除しました。").format(id=node_id, count=len(nodes_to_delete) -1)),
                        bgcolor=ft.Colors.GREEN_ACCENT_700,
                        duration=4000
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    print("[OK] フォールバック：従来スナックバーを表示")
                except:
                    print("[WARNING] 全ての通知方法が失敗しました")
            
        return True
    
    def reorder_raw_data(self):
        """
        子関係に基づいてraw_dataの順序を再構成する
        """
        # drag_drop_helpersにある関数を使用（今後他のマネージャーに移行される予定）
        try:
            # まずドラッグドロップマネージャーが利用可能か確認
            drag_drop_manager = self.app_state.get("drag_drop_manager")
            if drag_drop_manager and hasattr(drag_drop_manager, "get_ordered_node_ids"):
                # ドラッグドロップマネージャーのメソッドを使用
                ordered_nodes = drag_drop_manager.get_ordered_node_ids(self.app_state["root_ids"])
            else:
                # フォールバック：基本的な順序で処理
                ordered_nodes = self.app_state["root_ids"].copy()
        except ImportError:
            # フォールバックとして root_ids から順に処理
            ordered_nodes = []
            queue = self.app_state["root_ids"].copy()
            while queue:
                node_id = queue.pop(0)
                ordered_nodes.append(node_id)
                if node_id in self.app_state.get("children_map", {}):
                    queue.extend(self.app_state["children_map"][node_id])
        
        logger.debug(f"Reordering raw_data based on tree structure. Ordered nodes: {ordered_nodes[:5]}...")
        
        # 新しい順序の配列を構築
        new_raw_data = []
        id_key = self.app_state.get("id_key")
        
        # ID順にraw_dataから対応するオブジェクトを検索して新しい配列に追加
        if id_key:
            for node_id in ordered_nodes:
                for item in self.app_state["raw_data"]:
                    if isinstance(item, dict) and str(item.get(id_key)) == node_id:
                        new_raw_data.append(item)
                        break
        
        # 新しい順序のリストでraw_dataを置き換え
        if len(new_raw_data) > 0:
            self.app_state["raw_data"] = new_raw_data
    
    def prepare_empty_arrays(self, data, analysis_results):
        """
        空のlist[dict]配列に初期テンプレートを追加する
        解析結果に基づいて、空の配列（list[dict]型）を検出し、テンプレート辞書を配置する
        
        Args:
            data: 対象データ
            analysis_results: 解析結果
            
        Returns:
            テンプレート追加後のデータ
        """
        
        # フィールド詳細から配列型を持つフィールドを特定
        field_details = analysis_results.get("field_details", [])
        
        # dict[list[dict]]の構造を持つフィールドを抽出
        list_dict_fields = []
        for field in field_details:
            field_types = field.get("types", [])
            if field_types and field_types[0][0].startswith("list[dict]"):
                list_dict_fields.append(field.get("name"))
        
        if list_dict_fields:
            logger.debug(f"  発見されたlist[dict]型フィールド: {list_dict_fields}")
        else:
            logger.debug(f"  list[dict]型フィールドは見つかりませんでした")
            return data
        
        # 再帰的に処理
        def process_object(obj, path=""):
            modified = False
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    
                    # 値がリストで、そのパスがlist[dict]型の場合
                    if isinstance(value, list) and len(value) == 0:
                        # このパスがlist[dict]型かチェック
                        for field_path in list_dict_fields:
                            if field_path == new_path:
                                # テンプレート辞書の作成
                                template_dict = self.create_template_dict(field_path, field_details)
                                # 空配列にテンプレート辞書を追加
                                obj[key].append(template_dict)
                                logger.debug(f"  空の配列 '{new_path}' に初期テンプレートを追加: {template_dict}")
                                modified = True
                                break
                    
                    # 再帰的に処理（子要素に変更があれば記録）
                    if isinstance(value, (dict, list)):
                        if process_object(value, new_path):
                            modified = True
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    # 再帰的に処理（子要素に変更があれば記録）
                    if isinstance(item, (dict, list)):
                        if process_object(item, f"{path}[{i}]"):
                            modified = True
            
            return modified
        
        # 処理開始
        if isinstance(data, list):
            process_object(data)
        else:
            process_object(data, "")
        
        return data
    
    def create_template_dict(self, field_path, field_details):
        """
        フィールドパスに基づいてテンプレート辞書を作成する
        
        Args:
            field_path: フィールドのパス
            field_details: フィールド詳細情報
            
        Returns:
            作成されたテンプレート辞書
        """
        template = {}
        
        # 配列アイテムの子フィールドを探す（例: "items[].name"）
        child_field_prefix = f"{field_path}[]."
        matched_fields = []
        
        # 直接マッチするフィールド情報を探す
        for field in field_details:
            field_name = field.get("name", "")
            if field_name.startswith(child_field_prefix):
                # 子フィールド名を抽出（例: "name"）
                sub_key = field_name[len(child_field_prefix):]
                if "." not in sub_key and "[" not in sub_key:  # 直接の子フィールドのみ
                    matched_fields.append((sub_key, field))
        
        # マッチするフィールドが見つかった場合
        if matched_fields:
            for sub_key, field_info in matched_fields:
                field_types = field_info.get("types", [])
                default_value = ""  # デフォルト
                if field_types:
                    type_name = field_types[0][0]
                    if type_name == "int":
                        default_value = 0
                    elif type_name == "float":
                        default_value = 0.0
                    elif type_name == "bool":
                        default_value = False
                    elif type_name.startswith("list"):
                        default_value = []
                    elif type_name == "dict":
                        default_value = {}
                template[sub_key] = default_value
        
        # 子フィールドが特定できない場合は一般的なフィールドを提供
        if not template:
            # サンプルデータに基づく共通フィールド
            common_fields = ["id", "description", "text"]
            for field in common_fields:
                template[field] = ""
        
        # テンプレートデータであることを示すフラグを追加
        # これにより保存時に空の辞書を削除する際に判別できる
        template["_template_item"] = True
        
        return template
    
    def remove_template_items(self, data):
        """
        保存前に未編集のテンプレートアイテムを削除する
        
        Args:
            data: 処理対象のデータ
            
        Returns:
            テンプレートアイテム削除後のデータ
        """
        if isinstance(data, dict):
            # 辞書をイテレーションする際は新しいディクショナリを作成
            result = {}
            for key, value in data.items():
                # _template_itemキーは除外
                if key != "_template_item":
                    # 値を再帰的にクリーン
                    result[key] = self.remove_template_items(value)
            return result
        
        elif isinstance(data, list):
            # リストを処理する際は、フィルタリングと再帰処理を行う
            result = []
            for item in data:
                # アイテムがテンプレート辞書かどうかを判定
                if isinstance(item, dict) and item.get("_template_item", False):
                    # テンプレートアイテムであれば、内容が空か確認
                    is_empty = all(
                        (key == "_template_item" or 
                         value == "" or 
                         value == 0 or 
                         value == 0.0 or 
                         value == [] or 
                         value == {})
                        for key, value in item.items()
                    )
                    # 空でなければ（編集されていれば）追加するが、_template_itemフラグは削除
                    if not is_empty:
                        cleaned_item = self.remove_template_items(item)
                        if cleaned_item:  # 非空であれば
                            result.append(cleaned_item)
                else:
                    # 通常アイテムの場合は再帰的にクリーン
                    cleaned_item = self.remove_template_items(item)
                    result.append(cleaned_item)
            return result
        
        # 基本型はそのまま返す
        return data
    
    def get_value_by_path(self, data_obj: Union[Dict, List], key_path: str, return_reference: bool = False) -> Any:
        """
        キーパスを使用してデータオブジェクト内の値を取得する
        
        Args:
            data_obj: データオブジェクト（辞書またはリスト）
            key_path: キーパス（例: "a.b[0].c"）
            return_reference: 参照情報を返すかどうか
            
        Returns:
            取得した値、または参照情報を含む辞書
        """
        keys = self.key_path_regex.split(key_path)
        keys = [k for k in keys if k is not None and k != '']
        
        current_obj = data_obj
        parent_obj = None
        last_key = None

        for i, key in enumerate(keys):
            parent_obj = current_obj
            last_key = key
            is_last_key = (i == len(keys) - 1)

            if key.isdigit():
                idx = int(key)
                if isinstance(current_obj, list) and 0 <= idx < len(current_obj):
                    if is_last_key and return_reference:
                        return {'parent': parent_obj, 'key': idx, 'value': current_obj[idx]}
                    current_obj = current_obj[idx]
                else:
                    raise IndexError(f"List index {idx} out of range or not a list at path segment '{key}' in '{key_path}'")
            elif isinstance(current_obj, dict):
                if key in current_obj:
                    if is_last_key and return_reference:
                        return {'parent': parent_obj, 'key': key, 'value': current_obj[key]}
                    current_obj = current_obj[key]
                else:
                    raise KeyError(f"Key '{key}' not found in dict at path segment '{key}' in '{key_path}'")
            else:
                raise TypeError(f"Cannot access key/index '{key}' in non-dict/list object ({type(current_obj).__name__}) at path segment '{key}' in '{key_path}'")

        # キーパスの処理が完了した場合
        if return_reference:
             # ループ内で最後のキーの場合は参照情報を返す
             if last_key is not None:
                  key_or_index = int(last_key) if last_key.isdigit() else last_key
                  return {'parent': parent_obj, 'key': key_or_index, 'value': current_obj}
             else: # 空のパスの場合はオブジェクト自体を返す
                  return {'parent': None, 'key': None, 'value': data_obj}
        else:
            return current_obj
    
    def set_value_by_path(self, data_obj: Union[Dict, List], key_path: str, value: Any) -> bool:
        """
        キーパスを使用してデータオブジェクト内の値を設定する
        
        Args:
            data_obj: データオブジェクト（辞書またはリスト）
            key_path: キーパス（例: "a.b[0].c"）
            value: 設定する値
            
        Returns:
            設定が成功した場合はTrue、失敗した場合はFalse
        """
        try:
            keys = self.key_path_regex.split(key_path)
            keys = [k for k in keys if k is not None and k != '']

            current_obj = data_obj
            for i, key in enumerate(keys[:-1]): # 最後から2番目のキーまでイテレーション
                is_next_key_index = i+1 < len(keys) and keys[i+1].isdigit()

                if key.isdigit():
                    idx = int(key)
                    if isinstance(current_obj, list):
                        # 配列のサイズを拡張する必要がある場合
                        while len(current_obj) <= idx:
                            current_obj.append([] if is_next_key_index else {})
                        
                        current_obj = current_obj[idx]
                    else:
                        # 配列でない場合は自動的に配列に変換
                        if isinstance(current_obj, dict) and (key in current_obj or not current_obj):
                            # 既存のキーを保存するか、空の辞書の場合は単に上書き
                            new_list = []
                            while len(new_list) <= idx:
                                new_list.append([] if is_next_key_index else {})
                            
                            if key in current_obj:
                                parent = self.get_parent_from_path(data_obj, key_path[:key_path.find(f"[{key}]")])
                                if parent is not None:
                                    parent[self.get_last_key_from_path(key_path[:key_path.find(f"[{key}]")])] = new_list
                            else:
                                # キーが存在しないか空の辞書の場合は直接新しいリストを設定
                                current_obj = new_list
                            
                            current_obj = new_list[idx]
                        else:
                            raise IndexError(f"List index {idx} out of range or not a list at path segment '{key}' in '{key_path}'")
                elif isinstance(current_obj, dict):
                    if key not in current_obj or current_obj[key] is None:
                        # 中間層の配列または辞書を作成
                        current_obj[key] = [] if is_next_key_index else {}
                    current_obj = current_obj[key]
                else:
                    raise TypeError(f"Cannot access key/index '{key}' in non-dict/list object ({type(current_obj).__name__}) at path segment '{key}' in '{key_path}'")

            # 最終値を設定
            last_key = keys[-1]
            if last_key.isdigit():
                idx = int(last_key)
                if isinstance(current_obj, list):
                    # 配列のサイズを拡張する必要がある場合
                    while len(current_obj) <= idx:
                        current_obj.append(None)
                    current_obj[idx] = value
                else:
                    # 配列でない場合は自動的に配列に変換
                    if isinstance(current_obj, dict):
                        new_list = []
                        while len(new_list) <= idx:
                            new_list.append(None)
                        new_list[idx] = value
                        
                        # 親オブジェクトを取得して新しいリストを設定
                        parent_path = key_path[:key_path.rfind('.') if '.' in key_path else 0]
                        if parent_path:
                            parent = self.get_parent_from_path(data_obj, parent_path)
                            if parent is not None:
                                parent_key = self.get_last_key_from_path(parent_path)
                                if isinstance(parent, dict):
                                    parent[parent_key] = new_list
                                elif isinstance(parent, list) and parent_key.isdigit():
                                    parent[int(parent_key)] = new_list
                        else:
                            # ルートオブジェクトの場合
                            for k in list(current_obj.keys()):
                                del current_obj[k]
                            # データを新しいリストで更新
                            if isinstance(data_obj, dict) and len(keys) == 1:
                                data_obj[last_key] = new_list
                        
                        # current_objを更新
                        current_obj = new_list
                    else:
                        raise TypeError(f"Cannot set list index '{idx}' in non-list object ({type(current_obj).__name__}) at final path segment in '{key_path}'")
            elif isinstance(current_obj, dict):
                current_obj[last_key] = value
            else:
                raise TypeError(f"Cannot set key '{last_key}' in non-dict object ({type(current_obj).__name__}) at final path segment in '{key_path}'")
                
            return True
        except Exception as e:
            logger.error(f"Error setting value at path '{key_path}': {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def get_parent_from_path(self, data_obj: Union[Dict, List], path: str):
        """
        パスの親要素を取得するヘルパー関数
        
        Args:
            data_obj: データオブジェクト
            path: キーパス
            
        Returns:
            親オブジェクト、または取得できない場合はNone
        """
        if not path:
            return None
        
        try:
            result = self.get_value_by_path(data_obj, path, return_reference=True)
            return result.get('parent')
        except Exception:
            return None
    
    def get_last_key_from_path(self, path: str):
        """
        パスから最後のキーまたはインデックスを抽出するヘルパー関数
        
        Args:
            path: キーパス
            
        Returns:
            最後のキーまたはインデックス、取得できない場合はNone
        """
        if not path:
            return None
        
        keys = self.key_path_regex.split(path)
        keys = [k for k in keys if k is not None and k != '']
        
        if not keys:
            return None
        
        last_key = keys[-1]
        return int(last_key) if last_key.isdigit() else last_key
    
    def convert_value_based_on_type(self, value_str: Any, type_hint: Optional[str], key_path: str) -> Any:
        """
        フォームフィールドからの文字列値を指定された型に変換する
        
        Args:
            value_str: 変換する値
            type_hint: 型のヒント
            key_path: 値のキーパス
            
        Returns:
            変換された値
        """
        # 値が既に文字列でない場合はそのまま返す
        if not isinstance(value_str, str):
            return value_str

        target_type = None
        if type_hint:
            type_hint_lower = type_hint.lower()
            if type_hint_lower == "int": target_type = int
            elif type_hint_lower == "float": target_type = float
            elif type_hint_lower == "bool": target_type = bool
            elif type_hint_lower == "str" or type_hint_lower == "string": target_type = str
            elif type_hint_lower == "list": target_type = list
            elif type_hint_lower == "dict" or type_hint_lower == "object": target_type = dict

        # 型ヒントがない場合は、元のデータから型を推測
        if target_type is None and self.app_state.get("selected_node_id") and self.app_state.get("data_map"):
            try:
                original_value = self.get_value_by_path(
                    self.app_state["data_map"].get(self.app_state["selected_node_id"]), 
                    key_path
                )
                if original_value is not None:
                    target_type = type(original_value)
            except (KeyError, IndexError, TypeError):
                pass  # エラーを無視して型情報なしで続行

        # 変換を実行
        value_str_stripped = value_str.strip()

        try:
            if target_type == int:
                if not value_str_stripped: return None
                return int(float(value_str_stripped))  # 小数部を含む入力を許可
            elif target_type == float:
                if not value_str_stripped: return None
                return float(value_str_stripped)
            elif target_type == bool:
                if isinstance(value_str, bool): return value_str
                return value_str_stripped.lower() in ('true', '1', 'yes', 'on')
            elif target_type == list:
                if not value_str_stripped: return []
                return self.try_parse_json(value_str, list)
            elif target_type == dict:
                if not value_str_stripped: return {}
                return self.try_parse_json(value_str, dict)
            elif target_type == str:
                 return value_str
            else:
                # 型が不明な場合は、文字列の形式から型を推測
                if not value_str_stripped: return ""

                # 真偽値の判定
                if value_str_stripped.lower() in ('true', 'false'):
                    return value_str_stripped.lower() == 'true'
                # 整数の判定
                if value_str_stripped.isdigit() or (value_str_stripped.startswith('-') and value_str_stripped[1:].isdigit()):
                    return int(value_str_stripped)
                # 浮動小数点数の判定
                if value_str_stripped.replace('.', '', 1).replace('-', '', 1).isdigit() and value_str_stripped.count('.') <= 1:
                     try:
                          return float(value_str_stripped)
                     except ValueError:
                          pass  # 浮動小数点数ではない
                # JSONリスト/辞書の判定
                if value_str_stripped.startswith('[') and value_str_stripped.endswith(']'):
                     parsed = self.try_parse_json(value_str, list)
                     if parsed is not None: return parsed
                if value_str_stripped.startswith('{') and value_str_stripped.endswith('}'):
                     parsed = self.try_parse_json(value_str, dict)
                     if parsed is not None: return parsed

                # それ以外は文字列として返す
                return value_str

        except (ValueError, TypeError) as e:
            logger.warning(f"Conversion error for '{value_str}' to {target_type}: {e}. Returning as string.")
            return value_str  # 変換エラー時は元の文字列を返す
    
    def get_default_value_for_list_item(self, target_list: List) -> Any:
        """
        リストに追加する新しいアイテムのデフォルト値を決定する
        
        Args:
            target_list: 対象のリスト
            
        Returns:
            決定されたデフォルト値
        """
        if not target_list:  # 空リスト
            return ""  # デフォルトは空文字列

        # 既存アイテムの型をチェック
        has_dict = any(isinstance(item, dict) for item in target_list)
        has_list = any(isinstance(item, list) for item in target_list)
        has_int = any(isinstance(item, int) for item in target_list)
        has_float = any(isinstance(item, float) for item in target_list)
        has_bool = any(isinstance(item, bool) for item in target_list)
        has_str = any(isinstance(item, str) for item in target_list)

        # 複雑な型、数値型、真偽値、文字列の順で優先
        if has_dict: return {}
        if has_list: return []
        if has_int: return 0
        if has_float: return 0.0
        if has_bool: return False
        if has_str: return ""

        # フォールバック（None値や他の型のみのリスト）
        return None
    
    def get_default_value_for_type(self, type_hint: Optional[str]) -> Any:
        """
        指定された型ヒントに基づいてデフォルト値を返す
        
        Args:
            type_hint: 型ヒント文字列
            
        Returns:
            デフォルト値
        """
        if type_hint == "string":
            return ""
        elif type_hint == "int":
            return 0
        elif type_hint == "float":
            return 0.0
        elif type_hint == "bool":
            return False
        elif type_hint == "list":
            return []
        elif type_hint == "dict":
            return {}
        elif type_hint == "null":
            return None
        else:
            # 不明な型や 'any' の場合は空文字列を返す
            return ""
    
    def infer_empty_array_type(self, field_name: str, parent_path: str = "") -> Dict:
        """
        空配列のデータ型を推論する（AnalysisManagerのメソッドに委譲）
        
        Args:
            field_name: 配列のフィールド名
            parent_path: 親パスの文字列
            
        Returns:
            推論された型情報を含む辞書
        """
        # AnalysisManagerが利用可能な場合は委譲
        analysis_manager = self.app_state.get("analysis_manager")
        if analysis_manager:
            return analysis_manager.infer_empty_array_type(field_name, parent_path, self.app_state.get("raw_data"))
        
        # AnalysisManagerが利用できない場合のフォールバック
        return {
            "item_type": "dict",
            "template": {"id": "", "text": "", "description": ""},
            "confidence": 0.5
        }

    def try_parse_json(self, value: str, original_type: type) -> Any:
        """文字列をJSONとして解析し、可能であれば元の型に変換する（utils.pyより移行）"""
        
        # 空の文字列の場合
        if value == "":
            if original_type == list:
                return []
            elif original_type == dict:
                return {}
            elif original_type == int:
                return 0
            elif original_type == float:
                return 0.0
            elif original_type == bool:
                return False
            else:
                return value
        
        # Booleanの場合は特別処理
        if original_type == bool:
            if isinstance(value, str):
                lower_val = value.lower()
                if lower_val in ["true", "1", "yes", "y", "on"]:
                    return True
                elif lower_val in ["false", "0", "no", "n", "off"]:
                    return False
            return bool(value)
        
        # 数値型の場合
        if original_type == int:
            try:
                return int(float(value))  # 小数点を含む入力に対応
            except (ValueError, TypeError):
                logger.error(f"[エラー] 整数に変換できません: {value}")
                return value  # 変換できない場合は元の値を返す
        
        if original_type == float:
            try:
                return float(value)
            except (ValueError, TypeError):
                logger.error(f"[エラー] 浮動小数点数に変換できません: {value}")
                return value
        
        # JSONパースの試行
        import json
        try:
            # JSON形式として解析を試みる
            parsed = json.loads(value)
            
            # 解析結果が元の型と一致するか確認
            if original_type in (dict, list) and isinstance(parsed, original_type):
                return parsed
            
            # 型が一致しない場合は、元の文字列を返す
            logger.warning(f"[警告] 解析されたJSONの型が元の型と一致しません: parsed={type(parsed)}, target={original_type}")
            return value
        
        except json.JSONDecodeError:
            # 特殊なケース: "[]"や"{}"のような文字列が直接渡された場合
            if value.strip() == "[]" and original_type == list:
                return []
            elif value.strip() == "{}" and original_type == dict:
                return {}
            
            logger.warning(f"[警告] JSONとして解析できません: {value}")
            return value

    def get_nested_value(self, data: dict, key_path: str, default: Any = None) -> Any:
        """ドット記法でネストされた辞書のキーから値を取得する（utils.pyより移行）"""
        keys = key_path.split('.')
        value = data
        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value[key]
                else:
                    return default
            return value
        except (KeyError, TypeError):
            return default

    def on_file_selected(self, e: ft.FilePickerResultEvent):
        """
        ファイル選択時の処理
        
        Args:
            e (ft.FilePickerResultEvent): ファイル選択イベント
        """
        if not e.files or len(e.files) == 0:
            logger.error("ファイルが選択されていません")
            return
        
        file_path = e.files[0].path
        logger.info(f"ファイルが選択されました: {file_path}")
        
        # ファイルを読み込み
        success = self.load_json_file(file_path)
        
        if success:
            logger.info(f"ファイル読み込み成功: {file_path}")
            
            # UIManagerによるUI状態更新（データ変更なし）
            ui_manager = self.app_state.get("ui_manager")
            if ui_manager:
                ui_manager.handle_data_change(False)  # 読み込み時はdirty=False
                
            # ページ更新（ツリービュー更新は_process_loaded_dataで実行済み）
            if self.page:
                self.page.update()
                
            logger.debug("ファイル切り替え処理完了: UIとページの更新完了")
        else:
            logger.error(f"ファイル読み込み失敗: {file_path}")

    def extract_prefix_and_number(self, id_str: str) -> Optional[Tuple[str, int, int]]:
        """文字列IDからプレフィックス、数値、数値部分の桁数を抽出する（utils.pyより移行）"""
        import re
        match = re.match(r'^(.*?)(\d+)$', id_str)
        if match:
            prefix = match.group(1)
            number_str = match.group(2)
            number = int(number_str)
            padding = len(number_str)
            return prefix, number, padding
        return None

    def generate_next_prefixed_id(self, existing_ids: List[str]) -> Optional[str]:
        """
        既存のIDリストから最も一般的なプレフィックス+数値パターンを検出し、
        次のIDを生成する（数値は元の桁数を維持してインクリメント）（utils.pyより移行）
        """
        from collections import Counter
        patterns = Counter()
        parsed_ids = []

        for id_str in existing_ids:
            if not isinstance(id_str, str):
                continue
            parsed = self.extract_prefix_and_number(id_str)
            if parsed:
                prefix, number, padding = parsed
                patterns[(prefix, padding)] += 1
                parsed_ids.append(parsed)

        if not patterns:
            return None

        # 最も一般的なパターンを取得
        most_common_pattern, count = patterns.most_common(1)[0]
        common_prefix, common_padding = most_common_pattern

        # 最も一般的なパターンに一致するIDのみをフィルタリング
        relevant_ids = [p for p in parsed_ids if p[0] == common_prefix and p[2] == common_padding]

        if not relevant_ids:
            return None

        # 最大の数値を持つIDを見つける
        max_number = -1
        for _, number, _ in relevant_ids:
            if number > max_number:
                max_number = number

        # 次の数値を計算し、パディングを適用して新しいIDを生成
        next_number = max_number + 1
        next_id_str = f"{common_prefix}{str(next_number).zfill(common_padding)}"

        # 生成されたIDが既存IDと重複しないか確認
        if next_id_str in existing_ids:
            logger.warning(f"Warning: Generated next ID '{next_id_str}' already exists. Falling back.")
            return None

        return next_id_str


def create_data_manager(app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None) -> DataManager:
    """DataManagerのインスタンスを作成する工場関数"""
    data_manager = DataManager(app_state, ui_controls, page)
    app_state["data_manager"] = data_manager
    return data_manager