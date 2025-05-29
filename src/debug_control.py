"""
debug_control.py
デバッグ出力制御システム

環境変数DEBUG_MODEに基づいて、初期化メッセージやデバッグ情報の出力を制御する
本番環境では不要な出力を抑制し、開発時には詳細な情報を提供する
"""
import os
from typing import Optional


class DebugControl:
    """
    デバッグ出力制御クラス
    
    環境変数DEBUG_MODEの値に基づいて出力レベルを制御:
    - None/False/"0"/"false": 本番モード（初期化メッセージなし）
    - "1"/"true"/"True": 開発モード（初期化メッセージあり）
    - "2"/"verbose": 詳細モード（全デバッグ情報表示）
    """
    
    _instance: Optional['DebugControl'] = None
    _debug_mode: Optional[str] = None
    
    def __new__(cls):
        """シングルトンパターンで実装"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        else:
            # 環境変数が変更された場合は再初期化
            current_mode = os.environ.get("DEBUG_MODE", "0").lower()
            if cls._instance._debug_mode != current_mode:
                cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """環境変数から設定を読み込み"""
        self._debug_mode = os.environ.get("DEBUG_MODE", "0").lower()
        
        # 有効な値の正規化
        if self._debug_mode in ["true", "1", "yes", "on"]:
            self._debug_mode = "1"
        elif self._debug_mode in ["verbose", "2", "debug"]:
            self._debug_mode = "2"
        else:
            self._debug_mode = "0"
    
    @property
    def is_enabled(self) -> bool:
        """デバッグモードが有効かどうか"""
        return self._debug_mode in ["1", "2"]
    
    @property
    def is_verbose(self) -> bool:
        """詳細モードが有効かどうか"""
        return self._debug_mode == "2"
    
    def get_debug_mode(self) -> int:
        """デバッグモードレベルを数値で取得"""
        return int(self._debug_mode)
    
    def is_debug_mode(self) -> bool:
        """デバッグモードが有効かどうか（DEBUG_MODE>=1）"""
        return int(self._debug_mode) >= 1
    
    def print_init(self, message: str):
        """
        初期化メッセージの条件付き出力
        
        Args:
            message: 出力するメッセージ
        """
        if self.is_enabled:
            print(message)
    
    @classmethod
    def get_instance(cls) -> 'DebugControl':
        """インスタンスを取得（シングルトン）"""
        return cls()


# グローバルインスタンス
debug_control = DebugControl.get_instance()


# 現在使用されている関数のみ提供
def print_init(message: str):
    """初期化メッセージの条件付き出力（グローバル関数）"""
    debug_control.print_init(message)


def get_debug_control() -> DebugControl:
    """デバッグ制御インスタンスを取得"""
    return debug_control


# 将来の拡張用に残しておく関数（コメントアウト）
# def print_debug(message: str):
#     """デバッグメッセージの条件付き出力（グローバル関数）"""
#     if debug_control.is_verbose:
#         print(f"[DEBUG] DEBUG: {message}")
# 
# def print_verbose(message: str):
#     """詳細メッセージの条件付き出力（グローバル関数）"""
#     if debug_control.is_verbose:
#         print(f"[NOTE] VERBOSE: {message}")
# 
# def is_debug_enabled() -> bool:
#     """デバッグモードが有効かどうかの確認（グローバル関数）"""
#     return debug_control.is_enabled
# 
# def is_verbose_enabled() -> bool:
#     """詳細モードが有効かどうかの確認（グローバル関数）"""
#     return debug_control.is_verbose