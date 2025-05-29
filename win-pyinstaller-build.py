"""
PyInstallerでWindowsのexeを作成するスクリプト（Flet対応改善版）
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "FleDjSON"
ENTRY_POINT = Path("src/main.py")
DIST_DIR = Path("dist")
BUILD_DIR = Path("build")
ICON_PATH = Path("src/assets/icon_windows.ico")

def create_spec_file():
    """Fletアプリケーション用の適切なspecファイルを作成"""
    # Windowsパスを正しく処理
    entry_point_str = str(ENTRY_POINT).replace('\\', '/')
    icon_path_str = str(ICON_PATH).replace('\\', '/')
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['{entry_point_str}'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/assets', 'assets'),
        ('src/storage', 'storage'),
        ('src/storage/data/settings.json', 'storage/data'),
    ],
    hiddenimports=[
        'flet',
        'flet.app',
        'flet.canvas',
        'flet.controls',
        'flet.core',
        'flet_core',
        'flet_runtime',
        'managers',
        'managers.ui_manager',
        'managers.data_manager',
        'managers.form_manager',
        'managers.search_manager',
        'managers.analysis_manager',
        'managers.ui_state_manager',
        'managers.drag_drop_manager',
        'managers.settings_manager',
        'managers.copy_manager',
        'managers.flatten_manager',
        'managers.template_manager',
        'managers.event_aware_manager',
        'translation',
        'event_hub',
        'event_integration',
        'notification_system',
        'error_handling',
        'feedback',
        'json_template',
        'flatten_json',
        'optimizations',
        'debug_control',
        'logging_config',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windowsモードで実行（コンソールなし）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='{icon_path_str}' if os.path.exists('{icon_path_str}') else None,
)
'''
    
    with open(f"{APP_NAME}.spec", "w", encoding="utf-8") as f:
        f.write(spec_content)
    print(f"[OK] Created {APP_NAME}.spec file")

def clean():
    """前回のビルド成果物をクリーンアップ"""
    print("[CLEANUP] Cleaning previous builds...")
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
    spec_file = Path(f"{APP_NAME}.spec")
    if spec_file.exists():
        spec_file.unlink()
    print("[OK] Clean complete.")

def build_with_spec():
    """specファイルを使用してビルド"""
    print("[BUILD] Building .exe with PyInstaller using spec file...")
    
    # アイコンファイルの存在確認
    if not ICON_PATH.exists():
        print(f"[WARNING] Icon file not found at {ICON_PATH}")
        print("   Proceeding without icon...")
    else:
        print(f"[OK] Icon file found: {ICON_PATH}")
    
    # specファイルを作成
    create_spec_file()
    
    # specファイルを使用してビルド
    cmd = [sys.executable, "-m", "PyInstaller", f"{APP_NAME}.spec", "--clean"]
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print("[ERROR] Build failed.")
        sys.exit(1)
    
    print(f"[OK] Build complete. Executable at: {DIST_DIR / (APP_NAME + '.exe')}")

def build_with_flet():
    """Flet公式のビルドコマンドを使用（推奨）"""
    print("[BUILD] Building with Flet build command (recommended)...")
    print("Note: Make sure 'flet' is installed globally: pip install flet")
    
    cmd = ["flet", "build", "windows", "--name", APP_NAME]
    if ICON_PATH.exists():
        cmd.extend(["--icon", str(ICON_PATH)])
    
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print("[ERROR] Build failed.")
        print("Try running: poetry run flet build windows")
        sys.exit(1)
    
    print(f"[OK] Build complete.")

def build_simple():
    """シンプルなPyInstallerビルド（デバッグ用）"""
    print("[BUILD] Building with simple PyInstaller command...")
    
    # アイコンファイルの存在確認
    icon_option = []
    if ICON_PATH.exists():
        icon_option = ["--icon", str(ICON_PATH)]
        print(f"[OK] Using icon: {ICON_PATH}")
    else:
        print(f"[WARNING] Icon not found: {ICON_PATH}")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(ENTRY_POINT),
        "--onefile",
        "--windowed",
        f"--name={APP_NAME}",
        "--paths=src",
        "--add-data", "src/assets;assets",
        "--add-data", "src/storage;storage",
    ] + icon_option
    
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print("[ERROR] Build failed.")
        sys.exit(1)
    
    print(f"[OK] Build complete. Executable at: {DIST_DIR / (APP_NAME + '.exe')}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build FleDjSON for Windows")
    parser.add_argument(
        "--method", 
        choices=["pyinstaller", "flet", "simple"], 
        default="pyinstaller",
        help="Build method to use (default: pyinstaller)"
    )
    args = parser.parse_args()
    
    if args.method == "flet":
        build_with_flet()
    elif args.method == "simple":
        clean()
        build_simple()
    else:
        clean()
        build_with_spec()