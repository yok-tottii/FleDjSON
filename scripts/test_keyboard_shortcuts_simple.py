#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
キーボードショートカット(Ctrl+S/Cmd+S)保存機能の改善の簡易テスト
"""
import os
import sys
import json
from pathlib import Path

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui_helpers import (
    update_ui_save_state,
    handle_data_change,
    save_file_directly
)

print("🧪 キーボードショートカット保存機能の改善テスト")

# モック版のapp_stateとui_controlsを作成
class MockControl:
    def __init__(self):
        self.disabled = False
        self.updated = False
        self._page = True
        
    def update(self):
        self.updated = True

app_state = {
    "is_dirty": True,
    "raw_data": [{"id": 1, "name": "Test"}],
    "file_path": "/test/path.json"
}

ui_controls = {
    "detail_save_button": MockControl(),
    "save_button": MockControl()
}

# グローバル変数を設定
import src.ui_helpers
fledjson.ui_helpers.app_state = app_state
fledjson.ui_helpers.ui_controls = ui_controls

print("\n[OK] テスト: update_ui_save_state (dirty=True)")
update_ui_save_state()
print(f"detail_save_button.disabled = {ui_controls['detail_save_button'].disabled} (期待値: False)")
print(f"detail_save_button.updated = {ui_controls['detail_save_button'].updated} (期待値: True)")
print(f"save_button.disabled = {ui_controls['save_button'].disabled} (期待値: False)")

print("\n[OK] テスト: update_ui_save_state (dirty=False)")
app_state["is_dirty"] = False
ui_controls["detail_save_button"].updated = False
ui_controls["save_button"].updated = False
update_ui_save_state()
print(f"detail_save_button.disabled = {ui_controls['detail_save_button'].disabled} (期待値: True)")
print(f"detail_save_button.updated = {ui_controls['detail_save_button'].updated} (期待値: True)")

print("\n[OK] テスト: handle_data_change")
app_state["is_dirty"] = False
ui_controls["detail_save_button"].updated = False
handle_data_change(True)
print(f"app_state['is_dirty'] = {app_state['is_dirty']} (期待値: True)")
print(f"detail_save_button.updated = {ui_controls['detail_save_button'].updated} (期待値: True)")

print("\nテスト終了")