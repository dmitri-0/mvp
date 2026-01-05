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
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
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
