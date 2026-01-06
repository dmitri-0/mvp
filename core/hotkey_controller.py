from PySide6.QtCore import QObject, Signal
import sys
import platform

# Pynput используется как fallback для не-Windows систем
try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


class HotkeySignals(QObject):
    """Сигналы для глобальных горячих клавиш"""
    show_signal = Signal()
    hide_signal = Signal()
    quit_signal = Signal()
    activated = Signal()  # Сигнал успешной активации


class HotkeyController:
    """Контроллер глобальных горячих клавиш.
    
    На Windows использует Native API (RegisterHotKey) для надежности.
    На других ОС использует pynput.
    """
    
    # Windows API Constants
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    WM_HOTKEY = 0x0312
    VK_ESCAPE = 0x1B
    
    def __init__(self, window, config):
        self.window = window
        self.config = config
        self.signals = HotkeySignals()
        self.signals.show_signal.connect(window.show_and_focus)
        self.signals.hide_signal.connect(window.hide_to_tray)
        self.signals.quit_signal.connect(window.quit_app)
        
        self._listener = None
        self._native_hotkeys = {}  # id -> callback
        self._registered_ids = []
        self._current_id_counter = 1

    def start(self):
        """Запуск прослушивания горячих клавиш"""
        hotkeys = self.config.get("hotkeys", {})
        
        if "global" in hotkeys:
            global_keys = hotkeys["global"]
        else:
            global_keys = hotkeys

        show_key = global_keys.get("show_window", "<alt>+s")
        # Quit is strictly local now
        # quit_key = global_keys.get("quit", "<shift>+<esc>")
        
        if sys.platform == 'win32':
            self._register_native_windows(show_key, self.signals.show_signal.emit)
            # self._register_native_windows(quit_key, self.signals.quit_signal.emit)
        else:
            self._start_pynput(show_key)

    def stop(self):
        """Остановка прослушивания"""
        if sys.platform == 'win32':
            self._unregister_native_windows()
        
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _start_pynput(self, show_key):
        if not PYNPUT_AVAILABLE:
            print("Pynput not available")
            return

        hotkey_map = {
            show_key: self.signals.show_signal.emit,
            # quit_key: self.signals.quit_signal.emit,
        }
        
        try:
            self._listener = keyboard.GlobalHotKeys(hotkey_map)
            self._listener.start()
        except Exception as e:
            print(f"Error initializing pynput hotkeys: {e}")

    # --- Windows Native Implementation ---

    def _parse_hotkey(self, key_string):
        """Парсинг строки вида <alt>+s в (modifiers, vk)"""
        import ctypes
        
        mods = 0
        vk = 0
        
        parts = key_string.lower().replace('<', '').replace('>', '').split('+')
        
        # Последняя часть - сама клавиша
        key_char = parts[-1]
        
        # Модификаторы
        if 'alt' in parts[:-1]: mods |= self.MOD_ALT
        if 'ctrl' in parts[:-1] or 'control' in parts[:-1]: mods |= self.MOD_CONTROL
        if 'shift' in parts[:-1]: mods |= self.MOD_SHIFT
        if 'win' in parts[:-1] or 'cmd' in parts[:-1]: mods |= self.MOD_WIN
        
        # Код клавиши
        if key_char == 'esc' or key_char == 'escape':
            vk = self.VK_ESCAPE
        elif len(key_char) == 1:
            vk = ord(key_char.upper())
        else:
            # Можно расширить маппинг для F-клавиш и прочего если нужно
            pass
            
        return mods, vk

    def _register_native_windows(self, key_string, callback):
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            hwnd = int(self.window.winId())
            
            modifiers, vk = self._parse_hotkey(key_string)
            if vk == 0:
                print(f"Could not parse hotkey: {key_string}")
                return

            hotkey_id = self._current_id_counter
            self._current_id_counter += 1
            
            if user32.RegisterHotKey(hwnd, hotkey_id, modifiers, vk):
                self._native_hotkeys[hotkey_id] = callback
                self._registered_ids.append(hotkey_id)
                print(f"Registered native hotkey: {key_string} (id={hotkey_id})")
            else:
                print(f"Failed to register native hotkey: {key_string}")
                
        except Exception as e:
            print(f"Error registering native hotkey: {e}")

    def _unregister_native_windows(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = int(self.window.winId())
            
            for hid in self._registered_ids:
                user32.UnregisterHotKey(hwnd, hid)
            self._registered_ids.clear()
            self._native_hotkeys.clear()
            self._current_id_counter = 1
        except Exception:
            pass

    def handle_native_event(self, event_type, message):
        """Обработка системных событий (вызывается из MainWindow)"""
        if sys.platform != 'win32':
            return False, 0
            
        try:
            import ctypes
            from ctypes import wintypes
            
            # Структура MSG не всегда доступна напрямую через PySide6 аргумент message
            # message - это 'sip.voidptr', нужно привести к MSG
            
            if event_type == "windows_generic_MSG":
                msg = wintypes.MSG.from_address(int(message))
                
                if msg.message == self.WM_HOTKEY:
                    hotkey_id = int(msg.wParam)
                    if hotkey_id in self._native_hotkeys:
                        # Вызываем коллбек
                        self._native_hotkeys[hotkey_id]()
                        return True, 0
                        
        except Exception as e:
            print(f"Native event error: {e}")
            
        return False, 0
