# app.py - точка входа в приложение
import sys
import os
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
