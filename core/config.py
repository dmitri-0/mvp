# core/config.py
import json
import os


class Config:
    """Управление настройками приложения"""
    
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.data = self._load()
    
    def _load(self):
        """Загрузка конфигурации из JSON файла"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._default_config()
    
    def _default_config(self):
        """Конфигурация по умолчанию"""
        return {
            "database_path": "notes.db",
            "font_family": "Consolas",
            "font_size": 11,
            "hotkeys": {
                "show_window": "<alt>+s",
                "toggle_focus": "Tab",
                "add_note": "F4",
                "delete_note": "F8",
                "quit": "<shift>+<esc>"
            }
        }
    
    def save(self):
        """Сохранение конфигурации в файл"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def get(self, key, default=None):
        """Получение значения по ключу"""
        return self.data.get(key, default)
    
    def set(self, key, value):
        """Установка значения по ключу"""
        self.data[key] = value
        self.save()
