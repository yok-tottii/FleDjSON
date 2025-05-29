#!/usr/bin/env python3
"""テーマボタンの動作テスト"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import flet as ft
from managers.ui_manager import UIManager


def main(page: ft.Page):
    """テストアプリケーション"""
    page.title = "Theme Button Test"
    page.window_width = 400
    page.window_height = 300
    
    # 簡単なapp_stateとui_controlsを作成
    app_state = {"page": page}
    ui_controls = {}
    
    # UIManagerを作成
    ui_manager = UIManager(app_state, ui_controls, page)
    
    # テーマ変更コールバックを設定
    def change_theme(theme_mode: str):
        theme_mode_map = {
            "system": ft.ThemeMode.SYSTEM,
            "light": ft.ThemeMode.LIGHT,
            "dark": ft.ThemeMode.DARK
        }
        page.theme_mode = theme_mode_map.get(theme_mode, ft.ThemeMode.SYSTEM)
        page.update()
        print(f"Theme changed to: {theme_mode}")
    
    ui_manager.set_theme_change_callback(change_theme)
    
    # テーマボタンを作成
    theme_button = ui_manager.create_theme_button()
    print(f"Theme button created: {theme_button}")
    
    # AppBarに追加
    page.appbar = ft.AppBar(
        title=ft.Text("Theme Button Test"),
        actions=[theme_button] if theme_button else None
    )
    
    # メインコンテンツ
    page.add(
        ft.Container(
            content=ft.Column([
                ft.Text("テーマボタンのテスト", size=20),
                ft.Text("右上のパレットアイコンをクリックしてテーマを変更してください"),
            ]),
            padding=20
        )
    )
    
    page.update()


if __name__ == "__main__":
    ft.app(target=main)