import re
import traceback
import unicodedata

from PySide6.QtCore import Qt, QTimer
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

        # Метка количества найденных
        self.stats_lbl = QLabel("")
        self.stats_lbl.setStyleSheet("color: #666; margin-left: 10px;")
        top.addWidget(self.stats_lbl)

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
        self.stats_lbl.clear()

        if not q:
            return

        rows = self.repo.search_notes(q, limit=200)
        self.stats_lbl.setText(f"Найдено: {len(rows)}")

        for note_id, title, body_html, updated_at in rows:
            path = self.repo.get_note_path(note_id) or title

            # Только путь, без сниппета
            text = path

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, note_id)
            item.setData(Qt.UserRole + 1, body_html)  # Сохраняем тело (может быть неактуально)
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

        note_id = current.data(Qt.UserRole)
        # Важно: устанавливаем ID заметки, чтобы NoteEditor мог загружать картинки
        self.preview.set_current_note_id(note_id)

        query = self.edit.text().strip()

        # Двухступенчатый подход:
        # 1) поиск по базе -> список (уже сделан в _run_search)
        # 2) при выборе заметки заново грузим полный текст заметки и ищем в нем ВСЕ вхождения
        body_html = ""
        try:
            row = self.repo.get_note(int(note_id)) if note_id else None
            if row:
                # (id, parent_id, title, body_html, cursor_position, updated_at)
                body_html = row[3] or ""
            else:
                body_html = current.data(Qt.UserRole + 1) or ""
        except Exception:
            body_html = current.data(Qt.UserRole + 1) or ""

        if not query:
            self.preview.setHtml(body_html)
            return

        try:
            snippets_html = self._generate_snippets(body_html, query)
            self.preview.setHtml(snippets_html)
        except Exception as e:
            err_msg = (
                "<div style='color:red; font-weight:bold;'>Error generating snippets:<br>"
                f"{e}<br><pre>{traceback.format_exc()}</pre></div><hr>"
            )
            self.preview.setHtml(err_msg + body_html)

    def _generate_snippets(self, html: str, query: str) -> str:
        """Создает HTML со списком фрагментов. Сначала точно находит все вхождения, потом выводит."""
        doc = QTextDocument()
        doc.setHtml(html)

        # 1) Четко находим все вхождения по ПЛОСКОМУ тексту
        plain = doc.toPlainText() or ""

        # Нормализация (NFC) и замена NBSP для надежного поиска
        plain_norm = unicodedata.normalize("NFC", plain.replace("\u00a0", " "))
        query_norm = unicodedata.normalize("NFC", (query or "").replace("\u00a0", " "))

        if not query_norm:
             return html

        pattern = re.escape(query_norm)
        rx = re.compile(pattern, re.IGNORECASE)

        match_positions = []
        for m in rx.finditer(plain_norm):
            match_positions.append((m.start(), m.end()))

        if not match_positions:
            return (
                "<div style='color:#888; font-size:12px; margin:0 0 10px 0; border-bottom:1px solid #ddd; padding-bottom:5px;'>"
                "Найдено совпадений: 0 (показан полный текст)"
                "</div>" + html
            )

        # 2) Подсвечиваем в документе (по тем же позициям)
        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("yellow"))
        highlight_fmt.setForeground(Qt.black)

        # Важно: применяем форматирование к документу
        for start, end in match_positions:
            c = QTextCursor(doc)
            c.setPosition(start)
            c.setPosition(end, QTextCursor.KeepAnchor)
            c.mergeCharFormat(highlight_fmt)

        # 3) Формируем список фрагментов
        CONTEXT_LEN = 60
        doc_len = max(0, doc.characterCount() - 1)

        found_fragments = []
        for i, (start, end) in enumerate(match_positions):
            frag_start = max(0, start - CONTEXT_LEN)
            frag_end = min(doc_len, end + CONTEXT_LEN)

            extract_cursor = QTextCursor(doc)
            extract_cursor.setPosition(frag_start)
            if frag_end > frag_start:
                extract_cursor.setPosition(frag_end, QTextCursor.KeepAnchor)

            # Получаем HTML фрагмента (с подсветкой)
            fragment_html = extract_cursor.selection().toHtml()
            cleaned_fragment = self._clean_qt_html(fragment_html)
            
            # Добавляем в список
            found_fragments.append(
                f"<div style='margin-bottom: 20px; padding: 10px; border: 1px solid #eee; background: #fafafa;'>"
                f"<div style='font-size: 10px; color: #999; margin-bottom: 5px;'>Фрагмент #{i+1}</div>"
                f"{cleaned_fragment}"
                f"</div>"
            )

        debug_info = (
            "<div style='color:#888; font-size:12px; margin:0 0 10px 0; border-bottom:1px solid #ddd; padding-bottom:5px;'>"
            f"Найдено совпадений: {len(match_positions)}"
            "</div>"
        )

        return debug_info + "".join(found_fragments)

    def _clean_qt_html(self, html_fragment):
        """Убирает обертки HTML/BODY из фрагмента, возвращаемого toHtml()"""
        # Попытка найти содержимое внутри body через строковые операции (надежнее regex)
        start_tag = "<body"
        end_tag = "</body>"
        
        lower_html = html_fragment.lower()
        body_start = lower_html.find(start_tag)
        
        if body_start != -1:
            # Находим закрывающую скобку тега body (например <body style='...'>)
            content_start = lower_html.find(">", body_start) + 1
            body_end = lower_html.rfind(end_tag)
            
            if body_end != -1 and content_start < body_end:
                return html_fragment[content_start:body_end]

        # Если body не найден, пробуем вернуть как есть или очистить от html тегов
        # (резервный вариант для простых фрагментов)
        return html_fragment

    def _on_search_enter(self):
        """Перенос фокуса в список при нажатии Enter в строке поиска."""
        if self.list.count() > 0:
            self.list.setFocus()
            if not self.list.currentItem():
                self.list.setCurrentRow(0)
