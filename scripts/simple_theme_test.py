#!/usr/bin/env python3
"""シンプルなテーマボタンテスト"""
import flet as ft

def main(page: ft.Page):
    """テストアプリケーション"""
    page.title = "Theme Button Test"
    
    # PopupMenuButtonを直接作成
    theme_button = ft.PopupMenuButton(
        icon=ft.icons.PALETTE,
        tooltip="テーマ切り替え",
        items=[
            ft.PopupMenuItem(
                text="システムテーマ",
                icon=ft.icons.COMPUTER,
                on_click=lambda _: print("System theme selected")
            ),
            ft.PopupMenuItem(
                text="ライトテーマ",
                icon=ft.icons.LIGHT_MODE,
                on_click=lambda _: print("Light theme selected")
            ),
            ft.PopupMenuItem(
                text="ダークテーマ",
                icon=ft.icons.DARK_MODE,
                on_click=lambda _: print("Dark theme selected")
            ),
        ]
    )
    
    print(f"[DEBUG] theme_button created: {theme_button}")
    print(f"[DEBUG] theme_button type: {type(theme_button)}")
    
    # ボタンを含むRowを作成
    row = ft.Row([
        ft.ElevatedButton("テストボタン1"),
        ft.ElevatedButton("テストボタン2"),
        theme_button,
        ft.Text("テーマボタンはここ→"),
    ])
    
    print(f"[DEBUG] row.controls: {row.controls}")
    
    page.add(
        ft.Text("テーマボタンテスト", size=20),
        row
    )
    
    page.update()


if __name__ == "__main__":
    ft.app(target=main)