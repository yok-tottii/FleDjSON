#!/usr/bin/env python3
"""
Phase 3: main.py改修とイベントハンドラー設定の統合テスト

このスクリプトはmain.pyのクラスベースアーキテクチャ移行の完了を確認します
"""

import sys
import ast
import os
from typing import Dict, List, Tuple

def test_main_py_structure():
    """main.pyの構造をテストする"""
    main_py_path = "/Users/user/Documents/dev/FleDjSON/src/main.py"
    
    print("[DEBUG] Phase 3: main.py構造テスト開始")
    print("=" * 60)
    
    # ファイル存在確認
    if not os.path.exists(main_py_path):
        print("[ERROR] main.pyが見つかりません")
        return False
    
    # ファイル読み込み
    try:
        with open(main_py_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[ERROR] ファイル読み込みエラー: {e}")
        return False
    
    # 構文解析テスト
    try:
        ast.parse(content)
        print("[OK] 構文解析: OK")
    except SyntaxError as e:
        print(f"[ERROR] 構文エラー: {e}")
        return False
    
    # Phase 3要件の確認
    results = {}
    
    # 1. ヘルパー関数インポートの削除確認
    helper_imports = [
        "from src.ui_helpers import",
        "from src.drag_drop_helpers import", 
        "from src.analyze_json import",
        "from src.utils import"
    ]
    
    helper_found = False
    for helper_import in helper_imports:
        if helper_import in content:
            print(f"[WARNING] 未削除のヘルパーインポート発見: {helper_import}")
            helper_found = True
    
    if not helper_found:
        print("[OK] ヘルパー関数インポートの削除: OK")
        results["helper_imports_removed"] = True
    else:
        results["helper_imports_removed"] = False
    
    # 2. マネージャークラスのインポート確認
    manager_imports = [
        "from managers.form_manager import",
        "from managers.data_manager import",
        "from managers.ui_manager import",
        "from managers.drag_drop_manager import",
        "from managers.search_manager import"
    ]
    
    manager_import_count = 0
    for manager_import in manager_imports:
        if manager_import in content:
            manager_import_count += 1
            print(f"[OK] マネージャーインポート確認: {manager_import}")
    
    results["manager_imports"] = manager_import_count >= 4
    
    # 3. 初期化関数の存在確認
    init_functions = [
        "def create_initial_app_state",
        "def create_initial_ui_controls", 
        "def initialize_page_settings",
        "def initialize_managers",
        "def setup_event_handlers"
    ]
    
    init_function_count = 0
    for init_func in init_functions:
        if init_func in content:
            init_function_count += 1
            print(f"[OK] 初期化関数確認: {init_func}")
    
    results["init_functions"] = init_function_count >= 4
    
    # 4. グローバル変数削除確認
    global_vars = [
        "app_state = {",
        "ui_controls = {"
    ]
    
    global_vars_found = False
    for global_var in global_vars:
        if global_var in content and "def main" not in content[content.find(global_var)-50:content.find(global_var)+50]:
            print(f"[WARNING] グローバル変数が残存: {global_var}")
            global_vars_found = True
    
    if not global_vars_found:
        print("[OK] グローバル変数の関数内移動: OK")
        results["global_vars_moved"] = True
    else:
        results["global_vars_moved"] = False
    
    # 5. マネージャーベースのイベントハンドラー確認
    manager_handlers = [
        "setup_event_handlers(managers",
        "managers.get(",
        "managers[\"data_manager\"]",
        "managers[\"ui_manager\"]"
    ]
    
    manager_handler_count = 0
    for handler in manager_handlers:
        if handler in content:
            manager_handler_count += 1
            print(f"[OK] マネージャーベースハンドラー確認: {handler}")
    
    results["manager_handlers"] = manager_handler_count >= 3
    
    # 6. ヘルパー関数直接呼び出しチェック（残っていてはいけない）
    helper_calls = [
        "on_file_selected",
        "trigger_save_as_dialog", 
        "on_lock_change",
        "save_file_directly",
        "close_all_dialogs"
    ]
    
    helper_calls_found = []
    for helper_call in helper_calls:
        # マネージャーメソッド経由でない直接呼び出しを検出
        patterns = [
            f"{helper_call}(",
            f"= {helper_call}"
        ]
        for pattern in patterns:
            if pattern in content and "ui_manager." not in content[max(0, content.find(pattern)-20):content.find(pattern)+50]:
                if "data_manager." not in content[max(0, content.find(pattern)-20):content.find(pattern)+50]:
                    if "managers" not in content[max(0, content.find(pattern)-30):content.find(pattern)+30]:
                        helper_calls_found.append(helper_call)
    
    if not helper_calls_found:
        print("[OK] ヘルパー関数直接呼び出しの削除: OK")
        results["helper_calls_removed"] = True
    else:
        print(f"[WARNING] ヘルパー関数直接呼び出しが残存: {helper_calls_found}")
        results["helper_calls_removed"] = False
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("[SUMMARY] Phase 3テスト結果サマリー")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")
    
    print(f"\n📈 成功率: {passed_tests}/{total_tests} ({(passed_tests/total_tests)*100:.1f}%)")
    
    if passed_tests == total_tests:
        print("Phase 3: main.py改修とイベントハンドラー設定 - 完了!")
        return True
    else:
        print("[WARNING] Phase 3に未完了項目があります")
        return False


def test_manager_coverage():
    """各マネージャークラスのメソッドカバレッジを確認"""
    print("\n[DEBUG] マネージャークラス カバレッジ確認")
    print("=" * 60)
    
    manager_files = {
        "FormManager": "/Users/user/Documents/dev/FleDjSON/src/managers/form_manager.py",
        "DataManager": "/Users/user/Documents/dev/FleDjSON/src/managers/data_manager.py", 
        "UIManager": "/Users/user/Documents/dev/FleDjSON/src/managers/ui_manager.py",
        "DragDropManager": "/Users/user/Documents/dev/FleDjSON/src/managers/drag_drop_manager.py",
        "SearchManager": "/Users/user/Documents/dev/FleDjSON/src/managers/search_manager.py"
    }
    
    # 必須メソッドの定義
    required_methods = {
        "UIManager": ["trigger_save_as_dialog", "save_file_directly", "close_all_dialogs", "show_save_confirmation", "on_save_file_result"],
        "DataManager": ["on_file_selected", "load_json_file", "save_json_file"],
        "DragDropManager": ["on_lock_change"],
        "FormManager": ["toggle_add_mode"],
        "SearchManager": ["create_search_ui", "handle_keyboard_event"]
    }
    
    coverage_results = {}
    
    for manager_name, file_path in manager_files.items():
        if not os.path.exists(file_path):
            print(f"[ERROR] {manager_name}: ファイルが見つかりません")
            coverage_results[manager_name] = 0
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"[ERROR] {manager_name}: 読み込みエラー - {e}")
            coverage_results[manager_name] = 0
            continue
        
        required = required_methods.get(manager_name, [])
        found_methods = []
        
        for method in required:
            if f"def {method}" in content:
                found_methods.append(method)
        
        coverage = len(found_methods) / max(len(required), 1) * 100
        coverage_results[manager_name] = coverage
        
        status = "[OK]" if coverage >= 90 else "[WARNING]" if coverage >= 70 else "[ERROR]"
        print(f"{status} {manager_name}: {coverage:.1f}% ({len(found_methods)}/{len(required)} メソッド)")
        
        if found_methods:
            print(f"    ✓ 実装済み: {', '.join(found_methods)}")
        
        missing = [m for m in required if m not in found_methods]
        if missing:
            print(f"    ✗ 不足: {', '.join(missing)}")
    
    avg_coverage = sum(coverage_results.values()) / len(coverage_results)
    print(f"\n[STATS] 平均カバレッジ: {avg_coverage:.1f}%")
    
    return avg_coverage >= 85


if __name__ == "__main__":
    print("Phase 3統合テスト開始")
    print("Fletcher JSON Editor - クラスベースアーキテクチャ移行検証\n")
    
    success1 = test_main_py_structure()
    success2 = test_manager_coverage()
    
    print("\n" + "=" * 60)
    print("🏁 最終結果")
    print("=" * 60)
    
    if success1 and success2:
        print("Phase 3: 完全成功!")
        print("[OK] main.pyのクラスベースアーキテクチャ移行が完了しました")
        sys.exit(0)
    else:
        print("[WARNING] Phase 3: 部分的成功")
        print("追加の作業が必要です")
        sys.exit(1)