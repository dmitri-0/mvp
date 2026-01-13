import re
import traceback

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
            # Отображаем ошибку прямо в окне предпросмотра для отладки
            err_msg = f"<div style='color:red; font-weight:bold;'>Error generating snippets:<br>{e}<br><pre>{traceback.format_exc()}</pre></div><hr>"
            self.preview.setHtml(err_msg + body_html)
            print(f"Error generating snippets: {e}")

    def _generate_snippets(self, html: str, query: str) -> str:
        """Создает HTML со списком фрагментов. Показывает контекст вокруг совпадения."""
        doc = QTextDocument()
        doc.setHtml(html)

        escaped_query = re.escape(query)
        regex = QRegularExpression(escaped_query, QRegularExpression.CaseInsensitiveOption)

        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("yellow"))
        highlight_fmt.setForeground(Qt.black)

        match_positions = []
        
        # 1. Находим все вхождения последовательно
        cursor = QTextCursor(doc)
        cursor.setPosition(0)
        
        while True:
            # Поиск следующего вхождения начиная с текущей позиции курсора
            cursor = doc.find(regex, cursor)
            
            if cursor.isNull():
                break
                
            # Подсвечиваем найденное
            cursor.mergeCharFormat(highlight_fmt)
            
            # Сохраняем позиции
            match_positions.append((cursor.selectionStart(), cursor.selectionEnd()))

        if not match_positions:
            return (
                "<div style='color:#888; font-size:12px; margin:0 0 10px 0; border-bottom:1px solid #ddd; padding-bottom:5px;'>"
                "Найдено совпадений: 0 (показан полный текст)"
                "</div>" + html
            )

        # 2. Формируем список фрагментов без объединения
        CONTEXT_LEN = 60
        doc_len = max(0, doc.characterCount() - 1)
        
        found_fragments = []
        
        for start, end in match_positions:
            frag_start = max(0, start - CONTEXT_LEN)
            frag_end = min(doc_len, end + CONTEXT_LEN)
            
            extract_cursor = QTextCursor(doc)
            extract_cursor.setPosition(frag_start)
            if frag_end > frag_start:
                extract_cursor.setPosition(frag_end, QTextCursor.KeepAnchor)
            
            fragment = extract_cursor.selection().toHtml()
            fragment = self._clean_qt_html(fragment)
            
            found_fragments.append(f"<div style='margin: 10px 0; border-left: 2px solid #ddd; padding-left: 10px;'>{fragment}</div>")

        debug_info = (
            "<div style='color:#888; font-size:12px; margin:0 0 10px 0; border-bottom:1px solid #ddd; padding-bottom:5px;'>"
            f"Найдено совпадений: {len(match_positions)}"
            "</div>"
        )

        return debug_info + "<hr style='border: 0; border-top: 1px solid #eee; margin: 10px 0;'>".join(found_fragments)

    def _clean_qt_html(self, html_fragment):
        """Убирает обертки HTML/BODY из фрагмента, возвращаемого toHtml()"""
        # Сначала ищем body
        match = re.search(r"<body[^>]*>(.*)</body>", html_fragment, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Если body не найдено, пробуем вырезать html теги, если они есть
        match_html = re.search(r"<html[^>]*>(.*)</html>", html_fragment, re.DOTALL | re.IGNORECASE)
        if match_html:
            # Внутри html может быть head и body, но если мы здесь, значит body regex не сработал
            # Вернем содержимое html
            return match_html.group(1)

        return html_fragment

    def _on_search_enter(self):
        """Перенос фокуса в список при нажатии Enter в строке поиска."""
        if self.list.count() > 0:
            self.list.setFocus()
            if not self.list.currentItem():
                self.list.setCurrentRow(0)
