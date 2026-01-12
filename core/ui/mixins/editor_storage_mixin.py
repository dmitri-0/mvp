from PySide6.QtCore import Qt


class EditorStorageMixin:
    """Mixin: сохранение/восстановление содержимого редактора."""

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
