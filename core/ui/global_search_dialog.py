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
        self.preview.document().setDefaultStyleSheet("""
            img { max-width: 100%; height: auto; }
        """)
        
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
        try:
            snippets_html = self._generate_snippets(body_html, query)
            self.preview.setHtml(snippets_html)
        except Exception as e:
            print(f"Error generating snippets: {e}")
            self.preview.setHtml(body_html)

    def _generate_snippets(self, html: str, query: str) -> str:
        """Создает HTML со списком фрагментов. Показывает 300 символов до и после совпадения."""
        doc = QTextDocument()
        doc.setHtml(html)
        
        # 1. Подсветка всех совпадений (желтый фон)
        escaped_query = re.escape(query)
        regex = QRegularExpression(escaped_query, QRegularExpression.CaseInsensitiveOption)
        
        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("yellow"))
        highlight_fmt.setForeground(Qt.black)
        
        match_positions = []
        pos = 0
        
        # Более надежный цикл поиска с использованием целочисленной позиции
        while True:
            # Ищем, начиная с позиции pos
            cursor = doc.find(regex, pos)
            
            if cursor.isNull():
                break
                
            # Проверка, чтобы избежать бесконечного цикла, если найдено совпадение нулевой длины (хотя с обычным текстом маловероятно)
            if cursor.selectionEnd() <= pos:
                pos += 1
                continue
                
            cursor.mergeCharFormat(highlight_fmt)
            match_positions.append((cursor.selectionStart(), cursor.selectionEnd()))
            
            # Следующий поиск начинаем сразу после конца текущего совпадения
            pos = cursor.selectionEnd()

        if not match_positions:
            return html

        # 2. Формирование сниппетов (300 символов до и после)
        CONTEXT_LEN = 300
        doc_len = max(0, doc.characterCount() - 1) 
        
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
            # Двойная проверка границ перед созданием курсора
            safe_start = max(0, min(rng_start, doc_len))
            safe_end = max(safe_start, min(rng_end, doc_len))
            
            cursor = QTextCursor(doc)
            cursor.setPosition(safe_start)
            if safe_end > safe_start:
                cursor.setPosition(safe_end, QTextCursor.KeepAnchor)
            
            fragment = cursor.selection().toHtml()
            fragment = self._clean_qt_html(fragment)
            
            snippet_html = f"<div style='margin: 10px 0;'>{fragment}</div>"
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
