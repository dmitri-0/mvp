from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMessageBox


class NoteActionMixin:
    """Mixin: действия над заметками (добавление, удаление)."""

    def add_note(self):
        """Добавление новой заметки. В ветке 'Буфер обмена' копирует содержимое текущей."""
        self.save_current_note()

        # 1. Запоминаем контент текущей заметки, если мы в ветке "Буфер обмена"
        content_to_copy = None
        current_item = self.tree_notes.currentItem()
        
        # Получаем имя текущей ветки. Метод должен быть доступен в MainWindow (из TreeNavigationMixin)
        if current_item and hasattr(self, '_get_root_branch_name'):
            branch = self._get_root_branch_name(current_item)
            if branch == "Буфер обмена" and self.current_note_id:
                # Берем контент из редактора, т.к. только что сохранили и он актуален
                # Используем toHtml, чтобы сохранить форматирование
                content_to_copy = self.editor.toHtml()

        # 2. Стандартная логика создания (поиск ветки "Текущие" и создание там)
        # ВАЖНО: По требованию "Находимся ветке Буфер обмена... Нажатие F4 создает новую заметку..."
        # Обычно add_note создает в "Текущие".
        # Если мы в Буфере обмена, создаем ли мы заметку в Буфере или в Текущих?
        # "Нажатие F4 создает новую заметку..."
        # Логика ниже создает ВСЕГДА в "Текущие" -> "Дата" -> "Время".
        # Если нужно создавать в текущей ветке (Буфер обмена), нужно менять логику.
        # Но в ТЗ не сказано менять место создания, сказано "вставляет в нее сразу все содержимое".
        # Оставим создание в "Текущие" как было, но с контентом.
        
        current_root = self.repo.get_note_by_title("Текущие")
        if not current_root:
            current_root_id = self.repo.create_note(None, "Текущие")
        else:
            current_root_id = current_root[0]

        date_str = datetime.now().strftime("%y.%m.%d")
        date_note = self.repo.get_note_by_title(date_str, current_root_id)
        if not date_note:
            date_note_id = self.repo.create_note(current_root_id, date_str)
        else:
            date_note_id = date_note[0]

        time_str = datetime.now().strftime("%H:%M:%S")
        # Создаем пустую заметку
        new_note_id = self.repo.create_note(date_note_id, time_str)

        # 3. Если нужно скопировать контент, обновляем созданную заметку
        if content_to_copy:
            self.repo.update_note(new_note_id, body=content_to_copy)

        self.load_notes_tree()
        self._select_note_by_id(new_note_id)

        # Немедленно ставим фокус в редактор
        self.editor.setFocus()

    def delete_notes(self):
        """Удаление выбранных заметок с возвратом фокуса в ту же ветку"""
        selected_items = self.tree_notes.selectedItems()
        if not selected_items:
            return

        reply = QMessageBox.question(
            self,
            "Удаление заметок",
            f"Удалить {len(selected_items)} заметок?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # КЛЮЧЕВОЙ МОМЕНТ: запоминаем корневую ветку ПЕРЕД удалением
            current_item = self.tree_notes.currentItem()
            source_branch = self._get_root_branch_name(current_item)

            # Если среди удаляемых есть текущая заметка, сперва сохраняем
            if self.current_note_id:
                for item in selected_items:
                    if item.data(0, Qt.UserRole) == self.current_note_id:
                        self.save_current_note()
                        break

            for item in selected_items:
                note_id = item.data(0, Qt.UserRole)
                if note_id:
                    self.repo.delete_note(note_id)

            self.current_note_id = None
            self.editor.set_current_note_id(None)
            self.editor.blockSignals(True)
            self.editor.clear()
            self.editor.blockSignals(False)

            self.load_notes_tree()

            # Автоматическое сжатие базы после удаления (тихо, без сообщений)
            try:
                self.repo.vacuum()
            except Exception as e:
                print(f"Error compacting db: {e}")

            # ЛОГИКА ВОЗВРАТА: после перезагрузки дерева возвращаемся в ту же ветку
            # и отправляем Alt+S (через метод toggle_current_clipboard_branch)
            QTimer.singleShot(100, lambda: self._restore_focus_after_delete(source_branch))

    def _restore_focus_after_delete(self, source_branch: str):
        """Вспомогательный метод: восстановить фокус и выполнить Alt+S после удаления"""
        # Определяем текущую ветку после перезагрузки
        current_item = self.tree_notes.currentItem()
        current_branch = self._get_root_branch_name(current_item)

        # Если мы не в исходной ветке, переключаемся туда
        if current_branch != source_branch:
            self.toggle_current_clipboard_branch()
        else:
            # Уже в нужной ветке - просто устанавливаем фокус в редактор
            self.editor.setFocus()

        # Теперь выполняем логику Alt+S:
        # Находим последнюю запись в текущей ветке и встаём на неё
        root_note = self.repo.get_note_by_title(source_branch)
        if root_note:
            root_id = root_note[0]
            last_note = self.repo.get_last_descendant(root_id)
            if last_note:
                last_note_id = last_note[0]
                self._expand_path_to_note(last_note_id)
                self._select_note_by_id(last_note_id)
