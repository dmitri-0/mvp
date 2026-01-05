# core/hotkey_controller.py
import threading
from PySide6.QtCore import QObject, Signal
from pynput import keyboard


class HotkeySignals(QObject):
    """Сигналы для глобальных горячих клавиш"""
    show_signal = Signal()
    hide_signal = Signal()
    quit_signal = Signal()


class HotkeyController:
    """Контроллер глобальных горячих клавиш"""
    
    def __init__(self, window, config):
        self.window = window
        self.config = config
        self.signals = HotkeySignals()
        self.signals.show_signal.connect(window.show_and_focus)
        self.signals.hide_signal.connect(window.hide_to_tray)
        self.signals.quit_signal.connect(window.quit_app)
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        """Запуск прослушивания горячих клавиш"""
        self._thread.start()

    def _run(self):
        """Главный цикл прослушивания горячих клавиш"""
        hotkeys_config = self.config.get("hotkeys", {})
        show_key = hotkeys_config.get("show_window", "<alt>+s")
        quit_key = hotkeys_config.get("quit", "<shift>+<esc>")
        
        with keyboard.GlobalHotKeys({
            show_key: self.signals.show_signal.emit,
            quit_key: self.signals.quit_signal.emit,
        }) as h:
            h.join()
