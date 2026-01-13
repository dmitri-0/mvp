from datetime import datetime
import re
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMessageBox, QInputDialog


class NoteActionMixin:
    """Миксин: действия над заметками (добавление, удаление, перемещение)"""

    def _clone_attachments_and_rewrite_html(self, source_note_ids, target_note_id, html: str) -> str:
        """Клонировать вложения (attachments) из исходных заметок в целевую и переписать ссылки noteimg://.

        Это нужно для сценария: F4 (копия из ветки "Буфер обмена" в "Текущие") без "битых" картинок
        после удаления заметок из "Буфера".
        """
        if not html or not source_note_ids or not target_note_id:
            return html

        id_map = {}

        # Копируем ВСЕ вложения из исходных заметок в новую заметку
        for src_note_id in source_note_ids:
            if not src_note_id:
                continue
            try:
                attachments = self.repo.get_attachments(src_note_id)
            except Exception:
                attachments = []

            for att_id, name, img_bytes, mime in attachments:
                if not img_bytes:
                    continue

                safe_name = name or "image.png"
                safe_mime = mime or "image/png"
                new_att_id = self.repo.add_attachment(target_note_id, safe_name, img_bytes, safe_mime)
                id_map[int(att_id)] = int(new_att_id)

        if not id_map:
            return html

        def _repl(match):
            old_id = int(match.group(1))
            new_id = id_map.get(old_id)
            return f"noteimg://{new_id}" if new_id else match.group(0)

        return re.sub(r"noteimg://(\d+)", _repl, html)

    def add_note(self):
        """Добавление новой заметки. 
        В ветке 'Буфер обмена' копирует содержимое текущей заметки (или всех выделенных).
        """
        self.save_current_note()

        content_to_copy = ""
        source_note_ids = []

        current_item = self.tree_notes.currentItem()

        # Получаем список выделенных элементов
        selected_items = self.tree_notes.selectedItems()

        # Проверяем, находимся ли мы в ветке "Буфер обмена"
        # Достаточно проверить ветку текущего (фокусного) элемента
        if current_item and hasattr(self, "_get_root_branch_name"):
            branch = self._get_root_branch_name(current_item)
            if branch == "Буфер обмена":
                # Если выделено несколько заметок -> собираем контент со всех
                if len(selected_items) > 1:
                    contents = []

                    for item in selected_items:
                        note_id = item.data(0, Qt.UserRole)
                        if not note_id:
                            continue

                        # Если это текущая открытая заметка - берем из редактора (там свежее)
                        if note_id == self.current_note_id:
                            html = self.editor.toHtml()
                        else:
                            # Иначе читаем из базы
                            row = self.repo.get_note(note_id)
                            html = row[3] if row and row[3] else ""

                        if html:
                            contents.append(html)
                            source_note_ids.append(note_id)

                    # Объединяем контент. Просто склеиваем HTML.
                    # Можно добавить разделитель <hr> между заметками
                    content_to_copy = "<hr>".join(contents)

                # Если выделена только одна (или фокус на одной без selection)
                elif self.current_note_id:
                    content_to_copy = self.editor.toHtml()
                    source_note_ids = [self.current_note_id]

        # 2. Стандартная логика создания (поиск ветки "Текущие" и создание там)
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
            # ВАЖНО: при копировании из "Буфера обмена" нужно продублировать вложения,
            # иначе после удаления исходной заметки изображения станут "битыми".
            content_to_copy = self._clone_attachments_and_rewrite_html(source_note_ids, new_note_id, content_to_copy)
            self.repo.save_note(new_note_id, time_str, content_to_copy)

        self.load_notes_tree()
        self._select_note_by_id(new_note_id)

        # Немедленно ставим фокус в редактор
        self.editor.setFocus()

    def add_to_favorites(self):
        """Добавление текущей заметки в Избранное (F5)"""
        if not self.current_note_id:
            return

        # Сохраняем текущую заметку перед копированием
        self.save_current_note()

        # Получаем содержимое текущей заметки
        row = self.repo.get_note(self.current_note_id)
        if not row:
            return

        _, _, title, body_html, _, _ = row

        # Находим или создаем корневую ветку "Избранное"
        favorites_root = self.repo.get_note_by_title("Избранное")
        if not favorites_root:
            favorites_root_id = self.repo.create_note(None, "Избранное")
        else:
            favorites_root_id = favorites_root[0]

        # Создаем заметку в Избранном с тем же заголовком
        new_note_id = self.repo.create_note(favorites_root_id, title)

        # Копируем содержимое
        if body_html:
            self.repo.save_note(new_note_id, title, body_html)

        # Перезагружаем дерево чтобы показать новую заметку
        self.load_notes_tree()

        # Показываем уведомление
        QMessageBox.information(self, "Избранное", f"Заметка '{title}' добавлена в Избранное")

    def rename_note(self):
        """Переименование текущей заметки (F2). Корневые заметки не переименовываются."""
        current_item = self.tree_notes.currentItem()
        if not current_item:
            return

        note_id = current_item.data(0, Qt.UserRole)
        if not note_id:
            return

        # Получаем данные заметки
        row = self.repo.get_note(note_id)
        if not row:
            return

        _, parent_id, old_title, _, _, _ = row

        # Проверяем, что это не корневая заметка
        if parent_id is None:
            QMessageBox.warning(self, "Переименование", "Корневые ветки нельзя переименовывать")
            return

        # Диалог для ввода нового имени
        new_title, ok = QInputDialog.getText(self, "Переименование заметки", "Новое название:", text=old_title)

        if ok and new_title and new_title != old_title:
            # Сохраняем изменения
            if note_id == self.current_note_id:
                # Если это текущая открытая заметка, берем контент из редактора
                body_html = self.editor.toHtml()
                cursor_pos = self.editor.textCursor().position()
                self.repo.save_note(note_id, new_title, body_html, cursor_pos)
            else:
                # Иначе просто обновляем title
                cursor_pos = row[4]
                body_html = row[3]
                self.repo.save_note(note_id, new_title, body_html, cursor_pos)

            # Обновляем отображение в дереве
            current_item.setText(0, new_title)

    def move_notes(self):
        """Перемещение заметок (F6) - только внутри веток Избранное и Текущие"""
        selected_items = self.tree_notes.selectedItems()
        if not selected_items:
            return

        # Проверяем, что все выбранные заметки находятся в "Избранное" или "Текущие"
        allowed_branches = {"Избранное", "Текущие"}
        note_ids = []

        for item in selected_items:
            note_id = item.data(0, Qt.UserRole)
            if not note_id:
                continue

            # Проверяем корневую ветку
            branch = self.repo.get_root_branch_name(note_id)
            if branch not in allowed_branches:
                QMessageBox.warning(
                    self,
                    "Перемещение",
                    f'Перемещение доступно только для заметок в ветках "Избранное" и "Текущие".',
                )
                return

            # Проверяем, что это не корневая заметка
            row = self.repo.get_note(note_id)
            if row and row[1] is None:  # parent_id is None
                QMessageBox.warning(self, "Перемещение", "Корневые ветки нельзя перемещать")
                return

            note_ids.append(note_id)

        if not note_ids:
            return

        # Сохраняем текущую заметку перед перемещением
        self.save_current_note()

        # Открываем диалог выбора родителя
        from core.ui.move_note_dialog import MoveNoteDialog

        dialog = MoveNoteDialog(self.repo, note_ids, self)

        if dialog.exec() and dialog.selected_parent_id is not None:
            # Перемещаем все выбранные заметки
            for note_id in note_ids:
                self.repo.move_note(note_id, dialog.selected_parent_id)

            # Обновляем дерево
            self.load_notes_tree()

            # Выбираем первую перемещенную заметку
            if note_ids:
                self._expand_path_to_note(note_ids[0])
                self._select_note_by_id(note_ids[0])

    def delete_notes(self):
        """Удаление выбранных заметок с возвратом фокуса в ту же ветку"""
        selected_items = self.tree_notes.selectedItems()
        if not selected_items:
            return

        reply = QMessageBox.question(
            self, "Удаление заметок", f"Удалить {len(selected_items)} заметок?", QMessageBox.Yes | QMessageBox.No
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
