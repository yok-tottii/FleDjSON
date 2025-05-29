#!/usr/bin/env python3
"""
Fletの基本動作確認
"""
import flet as ft

def main(page: ft.Page):
    page.title = "Flet Test"
    page.add(ft.Text("Fletが正常に動作しています！"))

if __name__ == "__main__":
    ft.app(target=main)