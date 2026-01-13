import html
import re
import traceback
import unicodedata

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextDocument, QPalette, QColor
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

    def showEvent(self, event):
        # При каждом показе применяем текущую тему (в приложении она переключается динамически)
        super().showEvent(event)
        self._apply_theme()

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
        top.addWidget(self.stats_lbl)

        root.addLayout(top)

        # Разделитель с результатами и превью
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # Результаты (левая часть)
        self.list = QListWidget()
        self.list.itemActivated.connect(self._open_selected)
        self.list.currentItemChanged.connect(self._on_current_changed)
        # В некоторых стилях/темах длинные строки могут переноситься "по буквам".
        # Явно отключаем переносы и включаем элипсис.
        self.list.setWordWrap(False)
        self.list.setTextElideMode(Qt.ElideRight)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        splitter.addWidget(self.list)

        # Превью (правая часть) - используем NoteEditor для поддержки картинок
        self.preview = NoteEditor()
        self.preview.setReadOnly(True)
        self.preview.set_context(self.repo)
        splitter.addWidget(self.preview)

        splitter.setSizes([350, 650])

        self.hint_lbl = QLabel("Enter/двойной клик — открыть заметку, Esc — закрыть")
        root.addWidget(self.hint_lbl)

        self.edit.setFocus()

        self._apply_theme()

    def _apply_theme(self):
        """Привязка цветов/HTML к текущей палитре (поддержка тёмной темы)."""
        pal = self.palette()

        # "Приглушённый" цвет текста (для подсказок/статуса)
        placeholder_role = getattr(QPalette.ColorRole, "PlaceholderText", QPalette.ColorRole.Text)
        muted = pal.color(placeholder_role)

        self.stats_lbl.setStyleSheet(f"color: {muted.name(QColor.HexRgb)}; margin-left: 10px;")
        self.hint_lbl.setStyleSheet(f"color: {muted.name(QColor.HexRgb)};")

        # Базовые цвета для HTML предпросмотра
        text = pal.color(QPalette.ColorRole.Text).name(QColor.HexRgb)
        base = pal.color(QPalette.ColorRole.Base).name(QColor.HexRgb)
        link = pal.color(QPalette.ColorRole.Link).name(QColor.HexRgb)

        # Важно: setDefaultStyleSheet задаёт CSS по умолчанию для HTML в QTextDocument.
        # Если его не задать, QTextEdit в тёмной теме может остаться с чёрным текстом по умолчанию.
        # Убираем отступы у параграфов для более компактного вида
        self.preview.document().setDefaultStyleSheet(
            "\n".join(
                [
                    f"body {{ color: {text}; background-color: {base}; margin: 0; padding: 0; }}",
                    f"a {{ color: {link}; }}",
                    "p { margin: 0; padding: 0; }",
                    "img { max-width: 100%; height: auto; }",
                ]
            )
        )

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
            text = path

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, note_id)
            item.setData(Qt.UserRole + 1, body_html)
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
        self.preview.set_current_note_id(note_id)

        query = self.edit.text().strip()
        body_html = ""
        try:
            row = self.repo.get_note(int(note_id)) if note_id else None
            if row:
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

    def _generate_snippets(self, html_content: str, query: str) -> str:
        """
        ВАРИАНТ A: Работаем с plain text.
        Извлекаем текст, ищем совпадения, вырезаем фрагменты и оборачиваем в HTML сами.
        """
        # 1. Получаем чистый текст из HTML с помощью QTextDocument (он хорошо убирает теги)
        doc = QTextDocument()
        doc.setHtml(html_content)
        plain = doc.toPlainText() or ""

        # Нормализация для поиска
        plain_norm = unicodedata.normalize("NFC", plain.replace("\u00a0", " "))
        query_norm = unicodedata.normalize("NFC", (query or "").replace("\u00a0", " "))

        if not query_norm:
            return html_content

        pattern = re.escape(query_norm)
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # Если запрос некорректен как регулярка (маловероятно после escape), возвращаем оригинал
            return html_content

        match_positions = []
        for m in rx.finditer(plain_norm):
            match_positions.append((m.start(), m.end()))

        pal = self.preview.palette()
        placeholder_role = getattr(QPalette.ColorRole, "PlaceholderText", QPalette.ColorRole.Text)
        muted = pal.color(placeholder_role).name(QColor.HexRgb)
        border = pal.color(QPalette.ColorRole.Mid).name(QColor.HexRgb)
        card_bg = pal.color(QPalette.ColorRole.AlternateBase).name(QColor.HexRgb)
        window_bg = pal.color(QPalette.ColorRole.Window).lightness()
        is_dark = window_bg < 128

        match_bg = "#ffd54f" if is_dark else "#ffeb3b"
        match_fg = "#000000"
        highlight_style = f"background-color: {match_bg}; color: {match_fg}; font-weight: bold;"

        # Если ничего не нашли в тексте (может быть в тегах, но мы ищем по контенту)
        if not match_positions:
            return (
                f"<div style='color:{muted}; font-size:12px; margin:0 0 10px 0; "
                f"border-bottom:1px solid {border}; padding-bottom:5px;'>"
                "Найдено совпадений: 0 (показан полный текст)"
                "</div>" + html_content
            )

        # 2. Формируем HTML список фрагментов
        CONTEXT_LEN = 60
        text_len = len(plain)

        found_fragments = []

        for i, (start, end) in enumerate(match_positions):
            # Определяем границы фрагмента
            frag_start = max(0, start - CONTEXT_LEN)
            frag_end = min(text_len, end + CONTEXT_LEN)

            # Вырезаем части текста
            prefix = plain[frag_start:start]
            match_text = plain[start:end]
            suffix = plain[end:frag_end]

            # Собираем HTML, ОБЯЗАТЕЛЬНО экранируя текст
            safe_prefix = html.escape(prefix)
            safe_match = html.escape(match_text)
            safe_suffix = html.escape(suffix)

            # Добавляем многоточия, если обрезали
            if frag_start > 0:
                safe_prefix = "..." + safe_prefix
            if frag_end < text_len:
                safe_suffix = safe_suffix + "..."

            snippet_html = (
                f"{safe_prefix}"
                f"<span style='{highlight_style}'>{safe_match}</span>"
                f"{safe_suffix}"
            )

            # Заменяем переносы строк на <br>, чтобы в браузере выглядело как текст
            snippet_html = snippet_html.replace("\n", "<br>")

            # Разделитель между фрагментами (вместо "Фрагмент #")
            divider_html = ""
            if i > 0:
                # margin: 0; padding: 0; - убираем отступы вокруг черты
                divider_html = f"<hr style='border: 0; border-top: 1px solid {border}; margin: 0; padding: 0;'>"

            # Оборачиваем в блок (цвета берём из текущей палитры, чтобы работало в тёмной теме)
            # padding: 5px 10px; - уменьшаем вертикальный padding внутри блока
            found_fragments.append(
                divider_html
                + f"<div style='padding: 5px 10px; background: {card_bg}; font-family: sans-serif;'>"
                + f"<div style='font-size: 13px; line-height: 1.2;'>{snippet_html}</div>"
                + "</div>"
            )

        header = (
            f"<div style='color:{muted}; font-size:12px; margin:0 0 5px 0; "
            f"border-bottom:1px solid {border}; padding-bottom:5px;'>"
            f"Найдено совпадений: {len(match_positions)}"
            "</div>"
        )

        return header + "".join(found_fragments)

    def _on_search_enter(self):
        """Перенос фокуса в список при нажатии Enter в строке поиска."""
        if self.list.count() > 0:
            self.list.setFocus()
            if not self.list.currentItem():
                self.list.setCurrentRow(0)
