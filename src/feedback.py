"""
feedback.py
ユーザーフィードバックモジュール

FleDjSONのユーザーフィードバック機能を提供します。
進捗表示、操作レスポンス、情報通知などを統一的に扱います。
"""
import flet as ft
from flet import (
    Container, Row, Column, Text, ProgressBar, ProgressRing, 
    IconButton, Icon, Colors, MainAxisAlignment, CrossAxisAlignment,
    Padding, Border, BorderRadius, BorderSide, IconButton, Icons
)
from typing import Any, Dict, List, Optional, Callable, Union
import threading
import time
import functools
from translation import t

class OperationStatus:
    """操作状態を表す定数クラス"""
    IDLE = "idle"
    LOADING = "loading"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    CANCELLED = "cancelled"

class FeedbackManager:
    """
    ユーザーフィードバックを統合的に管理するクラス
    
    様々な種類のフィードバック要素を一元管理し、
    アプリケーション全体での統一的なフィードバック体験を提供します。
    
    Attributes:
        app_state (Dict): アプリケーションの状態を保持する辞書
        ui_controls (Dict): UIコントロールを保持する辞書
        page (ft.Page): Fletページオブジェクト
    """
    
    def __init__(self, app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None):
        """
        FeedbackManagerを初期化します。
        
        Args:
            app_state (Dict): アプリケーションの状態を保持する辞書
            ui_controls (Dict): UIコントロールを保持する辞書
            page (ft.Page, optional): Fletページオブジェクト
        """
        self.app_state = app_state
        self.ui_controls = ui_controls
        self.page = page or app_state.get("page")
        
        # 進捗状況の追跡用
        self.operations = {}
        self.current_operation = None
        
        # UIコントロールの初期化と登録
        self._init_feedback_controls()
        
        # 環境変数に基づく初期化メッセージ
        from debug_control import print_init
        print_init("[OK] FeedbackManager initialized.")
    
    def _init_feedback_controls(self):
        """フィードバック用UIコントロールを初期化"""
        # 拡張ローディングインジケータ（詳細情報表示付き）
        loading_details = Text("", size=14)
        loading_progress = ft.ProgressBar(width=300, height=6, value=0)
        
        detailed_loading_indicator = Container(
            content=Column(
                [
                    Row(
                        [
                            Text(t("loading.processing"), size=14, weight="bold"),
                            ft.ProgressRing(width=16, height=16, stroke_width=2)
                        ],
                        alignment=MainAxisAlignment.CENTER,
                        spacing=10
                    ),
                    loading_details,
                    loading_progress,
                    Row(
                        [
                            IconButton(
                                icon=Icons.CANCEL,
                                icon_color=Colors.RED,
                                icon_size=20,
                                tooltip=t("button.cancel"),
                                on_click=self._on_cancel_operation,
                                visible=False,
                            )
                        ],
                        alignment=MainAxisAlignment.CENTER,
                    )
                ],
                spacing=10,
                horizontal_alignment=CrossAxisAlignment.CENTER,
            ),
            padding=20,
            border_radius=10,
            bgcolor=Colors.with_opacity(0.9, Colors.SURFACE),
            visible=False
        )
        
        # トースト通知
        toast_container = Container(
            content=Row(
                [
                    Icon(Icons.INFO, color=Colors.PRIMARY),
                    Text("", size=14),
                    IconButton(
                        icon=Icons.CLOSE,
                        icon_size=16,
                        on_click=self._on_toast_close,
                    )
                ],
                spacing=10,
                alignment=MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=CrossAxisAlignment.CENTER,
            ),
            padding=10,
            border_radius=5,
            bgcolor=Colors.with_opacity(0.9, Colors.SURFACE),
            width=400,
            visible=False
        )
        
        
        # UIコントロールを登録
        self.ui_controls.update({
            "detailed_loading_indicator": detailed_loading_indicator,
            "loading_details": loading_details,
            "loading_progress": loading_progress,
            "toast_container": toast_container,
            "cancel_operation_button": detailed_loading_indicator.content.controls[3].controls[0],
        })
        
        # 既存のローディングインジケータとの連携
        if "loading_indicator" in self.ui_controls:
            self._original_loading_indicator = self.ui_controls["loading_indicator"]
        else:
            self._original_loading_indicator = None
        
        # ページオーバーレイに追加
        if self.page and hasattr(self.page, 'overlay'):
            if detailed_loading_indicator not in self.page.overlay:
                self.page.overlay.append(detailed_loading_indicator)
            if toast_container not in self.page.overlay:
                self.page.overlay.append(toast_container)
    
    def _on_cancel_operation(self, e):
        """キャンセルボタン押下時の処理"""
        if self.current_operation and self.current_operation in self.operations:
            operation = self.operations[self.current_operation]
            if operation.get("on_cancel"):
                operation["on_cancel"]()
            
            # 状態更新
            operation["status"] = OperationStatus.CANCELLED
            self._update_loading_display(self.current_operation, t("loading.cancelled"), 0)
            
            # インジケータを非表示（少し遅延）
            threading.Timer(1.0, self.hide_loading_indicator).start()
    
    def _on_toast_close(self, e):
        """トースト通知閉じるボタン押下時の処理"""
        toast = self.ui_controls.get("toast_container")
        if toast:
            toast.visible = False
            if self.page:
                self.page.update()
    
    def register_operation(self, 
                          operation_id: str, 
                          name: str, 
                          total_steps: int = 100,
                          can_cancel: bool = False,
                          on_cancel: Optional[Callable] = None) -> str:
        """
        追跡する操作を登録します。
        
        Args:
            operation_id (str): 操作の識別子
            name (str): 操作の表示名
            total_steps (int): 操作の総ステップ数
            can_cancel (bool): キャンセル可能かどうか
            on_cancel (Callable, optional): キャンセル時のコールバック
            
        Returns:
            str: 登録された操作ID
        """
        self.operations[operation_id] = {
            "name": name,
            "status": OperationStatus.IDLE,
            "progress": 0,
            "total_steps": total_steps,
            "current_step": 0,
            "start_time": None,
            "message": "",
            "can_cancel": can_cancel,
            "on_cancel": on_cancel
        }
        return operation_id
    
    def start_operation(self, operation_id: str, message: str = ""):
        """
        操作を開始します。
        
        Args:
            operation_id (str): 操作の識別子
            message (str, optional): 表示するメッセージ
        """
        if operation_id in self.operations:
            self.operations[operation_id].update({
                "status": OperationStatus.LOADING,
                "progress": 0,
                "current_step": 0,
                "start_time": time.time(),
                "message": message or f"{self.operations[operation_id]['name']}{t('loading.starting')}"
            })
            
            # ローディングインジケータを表示
            self.current_operation = operation_id
            self._update_loading_display(
                operation_id, 
                self.operations[operation_id]["message"],
                0
            )
            self.show_loading_indicator(detailed=True)
            
            # キャンセルボタンの表示状態を設定
            cancel_button = self.ui_controls.get("cancel_operation_button")
            if cancel_button:
                cancel_button.visible = self.operations[operation_id]["can_cancel"]
                if self.page:
                    cancel_button.update()
            
            # ステータスを更新
            # ステータスインジケーターの更新（ステータスバーが削除されたためスキップ）
            pass
    
    def update_operation(self, operation_id: str, current_step: int, message: Optional[str] = None):
        """
        操作の進捗を更新します。
        
        Args:
            operation_id (str): 操作の識別子
            current_step (int): 現在のステップ数
            message (str, optional): 表示するメッセージ
        """
        if operation_id in self.operations:
            operation = self.operations[operation_id]
            operation["current_step"] = min(current_step, operation["total_steps"])
            operation["progress"] = operation["current_step"] / operation["total_steps"]
            
            if message:
                operation["message"] = message
            
            # ローディングインジケータの表示を更新
            self._update_loading_display(
                operation_id, 
                operation["message"],
                operation["progress"]
            )
    
    def complete_operation(self, operation_id: str, message: str = "", status: str = OperationStatus.SUCCESS):
        """
        操作を完了します。
        
        Args:
            operation_id (str): 操作の識別子
            message (str, optional): 完了メッセージ
            status (str, optional): 完了ステータス
        """
        if operation_id in self.operations:
            # メッセージが空の場合はデフォルトメッセージを設定しない
            display_message = message if message else ""
            
            self.operations[operation_id].update({
                "status": status,
                "progress": 1.0,
                "current_step": self.operations[operation_id]["total_steps"],
                "message": display_message
            })
            
            # 完了メッセージとしてインジケータを更新
            self._update_loading_display(
                operation_id, 
                self.operations[operation_id]["message"],
                1.0
            )
            
            # 一定時間後にインジケータを非表示
            threading.Timer(1.0, self.hide_loading_indicator).start()
            
            # ステータスインジケーターの更新（ステータスバーが削除されたためスキップ）
            pass
            
            # メッセージが指定されている場合のみトースト通知を表示
            if message:
                # 完了時にトースト通知も表示
                icon_map = {
                    OperationStatus.SUCCESS: Icons.CHECK_CIRCLE,
                    OperationStatus.ERROR: Icons.ERROR,
                    OperationStatus.WARNING: Icons.WARNING_AMBER,
                    OperationStatus.CANCELLED: Icons.CANCEL
                }
                color_map = {
                    OperationStatus.SUCCESS: Colors.GREEN,
                    OperationStatus.ERROR: Colors.ERROR,
                    OperationStatus.WARNING: Colors.AMBER,
                    OperationStatus.CANCELLED: Colors.GREY
                }
                
                self.show_toast(
                    self.operations[operation_id]["message"],
                    icon=icon_map.get(status, Icons.INFO),
                    icon_color=color_map.get(status, Colors.PRIMARY)
                )
    
    def error_operation(self, operation_id: str, message: str):
        """
        操作がエラーで終了したことを記録します。
        
        Args:
            operation_id (str): 操作の識別子
            message (str): エラーメッセージ
        """
        self.complete_operation(operation_id, message, OperationStatus.ERROR)
    
    def show_success(self, message: str):
        """
        成功メッセージを表示します。
        
        Args:
            message (str): 成功メッセージ
        """
        self.show_toast(message, icon=Icons.CHECK_CIRCLE, icon_color=Colors.GREEN)
    
    def show_error(self, message: str):
        """
        エラーメッセージを表示します。
        
        Args:
            message (str): エラーメッセージ
        """
        self.show_toast(message, icon=Icons.ERROR, icon_color=Colors.RED)
    
    def show_toast(self, message: str, duration: int = 3000, icon: str = Icons.INFO, icon_color: str = Colors.PRIMARY):
        """
        トースト通知を表示します。
        
        Args:
            message (str): 表示するメッセージ
            duration (int): 表示時間（ミリ秒）
            icon (str): アイコン
            icon_color (str): アイコンの色
        """
        toast = self.ui_controls.get("toast_container")
        if toast and isinstance(toast.content, Row):
            # アイコンと文字列を設定
            toast.content.controls[0].name = icon
            toast.content.controls[0].color = icon_color
            toast.content.controls[1].value = message
            
            # 表示
            toast.visible = True
            if self.page:
                toast.update()
            
            # 一定時間後に非表示
            def hide_toast():
                toast.visible = False
                if self.page:
                    self.page.update()
            
            threading.Timer(duration / 1000, hide_toast).start()
    
    def show_snack_bar(self, message: str, action_text: str = "OK", bg_color: Optional[str] = None):
        """
        スナックバーを表示します。
        
        Args:
            message (str): 表示するメッセージ
            action_text (str): アクションテキスト
            bg_color (str, optional): 背景色
        """
        if not self.page:
            return
            
        snack_bar = ft.SnackBar(
            content=Text(message),
            action=action_text
        )
        
        if bg_color:
            snack_bar.bgcolor = bg_color
        
        self.page.snack_bar = snack_bar
        self.page.snack_bar.open = True
        self.page.update()
    
    def _update_loading_display(self, operation_id: str, message: str, progress: float):
        """
        ローディングインジケータの表示を更新します。
        
        Args:
            operation_id (str): 操作の識別子
            message (str): 表示するメッセージ
            progress (float): 進捗率（0.0〜1.0）
        """
        # 詳細ローディングインジケータ
        indicator = self.ui_controls.get("detailed_loading_indicator")
        if not indicator:
            return
            
        # メッセージ更新
        loading_details = self.ui_controls.get("loading_details")
        if loading_details:
            loading_details.value = message
            loading_details.update()
        
        # プログレスバー更新
        loading_progress = self.ui_controls.get("loading_progress")
        if loading_progress:
            loading_progress.value = progress
            loading_progress.update()
            
        # 元のローディングインジケータも連動
        if self._original_loading_indicator:
            self._original_loading_indicator.visible = indicator.visible
            if self.page:
                self._original_loading_indicator.update()
    
    def show_loading_indicator(self, message: str = "", detailed: bool = False):
        """
        ローディングインジケータを表示します。
        
        Args:
            message (str, optional): 表示するメッセージ
            detailed (bool): 詳細インジケータを表示するかどうか
        """
        if detailed:
            # 詳細ローディングインジケータ
            indicator = self.ui_controls.get("detailed_loading_indicator")
            if indicator:
                if message:
                    loading_details = self.ui_controls.get("loading_details")
                    if loading_details:
                        loading_details.value = message
                
                indicator.visible = True
                if self.page:
                    indicator.update()
        
        # 元のシンプルなローディングインジケータも連動
        if self._original_loading_indicator:
            self._original_loading_indicator.visible = True
            if self.page:
                self._original_loading_indicator.update()
    
    def hide_loading_indicator(self):
        """ローディングインジケータを非表示にします。"""
        # 詳細ローディングインジケータ
        indicator = self.ui_controls.get("detailed_loading_indicator")
        if indicator:
            indicator.visible = False
            if self.page:
                indicator.update()
        
        # 元のシンプルなローディングインジケータも連動
        if self._original_loading_indicator:
            self._original_loading_indicator.visible = False
            if self.page:
                self._original_loading_indicator.update()

# ユーティリティデコレータ
def with_feedback(operation_name: str, total_steps: int = 100, can_cancel: bool = False):
    """
    フィードバック表示機能付きの関数デコレータ
    
    Args:
        operation_name (str): 操作の表示名
        total_steps (int): 操作の総ステップ数
        can_cancel (bool): キャンセル可能かどうか
    """
    def decorating_function(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 実行コンテキストからFeedbackManagerを特定
            self_arg = args[0] if args else None
            app_state = getattr(self_arg, 'app_state', None) if self_arg else None
            
            if not app_state or 'feedback_manager' not in app_state:
                # FeedbackManagerが利用できない場合は元の関数をそのまま実行
                return func(*args, **kwargs)
            
            feedback_manager = app_state['feedback_manager']
            
            # 操作を登録
            operation_id = f"{operation_name}_{id(func)}_{time.time()}"
            feedback_manager.register_operation(
                operation_id,
                operation_name,
                total_steps,
                can_cancel
            )
            
            try:
                # 操作開始
                feedback_manager.start_operation(operation_id)
                
                # プログレスとして使用できるフック関数を定義
                def update_progress(step, message=None):
                    feedback_manager.update_operation(operation_id, step, message)
                
                # フック関数をキーワード引数として追加
                kwargs['update_progress'] = update_progress
                
                # 元の関数を実行
                result = func(*args, **kwargs)
                
                # 操作完了
                feedback_manager.complete_operation(
                    operation_id,
                    f"{operation_name}{t('loading.completed')}"
                )
                
                return result
                
            except Exception as e:
                # エラー時
                error_message = f"{operation_name}{t('loading.error')}: {str(e)}"
                feedback_manager.error_operation(operation_id, error_message)
                raise
                
        return wrapper
    return decorating_function


def create_feedback_manager(app_state: Dict[str, Any], ui_controls: Dict[str, Any], page: Optional[ft.Page] = None) -> FeedbackManager:
    """FeedbackManagerのインスタンスを作成する工場関数"""
    feedback_manager = FeedbackManager(app_state, ui_controls, page)
    app_state["feedback_manager"] = feedback_manager
    return feedback_manager