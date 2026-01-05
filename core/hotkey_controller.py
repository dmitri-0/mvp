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
        self._listener = None

    def start(self):
        """Запуск прослушивания горячих клавиш"""
        hotkeys = self.config.get("hotkeys", {})
        
        # Поддержка новой вложенной структуры с fallback на старую
        if "global" in hotkeys:
            global_keys = hotkeys["global"]
        else:
            global_keys = hotkeys

        show_key = global_keys.get("show_window", "<alt>+s")
        quit_key = global_keys.get("quit", "<shift>+<esc>")
        
        hotkey_map = {
            show_key: self.signals.show_signal.emit,
            quit_key: self.signals.quit_signal.emit,
        }

        try:
            self._listener = keyboard.GlobalHotKeys(hotkey_map)
            self._listener.start()
        except ValueError as e:
            print(f"Error initializing hotkeys: {e}. Falling back to defaults.")
            try:
                self._listener = keyboard.GlobalHotKeys({
                    "<alt>+s": self.signals.show_signal.emit,
                    "<shift>+<esc>": self.signals.quit_signal.emit,
                })
                self._listener.start()
            except Exception as e2:
                print(f"Critical error in hotkeys: {e2}")

    def stop(self):
        """Остановка прослушивания"""
        if self._listener:
            self._listener.stop()
            self._listener = None
