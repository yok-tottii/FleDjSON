#!/usr/bin/env python
"""
テスト実行と結果分析のスクリプト。
コードベースをテストし、カバレッジレポートを生成します。
"""

import os
import sys
import subprocess
import argparse
import time
from datetime import datetime

# プロジェクトルートディレクトリを取得
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# テスト結果ディレクトリ
TEST_RESULTS_DIR = os.path.join(PROJECT_ROOT, "test_results")
os.makedirs(TEST_RESULTS_DIR, exist_ok=True)


def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(description="FleDjSONのテスト実行スクリプト")
    parser.add_argument(
        "-m", "--marker", 
        help="実行するテストのマーカー（unit, integration, e2e, performance, etc.）"
    )
    parser.add_argument(
        "-p", "--path", 
        help="特定のテストファイルまたはディレクトリを指定"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="詳細な出力を表示"
    )
    parser.add_argument(
        "-c", "--coverage", 
        action="store_true", 
        help="カバレッジレポートを生成"
    )
    parser.add_argument(
        "--html", 
        action="store_true", 
        help="HTMLカバレッジレポートを生成"
    )
    return parser.parse_args()


def print_header(title):
    """整形されたヘッダーを表示"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")


def run_tests(args):
    """pytestを実行してテストを実施"""
    print_header("FleDjSONのテスト実行")
    
    # テストコマンドの構築
    cmd = ["pytest"]
    
    # 引数の追加
    if args.verbose:
        cmd.append("-v")
    
    if args.marker:
        cmd.append(f"-m {args.marker}")
    
    if args.path:
        cmd.append(args.path)
    
    # カバレッジ設定
    if args.coverage:
        cmd.append("--cov=fledjson")
        cmd.append("--cov-report=term")
        if args.html:
            html_report_dir = os.path.join(TEST_RESULTS_DIR, "html_coverage")
            cmd.append(f"--cov-report=html:{html_report_dir}")
    
    # コマンドを表示
    print(f"実行コマンド: {' '.join(cmd)}")
    print("-" * 80)
    
    # テスト開始時間
    start_time = time.time()
    
    # サブプロセスとして実行
    result = subprocess.run(" ".join(cmd), shell=True, cwd=PROJECT_ROOT)
    
    # テスト終了時間
    end_time = time.time()
    duration = end_time - start_time
    
    print("-" * 80)
    print(f"テスト実行時間: {duration:.2f} 秒")
    
    return result.returncode


def analyze_results(exit_code):
    """テスト結果の分析"""
    print_header("テスト結果分析")
    
    if exit_code == 0:
        print("[OK] 全てのテストが成功しました！")
        status = "成功"
    else:
        print(f"[ERROR] テスト失敗: 終了コード {exit_code}")
        status = "失敗"
    
    # 結果サマリーをファイルに保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_file = os.path.join(TEST_RESULTS_DIR, f"test_summary_{timestamp}.txt")
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(f"テスト実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"テスト結果: {status}\n")
        f.write(f"終了コード: {exit_code}\n")
    
    print(f"\nテスト結果サマリーをファイルに保存しました: {summary_file}")
    
    if exit_code == 0:
        # HTMLレポートがある場合はパスを表示
        html_report = os.path.join(TEST_RESULTS_DIR, "html_coverage", "index.html")
        if os.path.exists(html_report):
            print(f"\nHTMLカバレッジレポート: {html_report}")
    
    return exit_code


def main():
    """メイン関数"""
    # 引数解析
    args = parse_arguments()
    
    # テスト実行
    exit_code = run_tests(args)
    
    # 結果分析
    result_code = analyze_results(exit_code)
    
    return result_code


if __name__ == "__main__":
    sys.exit(main())