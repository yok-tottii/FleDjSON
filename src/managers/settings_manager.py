"""設定管理マネージャー"""
import json
import os
from typing import Dict, Any, Optional, Callable
from flet import ThemeMode
from event_hub import EventHub, EventType
from translation import set_language as set_global_language, t
from logging_config import get_logger

logger = get_logger(__name__)


class SettingsManager:
    """アプリケーション設定の管理を担当するマネージャー"""
    
    def __init__(self, event_hub: EventHub):
        """SettingsManagerの初期化
        
        Args:
            event_hub: イベントハブ
        """
        self._event_hub = event_hub
        self._settings_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "storage", "data", "settings.json"
        )
        self._settings: Dict[str, Any] = self._load_settings()
        self._theme_change_callbacks: list[Callable] = []
        
        # イベントハブに登録
        self._event_hub.subscribe("theme_changed", self._on_theme_changed)
    
    def _load_settings(self) -> Dict[str, Any]:
        """設定ファイルから設定を読み込む"""
        default_settings = {
            "theme_mode": "system",  # system, light, dark
            "color_scheme_seed": "indigo",
            "auto_save": True,
            "recent_files": [],
            "language": "ja"  # デフォルトは日本語
        }
        
        if os.path.exists(self._settings_file):
            try:
                with open(self._settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # デフォルト設定とマージ
                    default_settings.update(loaded_settings)
            except (json.JSONDecodeError, IOError):
                # 読み込みエラーの場合はデフォルト設定を使用
                pass
        
        # グローバル翻訳システムに言語を設定
        set_global_language(default_settings.get("language", "ja"))
        
        return default_settings
    
    def save_settings(self) -> None:
        """現在の設定をファイルに保存"""
        os.makedirs(os.path.dirname(self._settings_file), exist_ok=True)
        try:
            with open(self._settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
        except IOError as e:
            self._event_hub.publish("error_occurred", {"message": t("error.settings_save_failed").format(error=str(e))})
    
    def get_theme_mode(self) -> ThemeMode:
        """現在のテーマモードを取得"""
        mode = self._settings.get("theme_mode", "system")
        if mode == "light":
            return ThemeMode.LIGHT
        elif mode == "dark":
            return ThemeMode.DARK
        else:
            return ThemeMode.SYSTEM
    
    def set_theme_mode(self, mode: str) -> None:
        """テーマモードを設定
        
        Args:
            mode: "system", "light", "dark"のいずれか
        """
        if mode not in ["system", "light", "dark", "fledjson"]:
            raise ValueError(f"Invalid theme mode: {mode}")
        
        self._settings["theme_mode"] = mode
        self.save_settings()
        
        # テーマ変更イベントを発行
        self._event_hub.publish("theme_mode_changed", {"mode": mode})
        
        # コールバックを実行
        for callback in self._theme_change_callbacks:
            callback(mode)
    
    def get_color_scheme_seed(self) -> str:
        """カラースキームシードを取得"""
        return self._settings.get("color_scheme_seed", "indigo")
    
    def set_color_scheme_seed(self, seed: str) -> None:
        """カラースキームシードを設定"""
        self._settings["color_scheme_seed"] = seed
        self.save_settings()
        self._event_hub.publish("color_scheme_changed", {"seed": seed})
    
    def add_theme_change_callback(self, callback: Callable) -> None:
        """テーマ変更時のコールバックを追加"""
        self._theme_change_callbacks.append(callback)
    
    def remove_theme_change_callback(self, callback: Callable) -> None:
        """テーマ変更時のコールバックを削除"""
        if callback in self._theme_change_callbacks:
            self._theme_change_callbacks.remove(callback)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """設定値を取得"""
        return self._settings.get(key, default)
    
    def set_setting(self, key: str, value: Any) -> None:
        """設定値を設定"""
        self._settings[key] = value
        self.save_settings()
    
    def add_recent_file(self, file_path: str) -> None:
        """最近使用したファイルを追加"""
        recent_files = self._settings.get("recent_files", [])
        
        # 既に存在する場合は削除
        if file_path in recent_files:
            recent_files.remove(file_path)
        
        # 先頭に追加
        recent_files.insert(0, file_path)
        
        # 最大10件まで保持
        self._settings["recent_files"] = recent_files[:10]
        self.save_settings()
    
    def get_recent_files(self) -> list[str]:
        """最近使用したファイルのリストを取得"""
        return self._settings.get("recent_files", [])
    
    def get_language(self) -> str:
        """現在の言語設定を取得
        
        Returns:
            言語コード（"ja" または "en"）
        """
        return self._settings.get("language", "ja")
    
    def set_language(self, language: str) -> None:
        """言語を設定
        
        Args:
            language: 言語コード（"ja" または "en"）
        """
        if language not in ["ja", "en"]:
            logger.warning(f"Invalid language code: {language}, defaulting to 'ja'")
            language = "ja"
        
        self._settings["language"] = language
        self.save_settings()
        
        # グローバル翻訳システムに反映
        set_global_language(language)
        
        # 言語変更イベントを発行
        self._event_hub.publish(EventType.LANGUAGE_CHANGED, {"language": language})
        logger.info(f"Language changed to: {language}")
    
    def _on_theme_changed(self, data: Dict[str, Any]) -> None:
        """テーマ変更イベントのハンドラ"""
        mode = data.get("mode")
        if mode:
            self.set_theme_mode(mode)