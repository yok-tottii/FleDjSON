"""
ロギング設定モジュール

FleDjSONアプリケーション全体で使用するロギング設定を管理します。
環境変数DEBUG_MODEと連携し、適切なログレベルを設定します。
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional

from debug_control import get_debug_control


class FleDjSONLogger:
    """FleDjSON用のロガー設定クラス"""
    
    _instance: Optional['FleDjSONLogger'] = None
    _loggers: dict = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.debug_control = get_debug_control()
        self._setup_logging()
    
    def _setup_logging(self):
        """ロギングの初期設定"""
        # ログディレクトリの作成
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # ルートロガーの設定
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # 全てのレベルをキャプチャ
        
        # 既存のハンドラーをクリア
        root_logger.handlers.clear()
        
        # フォーマッターの作成
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(levelname)s - %(message)s'
        )
        
        # コンソールハンドラー
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self._get_console_log_level())
        console_handler.setFormatter(simple_formatter)
        root_logger.addHandler(console_handler)
        
        # ファイルハンドラー（デバッグモード時のみ）
        if self.debug_control.is_debug_mode():
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir / "fledjson.log",
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(detailed_formatter)
            root_logger.addHandler(file_handler)
    
    def _get_console_log_level(self) -> int:
        """コンソール出力のログレベルを決定"""
        debug_mode = self.debug_control.get_debug_mode()
        
        if debug_mode == 0:  # 本番モード
            return logging.WARNING
        elif debug_mode == 1:  # 通常デバッグ
            return logging.INFO
        else:  # 詳細デバッグ
            return logging.DEBUG
    
    def get_logger(self, name: str) -> logging.Logger:
        """モジュール用のロガーを取得"""
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        return self._loggers[name]
    
    def update_log_level(self):
        """DEBUG_MODEの変更に応じてログレベルを更新"""
        console_handler = logging.getLogger().handlers[0]
        if isinstance(console_handler, logging.StreamHandler):
            console_handler.setLevel(self._get_console_log_level())


# シングルトンインスタンス
_logger_config = FleDjSONLogger()


def get_logger(name: str) -> logging.Logger:
    """
    モジュール用のロガーを取得
    
    Args:
        name: モジュール名（通常は__name__を使用）
    
    Returns:
        設定済みのロガーインスタンス
    """
    return _logger_config.get_logger(name)


def update_log_levels():
    """環境変数の変更に応じてログレベルを更新"""
    _logger_config.update_log_level()


# ログレベルのマッピング（移行時の参考用）
EMOJI_TO_LEVEL = {
    "[OK]": logging.INFO,      # 成功
    "[ERROR]": logging.ERROR,     # エラー
    "[WARNING]": logging.WARNING,   # 警告
    "[INFO]": logging.INFO,      # 情報
    "[UPDATE]": logging.DEBUG,     # 処理中
    "[SAVE]": logging.INFO,      # 保存操作
    "[DEBUG]": logging.DEBUG,     # デバッグ/検索
    "[FILE]": logging.DEBUG,     # ファイル操作
    "[NOTE]": logging.DEBUG,     # 編集操作
    "[THEME]": logging.INFO,      # テーマ変更
    "[DATA]": logging.DEBUG,     # データ/統計
    "[TREE]": logging.DEBUG,     # ツリー構造
    "[CONFIG]": logging.INFO,      # 設定変更
    "[USER]": logging.DEBUG,     # ユーザー操作
}