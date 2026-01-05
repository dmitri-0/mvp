# app.py - точка входа в приложение
import sys
from PySide6.QtWidgets import QApplication
from core.main_window import MainWindow
from core.repository import NoteRepository
from core.tray_controller import TrayController
from core.hotkey_controller import HotkeyController
from core.config import Config


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Загрузка конфигурации
    config = Config("config.json")
    
    # Инициализация репозитория
    repo = NoteRepository(config.get("database_path", "notes.db"))
    
    # Создание главного окна
    window = MainWindow(repo, config)
    
    # Контроллеры
    tray = TrayController(window)
    hotkeys = HotkeyController(window, config)
    hotkeys.start()
    
    window.show_and_focus()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
