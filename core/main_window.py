from datetime import datetime
import sys
from PySide6.QtCore import Qt, QEvent, QUrl
from PySide6.QtGui import QFont, QTextDocument, QKeySequence, QShortcut, QImage, QTextCursor, QTextCharFormat
from PySide6.QtWidgets import (
    QMainWindow, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QSplitter,
    QApplication, QDialog, QVBoxLayout, QLabel, QSpinBox,
    QLineEdit, QPushButton, QFormLayout, QMessageBox
)
from core.note_editor import NoteEditor
from core.repository import NoteRepository
from core.config import Config
from core.clipboard_monitor import ClipboardMonitor


class SettingsDialog(QDialog):
    """Диалог настроек приложения"""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.resize(400, 250)

        layout = QFormLayout()

        # Путь к базе данных
        self.db_path_edit = QLineEdit(config.get("database_path", "notes.db"))
        layout.addRow("Путь к базе данных:", self.db_path_edit)

        # Шрифт
        self.font_family_edit = QLineEdit(config.get("font_family", "Consolas"))
        layout.addRow("Шрифт:", self.font_family_edit)

        # Размер шрифта
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(config.get("font_size", 11))
        layout.addRow("Размер шрифта:", self.font_size_spin)

        # Шорткат смены фокуса
        hotkeys = config.get("hotkeys", {})
        # Поддержка вложенной структуры
        if "local" in hotkeys:
            current_focus_key = hotkeys["local"].get("toggle_focus", "F3")
        else:
            current_focus_key = hotkeys.get("toggle_focus", "F3")

        self.focus_key_edit = QLineEdit(current_focus_key)
        layout.addRow("Смена фокуса:", self.focus_key_edit)

        # Кнопки
        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)

        # Кнопка сжатия базы
        btn_vacuum = QPushButton("Сжать базу данных")
        btn_vacuum.clicked.connect(self.compact_db)

        btn_layout = QVBoxLayout()
        btn_layout.addWidget(btn_vacuum)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)

        layout.addRow("", btn_layout)
        self.setLayout(layout)

    def compact_db(self):
        """Вызов сжатия базы"""
        try:
            # Получаем репозиторий через родительское окно (MainWindow)
            repo = self.parent().repo
            repo.vacuum()
            QMessageBox.information(self, "Успех", "База данных успешно сжата.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сжатии базы данных: {e}")

    def save_settings(self):
        """Сохранение настроек"""
        self.config.set("database_path", self.db_path_edit.text())
        self.config.set("font_family", self.font_family_edit.text())
        self.config.set("font_size", self.font_size_spin.value())

        hotkeys = self.config.get("hotkeys", {})
        if "local" not in hotkeys:
            hotkeys["local"] = {}
        hotkeys["local"]["toggle_focus"] = self.focus_key_edit.text()
        self.config.set("hotkeys", hotkeys)

        QMessageBox.information(
            self,
            "Настройки",
            "Настройки сохранены. Изменения применены.",
        )
        self.accept()


class MainWindow(QMainWindow):
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

    def _on_clipboard_note_created(self, note_id):
        """Обработчик создания новой записи из буфера обмена."""
        # Перезагружаем дерево чтобы отобразить новую запись
        self.load_notes_tree()
        # Можно автоматически выбрать новую запись если нужно
        # self._select_note_by_id(note_id)

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

    def _save_window_geometry(self):
        """Сохранение геометрии окна в config.json"""
        geometry = {
            "width": self.width(),
            "height": self.height(),
            "x": self.x(),
            "y": self.y()
        }
        self.config.set("window_geometry", geometry)

    def _restore_window_geometry(self):
        """Восстановление геометрии окна из config.json"""
        geometry = self.config.get("window_geometry")
        if geometry:
            self.resize(geometry.get("width", 1000), geometry.get("height", 600))
            x = geometry.get("x")
            y = geometry.get("y")
            if x is not None and y is not None:
                self.move(x, y)

    def _save_splitter_state(self, pos=None, index=None):
        """Сохранение позиции сплиттера"""
        self.config.set("splitter_sizes", self.splitter.sizes())

    def _restore_splitter_state(self):
        """Восстановление позиции сплиттера"""
        sizes = self.config.get("splitter_sizes")
        if sizes:
            self.splitter.setSizes(sizes)

    def _apply_font(self):
        """Применение настроек шрифта к редактору"""
        font_family = self.config.get("font_family", "Consolas")
        font_size = self.config.get("font_size", 11)
        font = QFont(font_family, font_size)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)

        # Обновление стиля документа для мгновенного применения
        doc = self.editor.document()
        doc.setDefaultFont(font)
        self.editor.setStyleSheet(
            f"QTextEdit {{ font-family: '{font_family}'; font-size: {font_size}pt; }}"
        )

        # Принудительное обновление размера шрифта во всем документе (без сброса других стилей)
        self._force_font_size(font_size)

    def _force_font_size(self, size):
        """Принудительно установить размер шрифта для всего содержимого"""
        cursor = self.editor.textCursor()
        if not cursor:
            return

        # Сохраняем позицию
        pos = cursor.position()

        # Выделяем все
        cursor.select(QTextCursor.Document)

        # Применяем только размер шрифта
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        cursor.mergeCharFormat(fmt)

        # Восстанавливаем позицию БЕЗ выделения
        cursor.clearSelection()
        cursor.setPosition(min(pos, len(self.editor.toPlainText())))
        self.editor.setTextCursor(cursor)

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

        focus_key = local_keys.get("toggle_focus", "F3")

        # Обновляем или создаем шорткат
        if self.toggle_focus_shortcut:
            self.toggle_focus_shortcut.setKey(QKeySequence(focus_key))
        else:
            self.toggle_focus_shortcut = QShortcut(QKeySequence(focus_key), self)
            self.toggle_focus_shortcut.activated.connect(self.toggle_focus)

        # F4 - добавить заметку
        add_note_key = local_keys.get("add_note", "F4")
        if getattr(self, 'add_note_shortcut', None):
            self.add_note_shortcut.setKey(QKeySequence(add_note_key))
        else:
            self.add_note_shortcut = QShortcut(QKeySequence(add_note_key), self)
            self.add_note_shortcut.activated.connect(self.add_note)

        del_note_key = local_keys.get("delete_note", "F8")
        if getattr(self, 'del_note_shortcut', None):
            self.del_note_shortcut.setKey(QKeySequence(del_note_key))
        else:
            self.del_note_shortcut = QShortcut(QKeySequence(del_note_key), self)
            self.del_note_shortcut.activated.connect(self.delete_notes)

        # Ctrl+, - открыть настройки
        # ПРИМЕЧАНИЕ: используем keyPressEvent для кроссплатформенной поддержки раскладок
        settings_key = local_keys.get("settings", "Ctrl+,")
        if getattr(self, 'settings_shortcut', None):
            self.settings_shortcut.setKey(QKeySequence(settings_key))
        else:
            self.settings_shortcut = QShortcut(QKeySequence(settings_key), self)
            self.settings_shortcut.activated.connect(self.open_settings)

        # Shift+Esc - выход (теперь настраиваемый)
        quit_key = local_keys.get("quit", "Shift+Esc")
        if getattr(self, 'quit_shortcut', None):
            self.quit_shortcut.setKey(QKeySequence(quit_key))
        else:
            self.quit_shortcut = QShortcut(QKeySequence(quit_key), self)
            self.quit_shortcut.activated.connect(self.quit_app)

        # Навигация по дереву, когда фокус в редакторе (Alt+стрелки по умолчанию)
        nav_up_key = local_keys.get("navigate_up", "Alt+Up")
        nav_down_key = local_keys.get("navigate_down", "Alt+Down")
        nav_left_key = local_keys.get("navigate_left", "Alt+Left")
        nav_right_key = local_keys.get("navigate_right", "Alt+Right")

        if getattr(self, 'nav_up_shortcut', None):
            self.nav_up_shortcut.setKey(QKeySequence(nav_up_key))
        else:
            self.nav_up_shortcut = QShortcut(QKeySequence(nav_up_key), self)
            self.nav_up_shortcut.activated.connect(lambda: self._navigate_tree_from_editor('up'))

        if getattr(self, 'nav_down_shortcut', None):
            self.nav_down_shortcut.setKey(QKeySequence(nav_down_key))
        else:
            self.nav_down_shortcut = QShortcut(QKeySequence(nav_down_key), self)
            self.nav_down_shortcut.activated.connect(lambda: self._navigate_tree_from_editor('down'))

        if getattr(self, 'nav_left_shortcut', None):
            self.nav_left_shortcut.setKey(QKeySequence(nav_left_key))
        else:
            self.nav_left_shortcut = QShortcut(QKeySequence(nav_left_key), self)
            self.nav_left_shortcut.activated.connect(lambda: self._navigate_tree_from_editor('left'))

        if getattr(self, 'nav_right_shortcut', None):
            self.nav_right_shortcut.setKey(QKeySequence(nav_right_key))
        else:
            self.nav_right_shortcut = QShortcut(QKeySequence(nav_right_key), self)
            self.nav_right_shortcut.activated.connect(lambda: self._navigate_tree_from_editor('right'))
        
        # Alt+S - переключение между последними записями "Текущие" <-> "Буфер обмена"
        # ПРИМЕЧАНИЕ: локальный шорткат удален, логика перенесена в on_global_show_hotkey

    def _set_tree_current_item(self, item: QTreeWidgetItem | None):
        if item is None:
            return
        self.tree_notes.setCurrentItem(item)
        self.tree_notes.scrollToItem(item)

    def _navigate_tree_from_editor(self, direction: str):
        """Навигация по дереву, не забирая фокус у редактора."""
        # Требование: работает только когда фокус в заметке.
        if not self.editor.hasFocus():
            return

        current = self.tree_notes.currentItem()
        if current is None:
            first = self.tree_notes.topLevelItem(0)
            self._set_tree_current_item(first)
            return

        if direction == 'up':
            self._set_tree_current_item(self.tree_notes.itemAbove(current))
            return

        if direction == 'down':
            self._set_tree_current_item(self.tree_notes.itemBelow(current))
            return

        if direction == 'left':
            if current.isExpanded():
                current.setExpanded(False)
            else:
                self._set_tree_current_item(current.parent())
            return

        if direction == 'right':
            if current.childCount() <= 0:
                return
            if not current.isExpanded():
                current.setExpanded(True)
            else:
                self._set_tree_current_item(current.child(0))
            return

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
    
    def toggle_current_clipboard_branch(self):
        """Переключение между последними записями в 'Текущие' и 'Буфер обмена'."""
        # Сохраняем текущую заметку перед переключением
        self.save_current_note()
        
        # Определяем текущую ветку
        current_item = self.tree_notes.currentItem()
        current_branch = self._get_root_branch_name(current_item)
        
        # Если текущая ветка "Текущие", переходим в "Буфер обмена" и наоборот
        if current_branch == "Текущие":
            target_branch = "Буфер обмена"
        else:
            target_branch = "Текущие"
        
        # Находим последнюю запись в целевой ветке
        target_root = self.repo.get_note_by_title(target_branch)
        if not target_root:
            # Создаем корневую ветку если не существует
            target_root_id = self.repo.create_note(None, target_branch)
            self.load_notes_tree()
            self._select_note_by_id(target_root_id)
        else:
            target_root_id = target_root[0]
            last_note = self.repo.get_last_descendant(target_root_id)
            
            if last_note:
                last_note_id = last_note[0]
                # Раскрываем путь к последней записи и выбираем её
                self._expand_path_to_note(last_note_id)
                self._select_note_by_id(last_note_id)
            else:
                # Если нет записей в целевой ветке, выбираем саму ветку
                self._select_note_by_id(target_root_id)
        
        # Сохраняем последнюю активную ветку
        self._last_active_branch = target_branch
        
        # Устанавливаем фокус в редактор
        self.editor.setFocus()
    
    def _get_root_branch_name(self, item: QTreeWidgetItem | None) -> str:
        """Получить имя корневой ветки для указанного элемента."""
        if not item:
            return "Текущие"  # По умолчанию
        
        # Поднимаемся до корневого элемента
        current = item
        while current.parent() is not None:
            current = current.parent()
        
        return current.text(0)

    def _find_item_by_id(self, note_id: int):
        iterator = QTreeWidgetItemIterator(self.tree_notes)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) == note_id:
                return item
            iterator += 1
        return None

    def _save_editor_content(self, note_id: int, title: str | None = None):
        """Сохранение содержимого редактора в указанную заметку.

        Важно: note_id должен соответствовать тому, что сейчас загружено в редактор.
        """
        if not note_id:
            return

        html = self.editor.toHtml()
        cursor_pos = self.editor.textCursor().position()

        if title is None:
            # Берем title максимально надежно
            item = self._find_item_by_id(note_id)
            if item is not None:
                title = item.text(0)
            else:
                row = self.repo.get_note(note_id)
                title = row[2] if row else ""

        self.repo.save_note(note_id, title, html, cursor_pos)

    def add_note(self):
        """Добавление новой заметки с автоматическим именованием"""
        self.save_current_note()

        current_root = self.repo.get_note_by_title("Текущие")
        if not current_root:
            current_root_id = self.repo.create_note(None, "Текущие")
        else:
            current_root_id = current_root[0]

        date_str = datetime.now().strftime("%y.%m.%d")
        date_note = self.repo.get_note_by_title(date_str, current_root_id)
        if not date_note:
            date_note_id = self.repo.create_note(current_root_id, date_str)
        else:
            date_note_id = date_note[0]

        time_str = datetime.now().strftime("%H:%M:%S")
        new_note_id = self.repo.create_note(date_note_id, time_str)

        self.load_notes_tree()
        self._select_note_by_id(new_note_id)

        # Немедленно ставим фокус в редактор
        self.editor.setFocus()

    def delete_notes(self):
        """Удаление выбранных заметок"""
        selected_items = self.tree_notes.selectedItems()
        if not selected_items:
            return

        reply = QMessageBox.question(
            self,
            "Удаление заметок",
            f"Удалить {len(selected_items)} заметок?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # Если среди удаляемых есть текущая заметка, сперва сохраняем
            if self.current_note_id:
                for item in selected_items:
                    if item.data(0, Qt.UserRole) == self.current_note_id:
                        self.save_current_note()
                        break

            for item in selected_items:
                note_id = item.data(0, Qt.UserRole)
                if note_id:
                    self.repo.delete_note(note_id)

            self.current_note_id = None
            self.editor.set_current_note_id(None)
            self.editor.blockSignals(True)
            self.editor.clear()
            self.editor.blockSignals(False)

            self.load_notes_tree()

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

        # Принудительно применяем шрифт при перезагрузке
        font_size = self.config.get("font_size", 11)
        self._force_font_size(font_size)

        # Восстановление курсора
        cursor = self.editor.textCursor()
        cursor.setPosition(min(cursor_pos, len(self.editor.toPlainText())))
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()

        self.editor.blockSignals(False)

    def _select_note_by_id(self, note_id):
        """Выбрать заметку по ID в дереве"""
        iterator = QTreeWidgetItemIterator(self.tree_notes)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) == note_id:
                self.tree_notes.setCurrentItem(item)
                break
            iterator += 1

    def _expand_path_to_note(self, note_id: int):
        """Раскрыть только те элементы дерева, которые ведут к указанной заметке"""
        # Получаем путь от корня до заметки
        path_ids = []
        current_id = note_id
        
        # Строим путь снизу вверх
        while current_id is not None:
            note_data = self.repo.get_note(current_id)
            if not note_data:
                break
            path_ids.append(current_id)
            current_id = note_data[1]  # parent_id
        
        # Раскрываем элементы по пути (кроме самой заметки)
        for path_id in path_ids[1:]:  # Пропускаем саму заметку
            item = self._find_item_by_id(path_id)
            if item:
                item.setExpanded(True)

    def load_notes_tree(self):
        """Загрузка дерева заметок из БД"""
        self._is_reloading_tree = True
        self.tree_notes.blockSignals(True)

        try:
            # Сохраняем состояние раскрытия
            expanded_ids = set()
            iterator = QTreeWidgetItemIterator(self.tree_notes)
            while iterator.value():
                item = iterator.value()
                if item.isExpanded():
                    expanded_ids.add(item.data(0, Qt.UserRole))
                iterator += 1

            current_selected_id = None
            cur_item = self.tree_notes.currentItem()
            if cur_item is not None:
                current_selected_id = cur_item.data(0, Qt.UserRole)

            self.tree_notes.clear()
            notes = self.repo.get_all_notes()

            # 1) создаем все item'ы
            items_map: dict[int, QTreeWidgetItem] = {}
            for note_id, parent_id, title, body_html, cursor_pos, updated_at in notes:
                item = QTreeWidgetItem([title])
                item.setData(0, Qt.UserRole, note_id)
                items_map[note_id] = item

            # 2) собираем иерархию (порядок в БД теперь не важен)
            root_items = []
            for note_id, parent_id, title, body_html, cursor_pos, updated_at in notes:
                item = items_map[note_id]
                if parent_id is None or parent_id not in items_map:
                    root_items.append(item)
                else:
                    items_map[parent_id].addChild(item)

            self.tree_notes.addTopLevelItems(root_items)

            # Восстанавливаем состояние раскрытия или раскрываем всё если пусто
            if not expanded_ids:
                # При первой загрузке дерево свернуто полностью
                # Раскрытие только до last_opened_note_id произойдет в _restore_last_state
                pass
            else:
                iterator = QTreeWidgetItemIterator(self.tree_notes)
                while iterator.value():
                    item = iterator.value()
                    if item.data(0, Qt.UserRole) in expanded_ids:
                        item.setExpanded(True)
                    iterator += 1

            # Восстанавливаем выделение (если было)
            if current_selected_id:
                item = items_map.get(current_selected_id)
                if item is not None:
                    self.tree_notes.setCurrentItem(item)

        finally:
            self.tree_notes.blockSignals(False)
            self._is_reloading_tree = False

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
            return

        note_id = current_item.data(0, Qt.UserRole)

        self._is_switching_note = True
        try:
            self.current_note_id = note_id
            self.editor.set_current_note_id(note_id)

            # Сохраняем ID открытой заметки
            self.repo.set_state("last_opened_note_id", note_id)

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
            # Тогда QTextDocument строил layout с placeholder-иконками,
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

            # Применяем шрифт ко всему содержимому при открытии
            font_size = self.config.get("font_size", 11)
            self._force_font_size(font_size)

            # Восстановление курсора
            if cursor_pos is not None:
                cursor = self.editor.textCursor()
                cursor.setPosition(min(cursor_pos, len(self.editor.toPlainText())))
                self.editor.setTextCursor(cursor)
                self.editor.ensureCursorVisible()

            self.editor.blockSignals(False)

        finally:
            self._is_switching_note = False

    def save_current_note(self):
        """Сохранение текущей заметки"""
        if not self.current_note_id:
            return

        # Сохраняем только если редактор действительно привязан к этой заметке
        if self.editor.current_note_id != self.current_note_id:
            return

        item = self.tree_notes.currentItem()
        title = None
        if item is not None and item.data(0, Qt.UserRole) == self.current_note_id:
            title = item.text(0)

        self._save_editor_content(self.current_note_id, title)

    def _on_editor_focus_out(self):
        """Ключевое событие: редактор теряет фокус."""
        if self._is_switching_note:
            return
        self.save_current_note()

    def _restore_last_state(self):
        """Восстановление последней открытой заметки"""
        last_id_str = self.repo.get_state("last_opened_note_id")
        if last_id_str:
            try:
                last_id = int(last_id_str)
                # Раскрываем только путь к этой заметке
                self._expand_path_to_note(last_id)
                self._select_note_by_id(last_id)
                if self.tree_notes.currentItem():
                    self.tree_notes.setFocus()
            except ValueError:
                pass

        # Если ничего не выбрали, выбираем первую
        if not self.tree_notes.currentItem():
            iter = QTreeWidgetItemIterator(self.tree_notes)
            if iter.value():
                self.tree_notes.setCurrentItem(iter.value())

    def on_global_show_hotkey(self):
        """Обработчик глобального Alt+S: показать окно или переключить ветки"""
        if self.isVisible() and self.isActiveWindow():
            # Окно уже активно - переключаем между Текущие/Буфер обмена
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
        if sys.platform == 'win32':
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
        if sys.platform == 'win32':
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
