#!/usr/bin/env python3
"""
テーマ切り替え機能のテストスクリプト

テスト手順:
1. アプリケーションを起動
2. テーマボタン（パレットアイコン）をクリック
3. 各テーマを選択して動作確認
"""

import os
import sys

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def main():
    print("[THEME] テーマ切り替え機能のテスト")
    print("=" * 50)
    print("\nテスト手順:")
    print("1. poetry run python src/main.py でアプリを起動")
    print("2. 右上のパレットアイコンをクリック")
    print("3. 以下の各テーマを選択して確認:")
    print("   - システムテーマ: OSの設定に従う")
    print("   - ライトテーマ: 明るい背景")
    print("   - ダークテーマ: 暗い背景")
    print("   - FleDjSONテーマ: 紫背景・ライムグリーン文字")
    print("\n確認ポイント:")
    print("✓ テーマが切り替わること")
    print("✓ 「○○テーマに変更しました」の通知が表示されること")
    print("✓ FleDjSONテーマで紫とライムグリーンの配色になること")
    print("\nデバッグ情報:")
    print("- コンソールに「[THEME] change_theme called with: <テーマ名>」が表示される")
    print("- コンソールに「[OK] テーマを <テーマ名> に変更しました」が表示される")

if __name__ == "__main__":
    main()