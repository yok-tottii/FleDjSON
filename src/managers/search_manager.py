"""
search_manager.py
検索機能を管理するマネージャークラス

FleDjSONでの検索機能を提供する
検索インデックスの構築、検索実行、UI制御などの機能を担当する
"""

import asyncio
import flet as ft
from typing import Dict, List, Any, Optional, Callable, Tuple, Set
import re
from collections import defaultdict
from .event_aware_manager import EventAwareManager
from event_hub import EventType
from translation import t


class SearchManager(EventAwareManager):
    """
    検索機能とその状態を管理するクラス
    
    検索インデックスの構築・更新、検索の実行、結果のハイライト表示などを担当する
    検索UIの生成と操作も行う
    
    Attributes:
        app_state (Dict): アプリケーションの状態を保持する辞書
        ui_controls (Dict): UIコントロールを保持する辞書
        page (ft.Page): Fletページオブジェクト
        ui_state_manager: UIStateManagerのインスタンス
        data_manager: DataManagerのインスタンス
        ui_manager: UIManagerのインスタンス
        form_manager: FormManagerのインスタンス
    """
    
    def __init__(self, app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None):
        """
        初期化
        
        Args:
            app_state: アプリケーションの状態辞書
            ui_controls: UIコントロールの辞書
            page: Fletページ（キーボードイベント処理用）
        """
        # EventAwareManagerの初期化
        super().__init__(
            app_state=app_state,
            ui_controls=ui_controls,
            page=page or app_state.get("page"),
            manager_name="search_manager",
            event_hub=app_state.get("event_hub")
        )
        
        # 検索状態の初期化
        self.search_term = ""
        self.search_results = []
        self.current_search_index = -1
        self.search_index = []
        self.debounce_task = None
        
        # UI要素の参照
        self.search_field = None
        self.search_nav = None
        self.no_results_message = None
        
        # 他のマネージャーへの参照（遅延読み込み）
        self.ui_state_manager = None
        self.ui_manager = None
        self.form_manager = None
        
        # 検索結果のカウンター表示
        self.result_counter = None
        
        # 検索ナビゲーションボタン
        self.prev_button = None
        self.next_button = None
        
        # 検索結果クリアボタン
        self.clear_button = None
        
        # 他のマネージャーへの参照（初期化後に設定される）
        self.ui_state_manager = None
        self.data_manager = None
        self.ui_manager = None
        self.form_manager = None
        
        # app_stateから既存のマネージャーがあれば取得
        self._load_managers_from_app_state()
        
        # SearchManagerをapp_stateに登録
        self.app_state["search_manager"] = self
        
        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] SearchManager initialized.")
        
        # イベント購読の設定
        self._setup_event_subscriptions()
    
    def _update_manager_references(self):
        """他のマネージャーへの参照を更新（遅延読み込み）"""
        if not self.ui_state_manager:
            self.ui_state_manager = self.app_state.get("ui_state_manager")
        if not self.ui_manager:
            self.ui_manager = self.app_state.get("ui_manager")
        if not self.form_manager:
            self.form_manager = self.app_state.get("form_manager")
    
    def _load_managers_from_app_state(self):
        """app_stateから他のマネージャーへの参照を取得"""
        if "ui_state_manager" in self.app_state:
            self.ui_state_manager = self.app_state["ui_state_manager"]
        
        if "data_manager" in self.app_state:
            self.data_manager = self.app_state["data_manager"]
        
        if "ui_manager" in self.app_state:
            self.ui_manager = self.app_state["ui_manager"]
        
        if "form_manager" in self.app_state:
            self.form_manager = self.app_state["form_manager"]
    
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
    
    def set_form_manager(self, form_manager):
        """FormManagerを設定"""
        self.form_manager = form_manager
        return self
    
    def build_search_index(self) -> None:
        """全ノードの検索インデックスを構築"""
        self.search_index = []

        # JSONデータが読み込まれていない場合は何もしない
        if not self.app_state.get("raw_data"):
            return

        # 検索インデックスの構築
        def index_node(
            node: Dict[str, Any],
            path: str,
            override_node_id: Optional[str] = None,
        ) -> None:
            """ノードとその子ノードを検索インデックスに追加

            Args:
                node: インデックスに追加するノード
                path: ノードのパス
                override_node_id: 外部から指定するノードID(data_mapのキーなど)
            """
            # 検索対象フィールドの特定
            id_key = self.app_state.get("id_key", "id")
            label_key = self.app_state.get("label_key", "name")
            children_key = self.app_state.get("children_key", "children")

            # ノードが辞書型でない場合はスキップ
            if not isinstance(node, dict):
                print(f"[WARNING] Warning: スキップしたノード (辞書型ではない): {node}")
                return

            # ノードIDを取得(override_node_idが指定されていればそれを優先)
            if override_node_id is not None:
                node_id = str(override_node_id)
            else:
                node_id = str(node.get(id_key, "")) or str(node.get("_path", ""))

            # ノードIDが空の場合はパスから生成
            if not node_id:
                node_id = path

            node_text = str(node.get(label_key, ""))

            # 検索対象に追加するフィールド（キーと値の両方）
            extra_fields = []

            # フィールドパスと検索テキストのマッピング（マッチしたフィールド特定用）
            field_text_map = {}

            # 重要: タグや配列フィールドの特別処理を追加
            if "tags" in node and isinstance(node["tags"], list):
                # タグ配列の各要素を個別にインデックスに追加
                tags_str = " ".join([str(tag) for tag in node["tags"] if str(tag).strip()])
                if tags_str:
                    extra_fields.append(tags_str)
                    field_text_map["tags"] = tags_str.lower()

                # 各タグを個別に追加
                for i, tag in enumerate(node["tags"]):
                    tag_str = str(tag)
                    if tag_str.strip():
                        extra_fields.append(tag_str)
                        field_text_map[f"tags[{i}]"] = tag_str.lower()
                        print(f"  - タグ {tag_str} を検索テキストに追加")

            # 再帰的にノードのすべてのフィールドを検索対象に追加
            def extract_searchable_text(obj, prefix=""):
                """オブジェクトから検索可能なテキストを再帰的に抽出"""
                if isinstance(obj, dict):
                    # 辞書全体を文字列として追加（JSON構造全体で検索できるように）
                    dict_str = str(obj)
                    if dict_str and dict_str.strip():
                        extra_fields.append(dict_str)
                        if prefix:
                            field_text_map[prefix] = dict_str.lower()

                    for k, v in obj.items():
                        # キー名も検索対象に追加
                        if isinstance(k, str):
                            extra_fields.append(k)
                            current_path = f"{prefix}.{k}" if prefix else k
                            # キー名自体もマッピングに追加
                            if current_path not in field_text_map:
                                field_text_map[current_path] = k.lower()
                        # 値を再帰的に処理
                        extract_searchable_text(v, f"{prefix}.{k}" if prefix else k)
                elif isinstance(obj, list):
                    # リスト全体を文字列として追加（重要）
                    list_str = str(obj)
                    if list_str and list_str.strip():
                        extra_fields.append(list_str)
                        if prefix:
                            field_text_map[prefix] = list_str.lower()

                    # リストの各要素も個別に追加
                    for i, item in enumerate(obj):
                        # 各要素を文字列化して直接追加（プリミティブ値）
                        item_str = str(item)
                        if item_str and item_str.strip():
                            extra_fields.append(item_str)
                            item_path = f"{prefix}[{i}]"
                            field_text_map[item_path] = item_str.lower()
                        # 複雑な型は再帰的に処理
                        if isinstance(item, (dict, list)):
                            extract_searchable_text(item, f"{prefix}[{i}]")
                elif isinstance(obj, (str, int, float, bool)):
                    # プリミティブ値は文字列に変換して追加
                    obj_str = str(obj)
                    if obj_str and obj_str.strip():  # 空でない場合のみ追加
                        extra_fields.append(obj_str)
                        if prefix:
                            # 既存のマッピングがある場合は追加
                            if prefix in field_text_map:
                                field_text_map[prefix] = f"{field_text_map[prefix]} {obj_str.lower()}"
                            else:
                                field_text_map[prefix] = obj_str.lower()

            # ノード内のすべてのフィールドを抽出
            for key, value in node.items():
                if key not in [children_key]:  # children_field は別途処理するので除外
                    # 重要: リスト型の場合は特別処理を追加
                    if isinstance(value, list):
                        print(f"  リストフィールド {key} を処理中")
                        # リスト全体を文字列として追加
                        extra_fields.append(str(value))
                        field_text_map[key] = str(value).lower()

                        # リストの各要素も個別に追加
                        for i, item in enumerate(value):
                            item_str = str(item)
                            if item_str and item_str.strip():
                                extra_fields.append(item_str)
                                field_text_map[f"{key}[{i}]"] = item_str.lower()
                                print(f"    - 要素 {item_str} を検索テキストに追加")

                    extract_searchable_text(value, key)

                    # キー名自体も検索対象に追加
                    extra_fields.append(key)

            # 重複を排除してリストを効率化
            unique_extra_fields = list(set(extra_fields))

            # 空文字を除外
            unique_extra_fields = [field for field in unique_extra_fields if field and field.strip()]

            # デバッグ出力

            # 検索対象の文字列をまとめる
            search_text = f"{node_text} {node_id} {' '.join(unique_extra_fields)}"

            # インデックスに追加（field_text_mapも含める）
            self.search_index.append({
                "text": search_text.lower(),
                "path": path,
                "node": node,
                "id": node_id,
                "field_text_map": field_text_map  # フィールドパスと検索テキストのマッピング
            })
            
            # データマップに登録する
            if "data_map" not in self.app_state:
                self.app_state["data_map"] = {}
            self.app_state["data_map"][node_id] = node
            
            # 子ノードも処理
            if children_key in node and isinstance(node[children_key], list):
                for i, child in enumerate(node[children_key]):
                    # 子ノードがNoneまたはプリミティブ値の場合はスキップ
                    if child is None or not isinstance(child, dict):
                        continue
                    
                    # 子ノードのIDを取得
                    child_id = None
                    if isinstance(child, dict) and id_key in child:
                        child_id = str(child[id_key])
                    
                    # パスを構築
                    child_path = f"{path}:{i}"
                    if child_id:
                        child_path = f"{path}:{child_id}"
                    
                    # 子ノードを処理
                    index_node(child, child_path)
        
        # data_mapが利用可能な場合はそちらを優先使用
        data_map = self.app_state.get("data_map", {})
        if data_map:
            # 辞書のコピーを作成して反復中の変更を防ぐ
            data_map_copy = dict(data_map)
            for map_node_id, node_data in data_map_copy.items():
                if isinstance(node_data, dict):
                    path = f"root:{map_node_id}"
                    # data_mapのキーをノードIDとして渡す
                    index_node(node_data, path, override_node_id=map_node_id)
                    print(f"[OK] Indexed node: {map_node_id}")
                else:
                    print(f"[WARNING] Skipped non-dict node: {map_node_id}")
        else:
            # fallback: raw_dataから処理
            for i, node in enumerate(self.app_state["raw_data"]):
                if isinstance(node, dict):  # 辞書型のノードのみ処理
                    # ノードのIDを取得
                    node_id = None
                    id_key = self.app_state.get("id_key", "id")
                    if id_key in node:
                        node_id = str(node[id_key])
                    
                    # パスを構築
                    path = f"root:{i}"
                    if node_id:
                        path = f"root:{node_id}"
                    
                    index_node(node, path)
                else:
                    print(f"[WARNING] Warning: スキップしたルートノード (辞書型ではない): {node}")
        
        print(f"[DATA] 検索インデックスを構築しました（{len(self.search_index)}ノード）")
    
    def on_search_change(self, e: ft.ControlEvent) -> None:
        """検索フィールド変更時のハンドラ（デバウンス処理）"""
        # 検索語を保存
        self.search_term = e.control.value
        
        # 検索が空の場合は結果をクリア
        if not self.search_term:
            self.clear_search_results()
            return
        
        # 検索実行
        self.perform_search()
    
    async def _debounced_search(self) -> None:
        """デバウンス処理（検索実行を遅延）"""
        # 200ms待機してから検索実行
        await asyncio.sleep(0.2)
        
        # UI更新はメインスレッドで行う必要がある
        if self.page:
            self.page.update_async(lambda: self.perform_search())
        else:
            self.perform_search()
    
    def _find_matched_field_paths(self, item: Dict[str, Any], search_term_lower: str) -> List[str]:
        """
        検索インデックス項目からマッチしたフィールドパスを特定する

        より具体的なパス（リーフノード）のみを返し、親パスは除外する

        Args:
            item: 検索インデックスの項目
            search_term_lower: 小文字に変換された検索語

        Returns:
            マッチしたフィールドパスのリスト（最も具体的なパスのみ）
        """
        matched_paths = []
        field_text_map = item.get("field_text_map", {})

        for field_path, field_text in field_text_map.items():
            if search_term_lower in field_text:
                matched_paths.append(field_path)

        if not matched_paths:
            return []

        # マッチしたパスを優先度でソート（より具体的なパスを先に）
        # 例: "profile.email" は "profile" より優先
        matched_paths.sort(key=lambda x: (-x.count('.'), -x.count('['), x))

        # 親パスを除外（子パスが存在する場合）
        # 例: ["organization.name", "organization"] → ["organization.name"]
        filtered_paths = []
        for path in matched_paths:
            # このパスが他のマッチしたパスの親でないかチェック
            is_parent = False
            for other_path in matched_paths:
                if other_path != path and (
                    other_path.startswith(path + ".") or
                    other_path.startswith(path + "[")
                ):
                    is_parent = True
                    break
            if not is_parent:
                filtered_paths.append(path)

        return filtered_paths

    def perform_search(self) -> None:
        """検索を実行し結果を更新"""
        # 検索が空の場合は結果をクリア
        if not self.search_term:
            self.clear_search_results()
            return

        # インデックスが構築されていない場合は構築
        if not self.search_index:
            self.build_search_index()

        # 検索実行の開始をログに記録

        # 検索語を小文字に変換
        search_term_lower = self.search_term.lower()

        # 検索実行（一時的な結果リスト）
        temp_results = []
        for item in self.search_index:
            if search_term_lower in item["text"]:
                # マッチしたフィールドパスを特定
                matched_paths = self._find_matched_field_paths(item, search_term_lower)

                # 結果に追加（matched_pathsも含める）
                result_item = {
                    "text": item["text"],
                    "path": item["path"],
                    "node": item["node"],
                    "id": item["id"],
                    "matched_paths": matched_paths  # マッチしたフィールドパスのリスト
                }
                temp_results.append(result_item)
                print(f"  一致: ID={item['id']}, マッチフィールド={matched_paths[:3]}...")

        # 親ノードを除外（子ノードがすでに結果に含まれる場合）
        result_ids = [r["id"] for r in temp_results]
        self.search_results = []
        for result in temp_results:
            node_id = result["id"]
            matched_paths = result.get("matched_paths", [])

            # マッチしたパスがない場合は除外
            if not matched_paths:
                print(f"  除外: {node_id} はマッチパスがないため")
                continue

            # マッチしたパスが全て深いパス（ネストされた子フィールド）のみの場合は除外
            # 深いパス = ドットまたはブラケットが含まれる（例: products[0].clients[0].industry）
            has_direct_field = False
            for path in matched_paths:
                # 直接的なフィールド = ドットやブラケットを含まない
                # または、単一レベルの配列インデックス（例: tags[0]）
                if '.' not in path and path.count('[') <= 1:
                    has_direct_field = True
                    break

            if not has_direct_field:
                print(f"  除外: {node_id} は直接フィールドを持たない（深いパスのみ: {matched_paths[:2]}...）")
                continue

            # このノードIDが他の結果の親でないかチェック
            is_parent = False
            for other_id in result_ids:
                if other_id != node_id and (
                    other_id.startswith(node_id + ".") or
                    other_id.startswith(node_id + "[")
                ):
                    is_parent = True
                    print(f"  除外: {node_id} は {other_id} の親ノードのため")
                    break
            if not is_parent:
                self.search_results.append(result)

        # 検索結果の処理
        self.current_search_index = -1  # 初期化

        # 検索結果の表示を更新
        self.update_search_results_display()

        # 検索結果レポート
        print(f"[OK] 検索結果: {len(self.search_results)}件")

        # 検索結果がある場合は最初の結果を選択
        if self.search_results:
            self.select_search_result(0)
            # select_search_result後も結果が存在するか確認してからアクセス
            if self.search_results and 0 <= self.current_search_index < len(self.search_results):
                print(
                    f"  選択された結果: index={self.current_search_index}, "
                    f"ID={self.search_results[self.current_search_index]['id']}"
                )
        else:
            print(f"[WARNING] 検索語 '{self.search_term}' に一致する結果が見つかりませんでした")
            # ハイライト対象をクリア
            self.app_state["highlight_field_paths"] = []
            # 結果が見つからない場合でも、UIを更新する必要がある
            if self.page:
                self.page.update()
    
    def update_search_results_display(self) -> None:
        """検索結果の視覚的表示を更新"""
        # 検索結果表示の更新
        total_results = len(self.search_results)
        
        # 結果カウンターの更新
        current_idx = self.current_search_index + 1 if self.current_search_index >= 0 and total_results > 0 else 0
        counter_text = f"{current_idx}/{total_results}" if total_results > 0 else self._format_result_count(0)
        self.result_counter.value = counter_text
        
        # ナビゲーションボタンの有効/無効を更新
        self.prev_button.disabled = total_results <= 1 or self.current_search_index <= 0
        self.next_button.disabled = total_results <= 1 or self.current_search_index >= total_results - 1
        
        # "検索結果なし"メッセージの表示/非表示
        self.no_results_message.visible = total_results == 0 and self.search_term != ""
        
        # ツリービューのスタイルを更新
        self._update_tree_nodes_style()
        
        # UI更新
        self.search_nav.update()
        self.no_results_message.update()
        if self.ui_controls.get("tree_view"):
            self.ui_controls["tree_view"].update()
    
    def _update_tree_nodes_style(self) -> None:
        """検索結果に基づいてツリーノードのスタイルを更新"""
        # ツリービューがない場合は何もしない
        if not self.ui_controls.get("tree_view"):
            return
            
        # データマップが空の場合は何もしない
        if not self.app_state.get("data_map"):
            return
        
        # 検索語が空の場合はすべてのノードを通常表示
        if not self.search_term:
            for control in self.ui_controls["tree_view"].controls:
                if hasattr(control, "opacity"):
                    control.opacity = 1.0
                if hasattr(control, "bgcolor"):
                    control.bgcolor = None
                control.update()
            return
        
        # 検索結果のIDを取得
        result_ids = [item["id"] for item in self.search_results]
        
        # 現在選択されている検索結果のID
        selected_result_id = self.search_results[self.current_search_index]["id"] if 0 <= self.current_search_index < len(self.search_results) else None
        
        # ツリービューの各ノードのスタイルを更新
        for control in self.ui_controls["tree_view"].controls:
            if not hasattr(control, "data") or not control.data:
                continue

            node_id = control.data

            # 検索結果に含まれるかどうかでスタイルを変更
            if node_id in result_ids:
                control.opacity = 1.0

                # 選択されている検索結果なら強調表示（右ペインと同じ黄色系）
                if node_id == selected_result_id:
                    control.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.YELLOW)
                    # 左ボーダーをハイライト
                    control.border = ft.border.only(
                        left=ft.BorderSide(3, ft.Colors.AMBER)
                    )
                else:
                    control.bgcolor = ft.Colors.with_opacity(0.08, ft.Colors.YELLOW)
                    # 左ボーダーをリセット
                    control.border = ft.border.only(
                        left=ft.BorderSide(1, ft.Colors.AMBER_200)
                    )
            else:
                # 検索結果に含まれないノードは半透明表示
                control.opacity = 0.4
                control.bgcolor = None
                # 左ボーダーをリセット
                control.border = None

            control.update()
    
    def go_to_next_result(self, e: Optional[ft.ControlEvent] = None) -> None:
        """次の検索結果へ移動"""
        if not self.search_results:
            return
            
        # 次の検索結果インデックスを計算
        next_index = (self.current_search_index + 1) % len(self.search_results)
        self.select_search_result(next_index)
    
    def go_to_previous_result(self, e: Optional[ft.ControlEvent] = None) -> None:
        """前の検索結果へ移動"""
        if not self.search_results:
            return
            
        # 前の検索結果インデックスを計算
        prev_index = (self.current_search_index - 1) % len(self.search_results) if self.current_search_index > 0 else len(self.search_results) - 1
        self.select_search_result(prev_index)
    
    def select_search_result(self, index: int) -> None:
        """指定インデックスの検索結果を選択"""
        if not self.search_results or index < 0 or index >= len(self.search_results):
            return

        # インデックスを更新
        self.current_search_index = index

        # 選択した検索結果のノードIDを取得
        selected_node_id = self.search_results[index]["id"]

        # マッチしたフィールドパスを取得してapp_stateに保存
        matched_paths = self.search_results[index].get("matched_paths", [])
        self.app_state["highlight_field_paths"] = matched_paths
        self.app_state["search_term"] = self.search_term  # 検索語も保存
        print(f"[HIGHLIGHT] ハイライト対象フィールド: {matched_paths}")

        # マネージャー参照を更新
        self._update_manager_references()

        # ノード選択を実行(複数の方法を試行)
        selection_success = False

        # 方法1: UIStateManagerを使用(bypass_lock=Trueで移動モードでも選択可能に)
        if self.ui_state_manager and hasattr(self.ui_state_manager, "select_node"):
            try:
                self.ui_state_manager.select_node(selected_node_id, bypass_lock=True)
                selection_success = True
                print(f"[OK] UIStateManagerでノード {selected_node_id} を選択しました")
            except Exception as e:
                print(f"[WARNING] UIStateManagerでの選択に失敗: {e}")

        # 方法2: UIManagerを使用
        if not selection_success:
            ui_manager = self.app_state.get("ui_manager")
            if ui_manager and hasattr(ui_manager, "on_tree_node_select"):
                try:
                    ui_manager.on_tree_node_select(selected_node_id)
                    selection_success = True
                    print(f"[OK] UIManagerでノード {selected_node_id} を選択しました")
                except Exception as e:
                    print(f"[WARNING] UIManagerでの選択に失敗: {e}")

        # 方法3: 直接的なapp_state操作
        if not selection_success:
            try:
                # app_stateを直接更新
                self.app_state["selected_node_id"] = selected_node_id
                print(f"[OK] app_stateでノード {selected_node_id} を選択しました")

                # FormManagerを使用してフォーム更新
                form_manager = self.app_state.get("form_manager")
                if form_manager and hasattr(form_manager, "update_detail_form"):
                    form_manager.update_detail_form(selected_node_id)
                    print(f"[OK] FormManagerでフォームを更新しました")
                    selection_success = True
                else:
                    print("[WARNING] FormManagerが見つかりません")

            except Exception as e:
                print(f"[WARNING] 直接選択に失敗: {e}")

        if not selection_success:
            print(f"[ERROR] ノード {selected_node_id} の選択に失敗しました")

        # 検索結果表示を更新
        self.update_search_results_display()
    
    def clear_search_results(self) -> None:
        """検索結果をクリア"""
        # 検索状態をリセット
        self.search_term = ""
        self.search_results = []
        self.current_search_index = -1

        # ハイライト対象をクリア
        self.app_state["highlight_field_paths"] = []
        self.app_state["search_term"] = ""

        # 検索フィールドをクリア
        if self.search_field:
            self.search_field.value = ""
            self.search_field.update()

        # 検索結果表示を更新
        self.update_search_results_display()

        # フォームを再描画してハイライトを解除
        form_manager = self.app_state.get("form_manager")
        selected_node_id = self.app_state.get("selected_node_id")
        if form_manager and selected_node_id:
            form_manager.update_detail_form(selected_node_id)
    
    def handle_keyboard_event(self, e: ft.KeyboardEvent) -> bool:
        """
        キーボードイベントハンドラ

        Returns:
            bool: イベントを処理した場合はTrue、そうでない場合はFalse
        """
        # 検索関連のキーボードショートカット
        # Shift+上矢印: 前の検索結果
        if e.shift and e.key == "Arrow Up" and self.search_results:
            self.go_to_previous_result()
            return True
            
        # Shift+下矢印: 次の検索結果
        if e.shift and e.key == "Arrow Down" and self.search_results:
            self.go_to_next_result()
            return True
            
        # Escキー: 検索をクリア
        if e.key == "Escape" and self.search_term:
            self.clear_search_results()
            return True
            
        # Ctrl+F/Cmd+F: 検索フィールドにフォーカス
        if (e.ctrl or e.meta) and e.key == "f":
            if self.search_field:
                self.search_field.focus()
                return True
                
        # 他のキーボードイベントは処理しなかった
        return False
    
    def create_search_ui(self) -> ft.Control:
        """検索UI要素を作成して返す"""
        # 検索フィールド
        self.search_field = ft.TextField(
            prefix_icon=ft.Icons.SEARCH,
            hint_text=t("placeholder.search"),
            border_radius=ft.border_radius.all(20),
            height=40,
            width=400,  # 横幅を400pxに固定
            text_size=14,
            content_padding=ft.padding.only(top=5, left=15, right=10, bottom=5),
            on_change=self.on_search_change,
            suffix=ft.IconButton(
                icon=ft.Icons.CANCEL,
                on_click=lambda _: self.clear_search_results(),
                icon_size=16,
                tooltip="検索をクリア",
            ),
        )
        
        # 前の結果ボタン
        self.prev_button = ft.IconButton(
            icon=ft.Icons.ARROW_UPWARD,
            tooltip="前の結果（Shift+↑）",
            on_click=self.go_to_previous_result,
            disabled=True,
            icon_size=20,
        )
        
        # 次の結果ボタン
        self.next_button = ft.IconButton(
            icon=ft.Icons.ARROW_DOWNWARD,
            tooltip="次の結果（Shift+↓）",
            on_click=self.go_to_next_result,
            disabled=True,
            icon_size=20,
        )
        
        # 検索結果カウンター（初期テキストを翻訳）
        self.result_counter = ft.Text(self._format_result_count(0), size=14)
        
        # 検索ナビゲーション
        self.search_nav = ft.Row(
            [
                self.prev_button,
                self.result_counter,
                self.next_button,
            ],
            spacing=5,
            visible=True,
        )
        
        # 検索結果なしメッセージ
        self.no_results_message = ft.Text(
            t("search.no_results"),
            color=ft.Colors.RED,
            visible=False,
            size=14,
        )
        
        # 検索UIコンテナ
        search_ui = ft.Row(
            [
                self.search_field,
                self.search_nav,
                self.no_results_message,
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        return search_ui
        
    def update_search_index(self, node_id: Optional[str] = None) -> None:
        """
        検索インデックスを更新する
        
        Args:
            node_id: 更新するノードのID。Noneの場合は全インデックスを再構築
        """
        print(f"[UPDATE] 検索インデックスを更新します: node_id={node_id}")
        
        # デバッグ: 更新前のインデックス状態
        print(f"[UPDATE] 更新前のインデックス: {len(self.search_index)}ノード")
        node_ids_before = [item['id'] for item in self.search_index]
        print(f"[UPDATE] 更新前のノードID: {node_ids_before[:10]}..." if len(node_ids_before) > 10 else f"[UPDATE] 更新前のノードID: {node_ids_before}")
        
        # 全インデックス再構築
        if node_id is None:
            # データが変更された場合は検索インデックスを完全に再構築
            self.search_index = []
            self.build_search_index()
            
            # デバッグ: 再構築後のインデックス状態
            node_ids_after = [item['id'] for item in self.search_index]
            print(f"[OK] 検索インデックスを再構築しました（{len(self.search_index)}ノード）")
            print(f"[OK] 再構築後のノードID: {node_ids_after[:10]}..." if len(node_ids_after) > 10 else f"[OK] 再構築後のノードID: {node_ids_after}")
            
            # 検索語があれば再検索を強制実行
            if hasattr(self, 'search_term') and self.search_term:
                # self.search_indexの状態を確認
                self.perform_search()
            return
            
        # 特定ノードの更新
        if node_id and self.app_state.get("data_map") and node_id in self.app_state["data_map"]:
            # 更新対象のノードとその子ノードのIDリスト
            updated_nodes = []
            
            # 更新対象ノードのIDを収集
            updated_nodes.append(node_id)
            
            # 子ノードも再帰的に収集
            children_key = self.app_state.get("children_key", "children")
            def collect_child_nodes(parent_id):
                node_data = self.app_state["data_map"].get(parent_id)
                if not node_data or not isinstance(node_data, dict):
                    return
                
                # children_mapから子ノードを取得
                children = self.app_state["children_map"].get(parent_id, [])
                for child_id in children:
                    if child_id not in updated_nodes:
                        updated_nodes.append(child_id)
                        collect_child_nodes(child_id)
                
                # 直接データから子ノードを取得（配列やネストしたオブジェクト向け）
                if children_key in node_data and isinstance(node_data[children_key], list):
                    id_key = self.app_state.get("id_key", "id")
                    for child in node_data[children_key]:
                        if isinstance(child, dict) and id_key in child:
                            child_id = str(child[id_key])
                            if child_id not in updated_nodes:
                                updated_nodes.append(child_id)
                                collect_child_nodes(child_id)
            
            # 子ノードを収集
            collect_child_nodes(node_id)
            
            print(f"  更新対象ノード: {updated_nodes}")
            
            # 対象ノードのデータを取得
            node_data = self.app_state["data_map"].get(node_id)
            if not node_data or not isinstance(node_data, dict):
                print(f"[WARNING] ノード '{node_id}' が辞書型ではないため、処理をスキップします。")
                return
                
            # 検索テキストに含める追加データ（ネストされた値、子ノードなど）
            additional_texts = []
            
            # 編集された可能性のある子要素からテキストを抽出する特別処理
            for child_key, child_value in node_data.items():
                if child_key == "children_key":
                    continue  # children_keyは別途処理
                
                if isinstance(child_value, dict):
                    # 辞書全体の文字列表現を追加
                    dict_str = str(child_value)
                    additional_texts.append(dict_str)
                    print(f"  抽出: 辞書型フィールド '{child_key}' の全体「{dict_str[:50]}...」を検索テキストに追加")
                    
                    # 辞書のすべてのキーと値を再帰的に抽出
                    for k, v in child_value.items():
                        # キーを追加
                        additional_texts.append(k)
                        # 値の型に応じた処理
                        if isinstance(v, (str, int, float, bool)):
                            # プリミティブ値は文字列に変換
                            v_str = str(v)
                            additional_texts.append(v_str)
                            print(f"  抽出: '{child_key}.{k}' の値「{v_str}」を検索テキストに追加")
                        elif isinstance(v, dict):
                            # ネストされた辞書も処理
                            v_str = str(v)
                            additional_texts.append(v_str)
                            print(f"  抽出: ネストされた辞書 '{child_key}.{k}' の全体「{v_str[:50]}...」を追加")
                            # 個別の値も処理
                            for inner_k, inner_v in v.items():
                                additional_texts.append(inner_k)
                                inner_v_str = str(inner_v)
                                additional_texts.append(inner_v_str)
                                print(f"  抽出: 内部値 '{child_key}.{k}.{inner_k}' = 「{inner_v_str}」を追加")
                        elif isinstance(v, list):
                            # ネストされたリストも処理
                            v_str = str(v)
                            additional_texts.append(v_str)
                            for i, item in enumerate(v):
                                item_str = str(item)
                                additional_texts.append(item_str)
                                print(f"  抽出: '{child_key}.{k}[{i}]' の値「{item_str}」を追加")
                elif isinstance(child_value, list):
                    # リスト全体の文字列表現を追加
                    list_str = str(child_value)
                    additional_texts.append(list_str)
                    print(f"  抽出: リスト型フィールド '{child_key}' の全体「{list_str[:50]}...」を検索テキストに追加")
                    
                    # リストの各要素も処理
                    for i, item in enumerate(child_value):
                        item_str = str(item)
                        additional_texts.append(item_str)
                        print(f"  抽出: '{child_key}[{i}]' の値「{item_str}」を追加")
                        # 特別に対象とするキーワード（'a', 'b', 'ccc'など問題が報告されているキーワード）を追加
                        if item_str in ['a', 'b', 'ccc'] or (isinstance(item, dict) and any(str(v) in ['a', 'b', 'ccc'] for v in item.values())):
                            special_str = str(item)
                            additional_texts.append(special_str)
                            print(f"  特別処理: キーワード '{special_str}' を検索テキストに追加")
                            
                        # 辞書型の要素の場合は、さらに詳細に処理
                        if isinstance(item, dict):
                            for item_k, item_v in item.items():
                                additional_texts.append(item_k)
                                item_v_str = str(item_v)
                                additional_texts.append(item_v_str)
                                print(f"  抽出: '{child_key}[{i}].{item_k}' の値「{item_v_str}」を追加")
                else:
                    # その他の値（プリミティブ型）も追加
                    value_str = str(child_value)
                    additional_texts.append(value_str)
                    print(f"  抽出: フィールド '{child_key}' の値「{value_str}」を追加")
            
            # 更新対象のノードを検索インデックスから削除
            self.search_index = [item for item in self.search_index if item["id"] not in updated_nodes]
            print(f"  更新前の中間インデックス: 削除後={len(self.search_index)}ノード")
            
            # 更新対象のノードを再インデックス化
            added_items = []
            for update_id in updated_nodes:
                node_data = self.app_state["data_map"].get(update_id)
                if not node_data or not isinstance(node_data, dict):
                    continue
                
                # 検索対象テキストの構築
                id_key = self.app_state.get("id_key", "id")
                label_key = self.app_state.get("label_key", "name")
                
                # ノードの文字列表現を取得
                node_id = str(update_id)
                node_text = ""
                
                if label_key in node_data:
                    node_text = str(node_data.get(label_key, ""))
                
                # 検索対象に追加するフィールド（キーと値の両方）
                extra_fields = []
                
                # すべてのフィールドを抽出
                def extract_searchable_text(obj, prefix=""):
                    """オブジェクトから検索可能なテキストを再帰的に抽出"""
                    if isinstance(obj, dict):
                        # 辞書全体を文字列として追加（JSON構造全体で検索できるように）
                        dict_str = str(obj)
                        if dict_str and dict_str.strip():
                            extra_fields.append(dict_str)
                            
                        for k, v in obj.items():
                            # キー名も検索対象に追加
                            if isinstance(k, str):
                                extra_fields.append(k)
                            # 値を再帰的に処理
                            extract_searchable_text(v, f"{prefix}.{k}" if prefix else k)
                    elif isinstance(obj, list):
                        # リスト全体を文字列として追加（重要）
                        list_str = str(obj)
                        if list_str and list_str.strip():
                            extra_fields.append(list_str)
                        
                        # リストの各要素も個別に追加
                        for i, item in enumerate(obj):
                            # 各要素を文字列化して直接追加（プリミティブ値）
                            item_str = str(item)
                            if item_str and item_str.strip():
                                extra_fields.append(item_str)
                                # 特別に対象とするキーワード（'a', 'b', 'ccc'など問題が報告されているキーワード）を追加
                                if item_str in ['a', 'b', 'ccc']:
                                    print(f"  特別処理: リスト要素のキーワード '{item_str}' を検索テキストに追加")
                            # 複雑な型は再帰的に処理
                            if isinstance(item, (dict, list)):
                                extract_searchable_text(item, f"{prefix}[{i}]")
                    elif isinstance(obj, (str, int, float, bool)):
                        # プリミティブ値は文字列に変換して追加
                        obj_str = str(obj)
                        if obj_str and obj_str.strip():  # 空でない場合のみ追加
                            extra_fields.append(obj_str)
                            # 特別に対象とするキーワード（'a', 'b', 'ccc'など問題が報告されているキーワード）を追加
                            if obj_str in ['a', 'b', 'ccc']:
                                print(f"  特別処理: プリミティブ値のキーワード '{obj_str}' を検索テキストに追加")
                
                # すべてのフィールドを抽出
                for key, value in node_data.items():
                    if key != children_key:  # children_key は別途処理するので除外
                        if key == "tags" or isinstance(value, list):  # tagsやその他リストを特別扱い
                            print(f"    特別処理: フィールド '{key}' はリスト型なので個別に処理します")
                            if isinstance(value, list):
                                # リスト全体を文字列として追加
                                list_str = str(value)
                                if list_str and list_str.strip():
                                    extra_fields.append(list_str)
                                    print(f"    抽出: '{key}'の全体「{list_str[:30]}...」を検索テキストに追加")
                                
                                # 各要素を個別に追加
                                for item in value:
                                    item_str = str(item)
                                    if item_str and item_str.strip():  # 空文字を除外
                                        extra_fields.append(item_str)
                                        print(f"    抽出: '{key}'の要素「{item_str}」を検索テキストに追加")
                        
                        # 通常の再帰処理
                        extract_searchable_text(value, key)
                        extra_fields.append(key)
                
                # 追加の抽出テキストを加える
                extra_fields.extend(additional_texts)
                
                # 重複を排除してリストを効率化
                unique_extra_fields = list(set(extra_fields))
                
                # 空文字を除外
                unique_extra_fields = [field for field in unique_extra_fields if field and field.strip()]
                
                # デバッグ出力を追加
                print(f"  ノード「{node_id}」の検索テキスト生成:")
                print(f"    - ラベル: {node_text}")
                print(f"    - 検索フィールド: {unique_extra_fields[:20]}{'...' if len(unique_extra_fields) > 20 else ''}")
                
                # 検索対象の文字列をまとめる
                search_text = f"{node_text} {node_id} {' '.join(unique_extra_fields)}"
                print(f"    - 検索テキスト（一部）: {search_text[:100]}...")
                
                # 新しいインデックス項目を作成
                new_index_item = {
                    "text": search_text.lower(),
                    "path": f"node:{node_id}", # 単純なパス形式に変更
                    "node": node_data,
                    "id": node_id
                }
                
                # インデックスに追加
                self.search_index.append(new_index_item)
                added_items.append(new_index_item)
            
            # デバッグ: 更新後の状態を確認
            print(f"[OK] 検索インデックスを更新しました: 追加={len(added_items)}ノード, 合計={len(self.search_index)}ノード")
            added_node_ids = [item["id"] for item in added_items]
            all_node_ids = [item["id"] for item in self.search_index]
            print(f"  追加されたID: {added_node_ids}")
            print(f"  更新後の全ID: {all_node_ids[:10]}..." if len(all_node_ids) > 10 else f"  更新後の全ID: {all_node_ids}")
            
            # インデックスに実際に追加されたか確認
            found_ids = []
            for test_id in updated_nodes:
                if any(item["id"] == test_id for item in self.search_index):
                    found_ids.append(test_id)
            print(f"  インデックスに存在するID: {found_ids}")
            
            # 現在の検索語があるか確認
            old_term = getattr(self, 'search_term', '')
            
            # 現在の検索条件で検索を確実に再実行（検索結果を更新するため）
            if old_term:
                # 検索実行前の最終チェック
                # 数件のサンプルを表示
                for i, item in enumerate(self.search_index):
                    if i < 3 or item["id"] in updated_nodes:
                        print(f"  - ID: {item['id']}, テキスト: {item['text'][:50]}...")
                
                # 検索語が検索テキストに含まれているか直接チェック
                check_term = old_term.lower()
                found_in_texts = [
                    item["id"] for item in self.search_index
                    if check_term in item["text"]
                ]
                if found_in_texts:
                    print(f"  検索語 '{old_term}' は以下のノードに存在します: {found_in_texts}")
                else:
                    print(f"  検索語 '{old_term}' は検索対象テキストに見つかりませんでした")
                
                # 特別処理: 特定のキーワードを直接チェック
                if check_term in ['a', 'b', 'ccc']:
                    print(f"  特別チェック: キーワード '{check_term}' を直接探索中...")
                    for item in self.search_index:
                        if item["id"] == node_id:
                            if check_term in item["text"]:
                                print(f"    [OK] キーワード '{check_term}' はノード {node_id} のテキストに存在します")
                            else:
                                print(f"    [ERROR] キーワード '{check_term}' はノード {node_id} のテキストに存在しません")
                            # 周辺コンテキストを表示
                            context = item["text"]
                            try:
                                index = context.find(check_term)
                                if index >= 0:
                                    start = max(0, index - 20)
                                    end = min(len(context), index + len(check_term) + 20)
                                    surrounding = context[start:end]
                                    print(f"    周辺コンテキスト: ...{surrounding}...")
                            except:
                                pass
                
                # 検索を強制的に実行
                self.perform_search()
                
                # 検索結果の表示を強制的に更新
                if self.search_results:
                    print(f"[OK] 検索結果が見つかりました: {len(self.search_results)}件")
                    result_ids = [result["id"] for result in self.search_results]
                    print(f"  - 検索結果のID: {result_ids}")
                    
                    # 検索結果のUIを確実に更新
                    self.update_search_results_display()
                    
                    # 検索結果が存在し、かつ最初の検索結果を選択
                    if len(self.search_results) > 0:
                        self.select_search_result(0)
                    
                    # ページ全体の更新
                    if self.page:
                        print(f"[OK] ページ全体を更新します")
                        self.page.update()
                else:
                    print(f"[WARNING] 検索語 '{old_term}' に一致する結果が見つかりませんでした")
                    # 結果が見つからない場合でも、UIを更新
                    self.update_search_results_display()
                    if self.page:
                        self.page.update()
        else:
            print(f"[WARNING] 指定されたノードID '{node_id}' が見つからないため、検索インデックスを更新できません")
            # 代替策として全インデックスを再構築
            self.search_index = []
            self.build_search_index()
            print(f"[OK] 代替として検索インデックスを完全に再構築しました（{len(self.search_index)}ノード）")
            
            # 検索語があれば再検索を強制実行
            if hasattr(self, 'search_term') and self.search_term:
                self.perform_search()


    def _setup_event_subscriptions(self):
        """イベント購読の設定"""
        # 言語変更イベントを購読
        self.subscribe_to_event(EventType.LANGUAGE_CHANGED, self._on_language_changed)
    
    def _on_language_changed(self, event):
        """言語変更時の処理"""
        # 検索UIの翻訳を更新
        if self.search_field:
            self.search_field.hint_text = t("placeholder.search")
            self.search_field.update()
        
        if self.no_results_message:
            self.no_results_message.value = t("search.no_results")
            self.no_results_message.update()
        
        # 結果カウンターの更新
        if self.result_counter:
            total_results = len(self.search_results)
            current_idx = self.current_search_index + 1 if self.current_search_index >= 0 and total_results > 0 else 0
            counter_text = f"{current_idx}/{total_results}" if total_results > 0 else self._format_result_count(0)
            self.result_counter.value = counter_text
            self.result_counter.update()
    
    def _format_result_count(self, count: int) -> str:
        """結果件数をフォーマット"""
        # 現在の言語に応じた形式で結果件数を表示
        from translation import get_language
        if get_language() == "en":
            return f"{count} results" if count != 1 else "1 result"
        else:
            return t("search.result_count").format(count=count)


def create_search_manager(app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None) -> SearchManager:
    """SearchManagerのインスタンスを作成する工場関数"""
    search_manager = SearchManager(app_state, ui_controls, page)
    app_state["search_manager"] = search_manager
    return search_manager