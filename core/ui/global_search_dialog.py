import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QSplitter,
    QTextBrowser,
)


class GlobalSearchDialog(QDialog):
    """Диалог глобального поиска по базе (заголовок + тело)."""

    def __init__(self, repo, parent=None, on_open_note=None):
        super().__init__(parent)
        self.repo = repo
        self.on_open_note = on_open_note
        self.setWindowTitle("Глобальный поиск")
        self.resize(1000, 600)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._run_search)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Верхняя строка поиска
        top = QHBoxLayout()
        lbl = QLabel("Найти:")
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Введите текст для поиска по заголовку и телу...")
        self.edit.textChanged.connect(self._schedule_search)
        self.edit.returnPressed.connect(self._on_search_enter)
        top.addWidget(lbl)
        top.addWidget(self.edit, 1)
        root.addLayout(top)

        # Разделитель с результатами и превью
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # Результаты (левая часть)
        self.list = QListWidget()
        self.list.itemActivated.connect(self._open_selected)
        self.list.currentItemChanged.connect(self._on_current_changed)
        splitter.addWidget(self.list)

        # Превью (правая часть)
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        splitter.addWidget(self.preview)

        splitter.setSizes([350, 650])

        hint = QLabel("Enter/двойной клик — открыть заметку, Esc — закрыть")
        hint.setStyleSheet("color: #777;")
        root.addWidget(hint)

        self.edit.setFocus()

    def _schedule_search(self):
        self._debounce_timer.start(150)

    def _run_search(self):
        q = (self.edit.text() or "").strip()
        self.list.clear()
        self.preview.clear()

        if not q:
            return

        rows = self.repo.search_notes(q, limit=200)
        for note_id, title, body_html, updated_at in rows:
            path = self.repo.get_note_path(note_id) or title

            # Только путь, без сниппета
            text = path
            
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, note_id)
            item.setData(Qt.UserRole + 1, body_html)  # Сохраняем тело для превью
            self.list.addItem(item)

    def _open_selected(self, item: QListWidgetItem):
        note_id = item.data(Qt.UserRole)
        if self.on_open_note and note_id:
            self.on_open_note(int(note_id))
        self.accept()

    def _on_current_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        if not current:
            self.preview.clear()
            return
        
        body_html = current.data(Qt.UserRole + 1)
        self.preview.setHtml(body_html or "")

    def _on_search_enter(self):
        """Перенос фокуса в список при нажатии Enter в строке поиска."""
        if self.list.count() > 0:
            self.list.setFocus()
            if not self.list.currentItem():
                self.list.setCurrentRow(0)
