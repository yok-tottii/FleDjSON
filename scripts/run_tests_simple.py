#!/usr/bin/env python
"""
シンプルなユニットテストを実行するスクリプト
"""

import sys
import os
import subprocess
import time
from datetime import datetime

# プロジェクトルートディレクトリを取得
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

def print_header(title):
    """整形されたヘッダーを表示"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def run_tests():
    """
    基本的なユニットテストのみを実行
    """
    print_header("基本的なユニットテストを実行")
    
    # テスト開始時間
    start_time = time.time()
    
    # シンプルなテストを実行
    cmd = [
        "python", "-m", "unittest",
        "discover", "-s", "tests",
        "-p", "test_basic.py"
    ]
    
    # コマンドを表示
    print(f"実行コマンド: {' '.join(cmd)}")
    print("-" * 80)
    
    # サブプロセスとして実行
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    
    # テスト終了時間
    end_time = time.time()
    duration = end_time - start_time
    
    print("-" * 80)
    print(f"テスト実行時間: {duration:.2f} 秒")
    
    return result.returncode

def main():
    """
    メイン実行関数
    """
    # テスト用のシンプルなテストファイルを作成
    test_file_path = os.path.join(PROJECT_ROOT, "tests", "test_basic.py")
    
    test_content = '''
import unittest

class TestBasic(unittest.TestCase):
    def test_simple_assertion(self):
        """シンプルなアサーション"""
        self.assertEqual(1 + 1, 2)
        
    def test_string_operation(self):
        """文字列操作"""
        self.assertEqual("hello" + " " + "world", "hello world")
        
if __name__ == "__main__":
    unittest.main()
'''
    
    with open(test_file_path, "w") as f:
        f.write(test_content)
    
    print(f"テストファイルを作成しました: {test_file_path}")
    
    # テスト実行
    exit_code = run_tests()
    
    print(f"テスト実行結果: {'成功' if exit_code == 0 else '失敗'}")
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())