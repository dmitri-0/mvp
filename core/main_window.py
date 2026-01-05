# core/main_window.py
from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextDocument, QKeySequence, QShortcut, QImage
from PySide6.QtWidgets import (
    QMainWindow, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QSplitter,
    QApplication, QDialog, QVBoxLayout, QLabel, QSpinBox,
    QLineEdit, QPushButton, QFormLayout, QMessageBox
)
from core.note_editor import NoteEditor
from core.repository import NoteRepository
from core.config import Config


class SettingsDialog(QDialog):
    """Диалог настроек приложения"""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.resize(400, 200)

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

        # Кнопки
        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)

        btn_layout = QVBoxLayout()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)

        layout.addRow("", btn_layout)
        self.setLayout(layout)

    def save_settings(self):
        """Сохранение настроек"""
        self.config.set("database_path", self.db_path_edit.text())
        self.config.set("font_family", self.font_family_edit.text())
        self.config.set("font_size", self.font_size_spin.value())

        QMessageBox.information(
            self,
            "Настройки",
            "Настройки сохранены. Перезапустите приложение для применения изменений.",
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

        # Левая панель - дерево заметок
        self.tree_notes = QTreeWidget()
        self.tree_notes.setHeaderLabel("Notes")
        self.tree_notes.currentItemChanged.connect(self.on_note_selected)
        self.tree_notes.setSelectionMode(QTreeWidget.ExtendedSelection)

        # Правая панель - редактор
        self.editor = NoteEditor()
        self.editor.setAcceptRichText(True)
        self.editor.set_context(self.repo, lambda: self.current_note_id)

        # Применение моноширинного шрифта
        font_family = config.get("font_family", "Consolas")
        font_size = config.get("font_size", 11)
        font = QFont(font_family, font_size)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tree_notes)
        splitter.addWidget(self.editor)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        self.setCentralWidget(splitter)

        # Автосохранение с debounce
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_current_note)
        self.editor.textChanged.connect(lambda: self._save_timer.start(500))

        self.current_note_id = None
        self.focused_widget = self.tree_notes  # Отслеживание фокуса

        # Шорткаты
        self._setup_shortcuts()

        self.load_notes_tree()

    def _setup_shortcuts(self):
        """Настройка горячих клавиш"""
        # Alt+S - переключение между деревом и редактором
        toggle_shortcut = QShortcut(QKeySequence("Alt+S"), self)
        toggle_shortcut.activated.connect(self.toggle_focus)

        # F4 - добавить заметку
        add_shortcut = QShortcut(QKeySequence("F4"), self)
        add_shortcut.activated.connect(self.add_note)

        # F8 - удалить заметки
        del_shortcut = QShortcut(QKeySequence("F8"), self)
        del_shortcut.activated.connect(self.delete_notes)

        # Ctrl+, - открыть настройки
        settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        settings_shortcut.activated.connect(self.open_settings)

    def toggle_focus(self):
        """Переключение фокуса между деревом и редактором"""
        if self.tree_notes.hasFocus():
            self.editor.setFocus()
            self.focused_widget = self.editor
        else:
            self.tree_notes.setFocus()
            self.focused_widget = self.tree_notes

    def add_note(self):
        """Добавление новой заметки с автоматическим именованием"""
        # Получаем корневую заметку "Текущие"
        current_root = self.repo.get_note_by_title("Текущие")
        if not current_root:
            current_root_id = self.repo.create_note(None, "Текущие")
        else:
            current_root_id = current_root[0]

        # Получаем или создаем заметку с текущей датой
        date_str = datetime.now().strftime("%y.%m.%d")
        date_note = self.repo.get_note_by_title(date_str, current_root_id)
        if not date_note:
            date_note_id = self.repo.create_note(current_root_id, date_str)
        else:
            date_note_id = date_note[0]

        # Создаем заметку с текущим временем
        time_str = datetime.now().strftime("%H:%M:%S")
        new_note_id = self.repo.create_note(date_note_id, time_str)

        # Обновляем дерево
        self.load_notes_tree()
        self._select_note_by_id(new_note_id)

    def delete_notes(self):
        """Удаление выбранных заметок"""
        selected_items = self.tree_notes.selectedItems()
        if not selected_items:
            return

        # Подтверждение удаления
        reply = QMessageBox.question(
            self,
            "Удаление заметок",
            f"Удалить {len(selected_items)} заметок?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            for item in selected_items:
                note_id = item.data(0, Qt.UserRole)
                if note_id:
                    self.repo.delete_note(note_id)

            self.current_note_id = None
            self.load_notes_tree()

    def open_settings(self):
        """Открытие окна настроек"""
        dialog = SettingsDialog(self.config, self)
        dialog.exec()

        # Применение новых настроек шрифта
        font_family = self.config.get("font_family", "Consolas")
        font_size = self.config.get("font_size", 11)
        font = QFont(font_family, font_size)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)

    def _select_note_by_id(self, note_id):
        """Выбрать заметку по ID в дереве"""
        iterator = QTreeWidgetItemIterator(self.tree_notes)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) == note_id:
                self.tree_notes.setCurrentItem(item)
                break
            iterator += 1

    def load_notes_tree(self):
        """Загрузка дерева заметок из БД"""
        self.tree_notes.clear()
        notes = self.repo.get_all_notes()

        # Построение дерева
        items_map = {}
        root_items = []

        for note_id, parent_id, title, body_html, updated_at in notes:
            item = QTreeWidgetItem([title])
            item.setData(0, Qt.UserRole, note_id)
            items_map[note_id] = item

            if parent_id is None:
                root_items.append(item)
            else:
                if parent_id in items_map:
                    items_map[parent_id].addChild(item)
                else:
                    root_items.append(item)

        self.tree_notes.addTopLevelItems(root_items)
        self.tree_notes.expandAll()

        # Выбрать первую заметку
        if root_items:
            self.tree_notes.setCurrentItem(root_items[0])

    def on_note_selected(self, current_item, previous_item):
        """Переключение на другую заметку"""
        if previous_item and self.current_note_id:
            self.save_current_note()

        if not current_item:
            return

        note_id = current_item.data(0, Qt.UserRole)
        self.current_note_id = note_id

        # Загрузить содержимое заметки
        notes = self.repo.get_all_notes()
        for nid, _, title, body_html, _ in notes:
            if nid == note_id:
                self.editor.blockSignals(True)
                self.editor.setHtml(body_html or "")

                # Загрузить картинки в ресурсы документа
                attachments = self.repo.get_attachments(note_id)
                for att_id, name, img_bytes, mime in attachments:
                    if img_bytes:
                        image = QImage.fromData(img_bytes)
                        self.editor.document().addResource(
                            QTextDocument.ImageResource,
                            f"noteimg://{att_id}",
                            image,
                        )

                self.editor.blockSignals(False)
                break

    def save_current_note(self):
        """Сохранение текущей заметки"""
        if not self.current_note_id:
            return

        html = self.editor.toHtml()
        current_item = self.tree_notes.currentItem()
        if current_item:
            title = current_item.text(0)
            self.repo.save_note(self.current_note_id, title, html)

    def show_and_focus(self):
        """Показать и активировать окно"""
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self):
        """Скрыть в трей"""
        self.hide()

    def quit_app(self):
        """Выход из приложения"""
        if self.current_note_id:
            self.save_current_note()
        QApplication.instance().quit()

    def keyPressEvent(self, event):
        """Обработка нажатий клавиш"""
        if event.key() == Qt.Key_Escape:
            self.hide_to_tray()
            event.accept()
        else:
            super().keyPressEvent(event)
