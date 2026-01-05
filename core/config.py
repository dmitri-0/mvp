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
                try:
                    data = json.load(f)
                    return self._migrate(data)
                except json.JSONDecodeError:
                    return self._default_config()
        return self._default_config()

    def _migrate(self, data):
        """Миграция старых форматов конфигурации"""
        hotkeys = data.get("hotkeys", {})
        
        # Проверка на старую плоскую структуру (если есть ключ show_window прямо в hotkeys)
        if "show_window" in hotkeys:
            default = self._default_config()
            new_hotkeys = default["hotkeys"]
            
            # Перенос глобальных
            if "show_window" in hotkeys:
                new_hotkeys["global"]["show_window"] = hotkeys["show_window"]
            if "quit" in hotkeys:
                new_hotkeys["global"]["quit"] = hotkeys["quit"]
                
            # Перенос локальных
            if "toggle_focus" in hotkeys:
                # Пытаемся адаптировать старый формат если он был в pynput стиле
                val = hotkeys["toggle_focus"]
                if val == "<alt>+s": val = "F3" # Сброс на новый дефолт если был старый
                new_hotkeys["local"]["toggle_focus"] = val
            if "add_note" in hotkeys:
                new_hotkeys["local"]["add_note"] = hotkeys["add_note"]
            if "delete_note" in hotkeys:
                new_hotkeys["local"]["delete_note"] = hotkeys["delete_note"]
                
            data["hotkeys"] = new_hotkeys
            # Сохраняем мигрированную версию
            self.data = data
            self.save()
            
        return data
    
    def _default_config(self):
        """Конфигурация по умолчанию"""
        return {
            "database_path": "notes.db",
            "font_family": "Consolas",
            "font_size": 11,
            "hotkeys": {
                "global": {
                    "show_window": "<alt>+s",
                    "quit": "<shift>+<esc>"
                },
                "local": {
                    "toggle_focus": "F3",
                    "add_note": "F4",
                    "delete_note": "F8",
                    "settings": "Ctrl+,"
                }
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
