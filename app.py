# app.py - точка входа в приложение
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from core.main_window import MainWindow
from core.repository import NoteRepository
from core.tray_controller import TrayController
from core.hotkey_controller import HotkeyController
from core.config import Config
from core.theme_manager import ThemeManager


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Установка иконки приложения
    icon_path = resource_path("app_icon.ico")
    app.setWindowIcon(QIcon(icon_path))
    
    # Загрузка конфигурации
    config = Config("config.json")
    
    # Применение темы при запуске
    theme = config.get("theme", "light")
    ThemeManager.apply_theme(theme)
    
    # Инициализация репозитория
    repo = NoteRepository(config.get("database_path", "notes.db"))
    
    # Создание главного окна
    window = MainWindow(repo, config)
    
    # Контроллеры
    tray = TrayController(window)
    hotkeys = HotkeyController(window, config)
    
    # ВАЖНО: устанавливаем ссылку на контроллер горячих клавиш в окно
    # чтобы nativeEvent мог их обрабатывать
    window.set_hotkey_controller(hotkeys)
    
    hotkeys.start()
    
    # Корректная остановка хоткеев при выходе и очистка буфера ввода
    def on_quit():
        hotkeys.stop()
        # Очистка буфера ввода (Linux/Windows)
        try:
            if sys.platform == 'win32':
                import msvcrt
                while msvcrt.kbhit():
                    msvcrt.getch()
            else:
                import termios
                import tty
                termios.tcflush(sys.stdin, termios.TCIOFLUSH)
        except ImportError:
            pass
        except Exception as e:
            print(f"Error flushing input buffer: {e}")

    app.aboutToQuit.connect(on_quit)
    
    window.show_and_focus()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
