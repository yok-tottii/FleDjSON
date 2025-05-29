#!/usr/bin/env python3
"""
FleDjSON用代替通知システム
SnackBarが表示されない環境でも確実に動作する
"""

import flet as ft
import threading
import time
from typing import Optional, Dict, Any
from translation import t

class NotificationSystem:
    """
    SnackBarが動作しない環境用の代替通知システム
    """
    
    def __init__(self, page: ft.Page):
        self.page = page
        self._notification_counter = 0
    
    def show_save_success(self, filename: str = None):
        """保存成功通知"""
        if filename:
            message = f"[OK] {t('notification.file_saved')}: {filename}"
        else:
            message = f"[OK] {t('notification.file_saved')}"
        
        self._show_overlay_notification(message, ft.Colors.GREEN_700)
    
    def show_save_error(self, error_message: str = None):
        """保存エラー通知"""
        if error_message:
            message = f"[ERROR] {t('error.save_failed')}: {error_message}"
        else:
            message = f"[ERROR] {t('error.save_failed')}"
        
        self._show_overlay_notification(message, ft.Colors.RED_700)
    
    def show_ctrl_s_save(self):
        """Ctrl+S保存成功通知"""
        self._show_overlay_notification(f"[OK] {t('notification.ctrl_s_save')}", ft.Colors.GREEN_700)
    
    def show_info(self, message: str):
        """情報通知"""
        self._show_overlay_notification(f"[INFO] {message}", ft.Colors.BLUE_700)
    
    def show_warning(self, message: str):
        """警告通知"""
        self._show_overlay_notification(f"[WARNING] {message}", ft.Colors.ORANGE_700)
    
    def show_error(self, message: str):
        """エラー通知"""
        self._show_overlay_notification(f"[ERROR] {message}", ft.Colors.RED_700)
    
    def show_success(self, message: str):
        """成功通知"""
        self._show_overlay_notification(f"[OK] {message}", ft.Colors.GREEN_700)
    
    def show_important_dialog(self, title: str, message: str):
        """重要な通知はダイアログで表示"""
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("OK", on_click=lambda e: self._close_dialog())
            ]
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
        print(f"Important dialog: {title} - {message}")
    
    def _close_dialog(self):
        """ダイアログを閉じる"""
        if hasattr(self.page, 'dialog') and self.page.dialog:
            self.page.dialog.open = False
            self.page.update()
    
    def _show_overlay_notification(self, message: str, bgcolor: ft.Colors, duration: int = 3):
        """Overlay通知の内部実装"""
        
        # 既存の通知を削除
        for control in self.page.overlay[:]:
            if hasattr(control, 'data') and control.data == 'fledjson_notification':
                self.page.overlay.remove(control)
        
        # 通知ID
        self._notification_counter += 1
        notification_id = f"notification_{self._notification_counter}"
        
        # 通知コンテナを作成
        notification = ft.Container(
            content=ft.Row([
                ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, expand=True),
                ft.IconButton(
                    ft.Icons.CLOSE,
                    icon_color=ft.Colors.WHITE,
                    icon_size=16,
                    tooltip=t("dialog.close"),
                    on_click=lambda e: self._remove_notification(notification)
                )
            ], spacing=5),
            bgcolor=bgcolor,
            padding=ft.padding.symmetric(horizontal=15, vertical=10),
            border_radius=8,
            margin=ft.margin.all(10),
            data='fledjson_notification',
            width=450,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=8,
                color=ft.Colors.with_opacity(0.4, ft.Colors.BLACK),
            ),
            animate_opacity=300
        )
        
        # Overlayに追加
        self.page.overlay.append(notification)
        self.page.update()
        
        # 自動削除タイマー
        def auto_remove():
            time.sleep(duration)
            try:
                self._remove_notification(notification)
            except:
                pass
        
        threading.Thread(target=auto_remove, daemon=True).start()
    
    def _remove_notification(self, notification):
        """通知を削除"""
        try:
            if notification in self.page.overlay:
                self.page.overlay.remove(notification)
                self.page.update()
        except:
            pass

# Factory function for FleDjSON integration
def create_notification_system(page: ft.Page) -> NotificationSystem:
    """FleDjSON用通知システムのファクトリー関数"""
    return NotificationSystem(page)

# Legacy SnackBar API compatibility
def show_snackbar_compatible(page: ft.Page, message: str, bgcolor: ft.Colors = ft.Colors.GREEN):
    """
    従来のSnackBar APIと互換性を持つ関数
    FleDjSONの既存コードで簡単に置き換え可能
    """
    notification_system = NotificationSystem(page)
    notification_system._show_overlay_notification(message, bgcolor)

# Test function
def main(page: ft.Page):
    """テスト用メイン関数"""
    page.title = "FleDjSON Notification System"
    
    notification_system = create_notification_system(page)
    
    def test_save_success(e):
        notification_system.show_save_success("test-file.json")
    
    def test_ctrl_s(e):
        notification_system.show_ctrl_s_save()
    
    def test_error(e):
        notification_system.show_save_error("ディスク容量不足")
    
    def test_warning(e):
        notification_system.show_warning("未保存の変更があります")
    
    def test_info(e):
        notification_system.show_info("ファイルが正常に読み込まれました")
    
    def test_important(e):
        notification_system.show_important_dialog("重要な確認", "データが変更されています。保存しますか？")
    
    def test_legacy_api(e):
        show_snackbar_compatible(page, "従来API互換テスト", ft.Colors.PURPLE)
    
    page.add(
        ft.Column([
            ft.Text("FleDjSON通知システム", style=ft.TextThemeStyle.HEADLINE_MEDIUM),
            ft.Divider(),
            ft.ElevatedButton("保存成功", on_click=test_save_success, bgcolor=ft.Colors.GREEN),
            ft.ElevatedButton("Ctrl+S保存", on_click=test_ctrl_s, bgcolor=ft.Colors.GREEN_700),
            ft.ElevatedButton("保存エラー", on_click=test_error, bgcolor=ft.Colors.RED),
            ft.ElevatedButton("警告", on_click=test_warning, bgcolor=ft.Colors.ORANGE),
            ft.ElevatedButton("情報", on_click=test_info, bgcolor=ft.Colors.BLUE),
            ft.ElevatedButton("重要ダイアログ", on_click=test_important, bgcolor=ft.Colors.DEEP_ORANGE),
            ft.ElevatedButton("従来API互換", on_click=test_legacy_api, bgcolor=ft.Colors.PURPLE),
        ], spacing=10)
    )

if __name__ == "__main__":
    ft.app(target=main)