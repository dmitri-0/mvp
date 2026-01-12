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
        
        # Убираем inline-стили, чтобы тема применялась корректно
        # self.editor.setStyleSheet(
        #     f"QTextEdit {{ font-family: '{font_family}'; font-size: {font_size}pt; }}"
        # )

        # Принудительное обновление шрифта во всем документе
        self._enforce_global_font()

    def _enforce_global_font(self):
        """Принудительно установить глобальный шрифт и размер для всего содержимого"""
        font_family = self.config.get("font_family", "Consolas")
        font_size = self.config.get("font_size", 11)

        cursor = self.editor.textCursor()
        if not cursor:
            return

        # Сохраняем позицию
        pos = cursor.position()

        # Выделяем все
        cursor.select(QTextCursor.Document)

        # Применяем шрифт и размер
        fmt = QTextCharFormat()
        fmt.setFontFamily(font_family)
        fmt.setFontPointSize(font_size)
        cursor.mergeCharFormat(fmt)

        # Восстанавливаем позицию БЕЗ выделения
        cursor.clearSelection()
        doc_len = len(self.editor.toPlainText())
        cursor.setPosition(min(pos, doc_len))
        self.editor.setTextCursor(cursor)
