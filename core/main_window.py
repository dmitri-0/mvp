import sys

from PySide6.QtCore import Qt, QEvent, QUrl
from PySide6.QtGui import QTextDocument, QKeySequence, QShortcut, QImage
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QSplitter,
    QTreeWidget,
    QStatusBar,
    QMessageBox,
)
import subprocess
import tempfile
import os

from core.clipboard_monitor import ClipboardMonitor
from core.config import Config
from core.note_editor import NoteEditor
from core.repository import NoteRepository
from core.theme_manager import ThemeManager
from core.ui.mixins.editor_storage_mixin import EditorStorageMixin
from core.ui.mixins.editor_style_mixin import EditorStyleMixin
from core.ui.mixins.tree_navigation_mixin import TreeNavigationMixin
from core.ui.mixins.window_state_mixin import WindowStateMixin
from core.ui.mixins.tree_data_mixin import TreeDataMixin
from core.ui.mixins.note_action_mixin import NoteActionMixin
from core.ui.mixins.branch_control_mixin import BranchControlMixin
from core.ui.settings_dialog import SettingsDialog
from core.ui.history_dialog import HistoryDialog
from core.ui.image_selection_dialog import ImageSelectionDialog


class MainWindow(
    QMainWindow,
    WindowStateMixin,
    EditorStyleMixin,
    TreeNavigationMixin,
    EditorStorageMixin,
    TreeDataMixin,
    NoteActionMixin,
    BranchControlMixin,
):
    """Главное окно приложения"""

    def __init__(self, repo: NoteRepository, config: Config):
        super().__init__()
        self.repo = repo
        self.config = config
        self.setWindowTitle("Notes Manager")
        self.resize(1000, 600)

        # Восстановление сохраненной геометрии окна
        self._restore_window_geometry()

        # Левая панель - дерево заметок
        self.tree_notes = QTreeWidget()
        self.tree_notes.setHeaderLabel("Notes")
        self.tree_notes.currentItemChanged.connect(self.on_note_selected)
        self.tree_notes.setSelectionMode(QTreeWidget.ExtendedSelection)

        # Правая панель - редактор
        self.editor = NoteEditor()
        self.editor.setAcceptRichText(True)
        self.editor.set_context(self.repo)
        self.editor.set_main_window(self)  # Устанавливаем ссылку на главное окно
        self.editor.focusOut.connect(self._on_editor_focus_out)

        # Применение шрифта
        self._apply_font()

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.tree_notes)
        self.splitter.addWidget(self.editor)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.splitterMoved.connect(self._save_splitter_state)
        self.setCentralWidget(self.splitter)

        # Восстановление позиции сплиттера
        self._restore_splitter_state()

        # Строка состояния
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.current_note_id = None  # id заметки, загруженной в редактор
        self.focused_widget = self.tree_notes
        self.toggle_focus_shortcut = None  # Ссылка на шорткат
        self.hotkey_controller = None  # Сохраним ссылку на контроллер глобальных клавиш

        # Флаги защиты от гонок событий
        self._is_switching_note = False
        self._is_reloading_tree = False

        # Последняя активная ветка ("Текущие" или "Буфер обмена")
        self._last_active_branch = "Текущие"

        # Инициализация монитора буфера обмена
        self.clipboard_monitor = ClipboardMonitor(self.repo, self)
        self.clipboard_monitor.clipboard_changed.connect(self._on_clipboard_note_created)

        # Шорткаты
        self._setup_shortcuts()

        # Загрузка и восстановление состояния
        self.load_notes_tree()
        self._restore_last_state()

    def _update_status_bar(self, note_id=None):
        """Обновление строки состояния с путем текущей заметки"""
        if note_id is None:
            note_id = self.current_note_id
        
        if note_id:
            path = self.repo.get_note_path(note_id)
            if path:
                self.status_bar.showMessage(path)
            else:
                self.status_bar.clearMessage()
        else:
            self.status_bar.clearMessage()

    def _on_clipboard_note_created(self, note_id):
        """Обработчик создания новой записи из буфера обмена."""
        # Перезагружаем дерево чтобы отобразить новую запись
        self.load_notes_tree()
        # Можно автоматически выбрать новую запись если нужно
        # self._select_note_by_id(note_id)

    def show_history_dialog(self):
        """Показать окно истории недавно измененных заметок (Alt+D)."""
        dlg = HistoryDialog(self.repo, self, self)
        dlg.exec()

    def edit_image(self):
        """Редактировать изображение из заметки (F12)"""
        if not self.current_note_id:
            QMessageBox.warning(self, "Ошибка", "Заметка не выбрана.")
            return
            
        editor_path = self.config.get("image_editor_path", "")
        if not editor_path or not os.path.exists(editor_path):
            QMessageBox.warning(
                self,
                "Ошибка",
                "Путь к редактору изображений не настроен.\n"
                f"Укажите путь в config.json: image_editor_path"
            )
            return
        
        # Получаем список изображений
        images = self.editor.get_images_in_content()
        
        if not images:
            QMessageBox.information(self, "Инфо", "В заметке нет изображений.")
            return
        
        selected_image = None
        if len(images) == 1:
            selected_image = images[0]
        else:
            # Открываем диалог выбора
            dlg = ImageSelectionDialog(images, self)
            if dlg.exec():
                selected_image = dlg.selected_image
        
        if not selected_image:
            return
        
        # selected_image = (id, note_id, name, bytes, mime)
        att_id, _, name, img_bytes, mime = selected_image
        
        # Создаем временный файл
        ext = name.split('.')[-1] if '.' in name else 'png'
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
        temp_file.write(img_bytes)
        temp_file.close()
        
        try:
            # Запускаем редактор
            if sys.platform == 'win32':
                subprocess.Popen([editor_path, temp_file.name])
            else:
                subprocess.Popen([editor_path, temp_file.name])
            
            # TODO: Можно добавить отслеживание изменений файла и обновление в базе
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть редактор: {e}")

    def toggle_theme(self):
        """Переключение между светлой и темной темой (F10)"""
        current_theme = self.config.get("theme", "light")
        new_theme = "dark" if current_theme == "light" else "light"
        
        self.config.set("theme", new_theme)
        ThemeManager.apply_theme(new_theme)

    def toggle_view_mode(self):
        """Переключение режима просмотра (обычный текст / markdown) по F3"""
        self.editor.toggle_view_mode()

    def set_hotkey_controller(self, controller):
        """Установить контроллер глобальных горячих клавиш"""
        self.hotkey_controller = controller

    def nativeEvent(self, eventType, message):
        """Обработка нативных событий для глобальных горячих клавиш"""
        if self.hotkey_controller:
            handled, result = self.hotkey_controller.handle_native_event(eventType, message)
            if handled:
                return handled, result
        return super().nativeEvent(eventType, message)

    def resizeEvent(self, event):
        """Сохранение размера окна при изменении"""
        super().resizeEvent(event)
        self._save_window_geometry()

    def _setup_shortcuts(self):
        """Настройка горячих клавиш"""
        # Смена фокуса
        hotkeys = self.config.get("hotkeys", {})

        # Безопасное получение локальных настроек
        if "local" in hotkeys:
            local_keys = hotkeys["local"]
        else:
            # Fallback для старых конфигов или если миграция не прошла
            local_keys = hotkeys

        # 1. Основные команды
        self._bind_shortcut("toggle_view_mode_shortcut", local_keys.get("toggle_view_mode", "F3"), self.toggle_view_mode)
        self._bind_shortcut("add_note_shortcut", local_keys.get("add_note", "F4"), self.add_note)
        self._bind_shortcut("del_note_shortcut", local_keys.get("delete_note", "F8"), self.delete_notes)
        self._bind_shortcut("settings_shortcut", local_keys.get("settings", "Ctrl+,"), self.open_settings)
        self._bind_shortcut("quit_shortcut", local_keys.get("quit", "Shift+Esc"), self.quit_app)

        # Копирование содержимого заметки
        self._bind_shortcut("copy_note_shortcut", local_keys.get("copy_note", "Ctrl+C"), self.copy_current_note_to_clipboard)
        
        self._bind_shortcut("move_note_shortcut", local_keys.get("move_note", "F6"), self.move_notes)

        # Новые функции
        self._bind_shortcut("add_to_favorites_shortcut", local_keys.get("add_to_favorites", "F5"), self.add_to_favorites)
        self._bind_shortcut("rename_note_shortcut", local_keys.get("rename_note", "F2"), self.rename_note)
        self._bind_shortcut("edit_image_shortcut", local_keys.get("edit_image", "F12"), self.edit_image)

        # Переключение между ветками (Текущие/Буфер/Избранное)
        self._bind_shortcut("toggle_branch_shortcut", local_keys.get("toggle_branch", "Alt+S"), self.toggle_current_clipboard_branch)

        # История изменений
        self._bind_shortcut("history_shortcut", local_keys.get("history", "Alt+D"), self.show_history_dialog)

        # Переключение темы
        self._bind_shortcut("toggle_theme_shortcut", local_keys.get("toggle_theme", "F10"), self.toggle_theme)

        # 2. Навигация (когда фокус в редакторе)
        self._bind_shortcut("nav_up_shortcut", local_keys.get("navigate_up", "Alt+Up"), 
                           lambda: self._navigate_tree_from_editor("up"))
        self._bind_shortcut("nav_down_shortcut", local_keys.get("navigate_down", "Alt+Down"), 
                           lambda: self._navigate_tree_from_editor("down"))
        self._bind_shortcut("nav_left_shortcut", local_keys.get("navigate_left", "Alt+Left"), 
                           lambda: self._navigate_tree_from_editor("left"))
        self._bind_shortcut("nav_right_shortcut", local_keys.get("navigate_right", "Alt+Right"), 
                           lambda: self._navigate_tree_from_editor("right"))
        
        # 3. Постраничная навигация
        self._bind_shortcut("nav_page_up_shortcut", local_keys.get("navigate_page_up", "Alt+PgUp"), 
                           lambda: self._navigate_tree_from_editor("page_up"))
        self._bind_shortcut("nav_page_down_shortcut", local_keys.get("navigate_page_down", "Alt+PgDown"), 
                           lambda: self._navigate_tree_from_editor("page_down"))

    def _bind_shortcut(self, attr_name, key_sequence, callback):
        """Вспомогательный метод для привязки шортката к атрибуту окна"""
        shortcut = getattr(self, attr_name, None)
        if shortcut:
            shortcut.setKey(QKeySequence(key_sequence))
        else:
            shortcut = QShortcut(QKeySequence(key_sequence), self)
            shortcut.activated.connect(callback)
            setattr(self, attr_name, shortcut)

    def toggle_focus(self):
        """Переключение фокуса между деревом и редактором"""
        if self.editor.hasFocus():
            # ключевой момент: редактор теряет фокус -> сохраняем
            self.save_current_note()
            self.tree_notes.setFocus()
            self.focused_widget = self.tree_notes
        else:
            self.editor.setFocus()
            self.focused_widget = self.editor

    def copy_current_note_to_clipboard(self):
        """Копирование текста текущей заметки в буфер обмена"""
        # Если фокус в редакторе и есть выделение - стандартное поведение копирования
        if self.editor.hasFocus() and self.editor.textCursor().hasSelection():
            self.editor.copy()
            return

        # Иначе (фокус в дереве или в редакторе без выделения) копируем все содержимое
        if self.current_note_id:
            # Используем текст из редактора, так как он самый актуальный
            # Если нужно HTML, можно toHtml(). Но в буфер обычно удобнее plain text.
            # Либо можно положить и то и то через QMimeData, но setText проще.
            text = self.editor.toPlainText()
            QApplication.clipboard().setText(text)

    def on_note_selected(self, current_item, previous_item):
        """Переключение на другую заметку"""
        if self._is_reloading_tree:
            return

        # Важно: currentItemChanged вызывается когда текущий элемент уже изменен.
        # Поэтому сохранение нужно делать по previous_item / previous_note_id.
        previous_note_id = None
        if previous_item is not None:
            previous_note_id = previous_item.data(0, Qt.UserRole)

        if previous_note_id and self.current_note_id == previous_note_id:
            # В редакторе сейчас ещё текст предыдущей заметки -> сохраняем её
            self._save_editor_content(previous_note_id, previous_item.text(0))

        if not current_item:
            self.current_note_id = None
            self.editor.set_current_note_id(None)
            self._update_status_bar(None)
            return

        note_id = current_item.data(0, Qt.UserRole)

        self._is_switching_note = True
        try:
            self.current_note_id = note_id
            self.editor.set_current_note_id(note_id)

            # Сохраняем ID открытой заметки
            self.repo.set_state("last_opened_note_id", note_id)

            # Обновляем строку состояния
            self._update_status_bar(note_id)

            row = self.repo.get_note(note_id)
            if not row:
                self.editor.blockSignals(True)
                self.editor.setHtml("")
                self.editor.blockSignals(False)
                return

            nid, parent_id, title, body_html, cursor_pos, updated_at = row

            self.editor.blockSignals(True)

            # Ключевой момент:
            # Раньше setHtml() выполнялся ДО addResource().
            # Тогда QTextDocument строился layout с placeholder-иконками,
            # и размеры картинок "подхватывались" только при повторном открытии заметки.
            attachments = self.repo.get_attachments(note_id)
            doc = self.editor.document()
            for att_id, name, img_bytes, mime in attachments:
                if img_bytes:
                    image = QImage.fromData(img_bytes)
                    doc.addResource(
                        QTextDocument.ImageResource,
                        QUrl(f"noteimg://{att_id}"),
                        image,
                    )

            self.editor.setHtml(body_html or "")

            # Применяем глобальный шрифт
            self._enforce_global_font()

            # Восстановление курсора
            if cursor_pos is not None:
                cursor = self.editor.textCursor()
                cursor.setPosition(min(cursor_pos, len(self.editor.toPlainText())))
                self.editor.setTextCursor(cursor)
                self.editor.ensureCursorVisible()

            self.editor.blockSignals(False)

        finally:
            self._is_switching_note = False

    def on_global_show_hotkey(self):
        """Обработчик глобального Alt+S: показать окно или переключить ветки"""
        if self.isVisible() and self.isActiveWindow():
            # Окно уже активно - переключаем между Текущие/Буфер обмена/Избранное
            self.toggle_current_clipboard_branch()
        else:
            # Окно скрыто или неактивно - показываем
            self.show_and_focus()

    def show_and_focus(self):
        """Показать и активировать окно - используется единый метод аналогичный show_from_tray"""
        # Показываем окно нормально (не свернутым)
        self.showNormal()
        # Активируем окно на передний план
        self.activateWindow()
        # Поднимаем окно выше других
        self.raise_()

        # Дополнительная активация через Windows API для надежности
        if sys.platform == "win32":
            try:
                import ctypes

                hwnd = int(self.winId())
                user32 = ctypes.windll.user32
                # SW_RESTORE = 9 (восстановить окно если свернуто)
                user32.ShowWindow(hwnd, 9)
                # Устанавливаем на передний план без звука
                user32.SetForegroundWindow(hwnd)
            except Exception as e:
                print(f"Ошибка при активации окна через Windows API: {e}")

        # Фокус на редактор если заметка выбрана
        if self.current_note_id:
            self.editor.setFocus()

    def hide_to_tray(self):
        """Скрыть в трей"""
        self.save_current_note()
        self.hide()

    def quit_app(self):
        """Выход из приложения"""
        self.save_current_note()
        QApplication.instance().quit()

    def changeEvent(self, event):
        # Сохранение при сворачивании
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                self.save_current_note()
        super().changeEvent(event)

    def keyPressEvent(self, event):
        """Обработка нажатий клавиш"""
        # Ctrl+, независимо от раскладки (Windows)
        if sys.platform == "win32":
            # VK_OEM_COMMA = 0xBC (физическая клавиша запятой)
            if (event.modifiers() & Qt.ControlModifier) and event.nativeVirtualKey() == 0xBC:
                self.open_settings()
                event.accept()
                return

        if event.key() == Qt.Key_Escape:
            self.hide_to_tray()
            event.accept()
        else:
            super().keyPressEvent(event)

    def open_settings(self):
        """Открытие окна настроек"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            # Обновляем шорткаты
            self._setup_shortcuts()
            # Применение новых настроек
            self._apply_font()
            # Перезагрузить текущую заметку чтобы обновился шрифт
            if self.current_note_id:
                self._reload_current_note()

    def _reload_current_note(self):
        """Перезагрузка текущей заметки для применения новых настроек"""
        if not self.current_note_id:
            return

        cursor_pos = self.editor.textCursor().position()
        row = self.repo.get_note(self.current_note_id)
        if not row:
            return

        _, _, _, body_html, _, _ = row

        self.editor.blockSignals(True)

        # Важно: зарегистрировать ресурсы ДО setHtml, иначе document/layout
        # сначала строится с placeholder-иконками (треугольники), а размеры
        # картинок учитываются только при повторном чтении.
        attachments = self.repo.get_attachments(self.current_note_id)
        doc = self.editor.document()
        for att_id, name, img_bytes, mime in attachments:
            if img_bytes:
                image = QImage.fromData(img_bytes)
                doc.addResource(
                    QTextDocument.ImageResource,
                    QUrl(f"noteimg://{att_id}"),
                    image,
                )

        self.editor.setHtml(body_html or "")

        # Принудительно применяем глобальный шрифт при перезагрузке
        self._enforce_global_font()

        # Восстановление курсора
        cursor = self.editor.textCursor()
        cursor.setPosition(min(cursor_pos, len(self.editor.toPlainText())))
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()

        self.editor.blockSignals(False)
