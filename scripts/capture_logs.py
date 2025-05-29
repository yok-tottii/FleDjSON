#!/usr/bin/env python3
"""ログキャプチャスクリプト"""
import subprocess
import sys
import time

# アプリを起動してログをキャプチャ
proc = subprocess.Popen(
    ["poetry", "run", "python", "src/main.py"],
    cwd="/Users/toshiyuki/Documents/program_source/fledjson-dev",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# 3秒間ログを収集
start_time = time.time()
while time.time() - start_time < 3:
    line = proc.stdout.readline()
    if line:
        print(line.rstrip())

# プロセスを終了
proc.terminate()
proc.wait()