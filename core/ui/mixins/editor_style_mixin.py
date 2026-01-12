from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat


class EditorStyleMixin:
    """Mixin: оформление/шрифт редактора."""

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
