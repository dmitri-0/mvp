import re

from PySide6.QtCore import Qt, QTimer, QRegularExpression
from PySide6.QtGui import QTextDocument, QTextCursor, QTextCharFormat, QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QSplitter,
)

from core.note_editor import NoteEditor


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

        # Превью (правая часть) - используем NoteEditor для поддержки картинок
        self.preview = NoteEditor()
        self.preview.setReadOnly(True)
        self.preview.set_context(self.repo)
        
        # CSS для автоматического масштабирования картинок под ширину окна
        self.preview.document().setDefaultStyleSheet("img { max-width: 100%; height: auto; }")
        
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
        
        body_html = current.data(Qt.UserRole + 1) or ""
        # Важно: устанавливаем ID заметки, чтобы NoteEditor мог загружать картинки
        note_id = current.data(Qt.UserRole)
        self.preview.set_current_note_id(note_id)
        
        query = self.edit.text().strip()
        
        if not query:
            self.preview.setHtml(body_html)
            return

        # Генерация сниппетов (отрывков с искомым текстом)
        snippets_html = self._generate_snippets(body_html, query)
        self.preview.setHtml(snippets_html)

    def _generate_snippets(self, html: str, query: str) -> str:
        """Создает HTML со списком фрагментов. Показывает 300 символов до и после совпадения."""
        doc = QTextDocument()
        doc.setHtml(html)
        
        # 1. Подсветка всех совпадений (желтый фон)
        escaped_query = re.escape(query)
        regex = QRegularExpression(escaped_query, QRegularExpression.CaseInsensitiveOption)
        
        highlight_cursor = doc.find(regex)
        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("yellow"))
        highlight_fmt.setForeground(Qt.black)
        
        # Список позиций всех совпадений
        match_positions = []

        while not highlight_cursor.isNull():
            highlight_cursor.mergeCharFormat(highlight_fmt)
            # Сохраняем позицию начала и конца совпадения
            match_positions.append((highlight_cursor.selectionStart(), highlight_cursor.selectionEnd()))
            highlight_cursor = doc.find(regex, highlight_cursor)

        if not match_positions:
            return html

        # 2. Формирование сниппетов (300 символов до и после)
        snippets = []
        CONTEXT_LEN = 300
        doc_len = doc.characterCount()
        
        # Чтобы не дублировать пересекающиеся области, будем следить за последней обработанной позицией
        last_end_pos = -1

        for start_pos, end_pos in match_positions:
            # Если это совпадение уже попало в предыдущий сниппет, пропускаем или объединяем?
            # Лучше объединять, если они близко.
            
            # Определяем границы контекста
            snippet_start = max(0, start_pos - CONTEXT_LEN)
            snippet_end = min(doc_len, end_pos + CONTEXT_LEN)
            
            # Если начало текущего сниппета перекрывается с концом предыдущего (или очень близко)
            # То просто расширяем предыдущий сниппет
            if snippets and snippet_start <= last_end_pos:
                # Получаем последний добавленный фрагмент и его границы (нужно хранить)
                # Упростим: просто создадим новый курсор от (последний end) до (текущий end)
                # Но это сложно склеить.
                
                # Проще: перезаписать последний сниппет, расширив его.
                # Но у нас уже HTML текст в списке.
                
                # Давайте хранить список диапазонов (start, end) для сниппетов, объединять их, а потом генерировать HTML.
                pass
            else:
                # Это новый сниппет? пока просто соберем диапазоны
                pass
        
        # 2.1 Объединение диапазонов
        merged_ranges = []
        for start_pos, end_pos in match_positions:
            rng_start = max(0, start_pos - CONTEXT_LEN)
            rng_end = min(doc_len, end_pos + CONTEXT_LEN)
            
            if not merged_ranges:
                merged_ranges.append([rng_start, rng_end])
            else:
                last_rng = merged_ranges[-1]
                # Если текущий диапазон пересекается с последним или идет сразу за ним
                if rng_start <= last_rng[1]:
                    last_rng[1] = max(last_rng[1], rng_end)
                else:
                    merged_ranges.append([rng_start, rng_end])
        
        # 2.2 Генерация HTML для каждого диапазона
        found_fragments = []
        
        for rng_start, rng_end in merged_ranges:
            cursor = QTextCursor(doc)
            cursor.setPosition(rng_start)
            cursor.setPosition(rng_end, QTextCursor.KeepAnchor)
            
            fragment = cursor.selection().toHtml()
            fragment = self._clean_qt_html(fragment)
            
            snippet_html = (
                f"<div style='color: #888; font-size: 0.9em; text-align: center;'>...</div>"
                f"<div style='margin: 10px 0;'>{fragment}</div>"
                f"<div style='color: #888; font-size: 0.9em; text-align: center;'>...</div>"
            )
            found_fragments.append(snippet_html)
            
        return "<hr style='border: 0; border-top: 2px solid #ccc; margin: 20px 0;'>".join(found_fragments)

    def _clean_qt_html(self, html_fragment):
        """Убирает обертки HTML/BODY из фрагмента, возвращаемого toHtml()"""
        match = re.search(r"<body[^>]*>(.*)</body>", html_fragment, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
        return html_fragment

    def _on_search_enter(self):
        """Перенос фокуса в список при нажатии Enter в строке поиска."""
        if self.list.count() > 0:
            self.list.setFocus()
            if not self.list.currentItem():
                self.list.setCurrentRow(0)
