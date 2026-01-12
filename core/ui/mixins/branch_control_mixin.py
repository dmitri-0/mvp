class BranchControlMixin:
    """Mixin: управление ветками (Текущие / Буфер обмена)."""

    def toggle_current_clipboard_branch(self):
        """Переключение между последними записями в 'Текущие' и 'Буфер обмена'."""
        # Сохраняем текущую заметку перед переключением
        self.save_current_note()

        # Определяем текущую ветку
        current_item = self.tree_notes.currentItem()
        current_branch = self._get_root_branch_name(current_item)

        # Если текущая ветка "Текущие", переходим в "Буфер обмена" и наоборот
        if current_branch == "Текущие":
            target_branch = "Буфер обмена"
        else:
            target_branch = "Текущие"

        # Находим последнюю запись в целевой ветке
        target_root = self.repo.get_note_by_title(target_branch)
        if not target_root:
            # Создаем корневую ветку если не существует
            target_root_id = self.repo.create_note(None, target_branch)
            self.load_notes_tree()
            self._select_note_by_id(target_root_id)
        else:
            target_root_id = target_root[0]
            last_note = self.repo.get_last_descendant(target_root_id)

            if last_note:
                last_note_id = last_note[0]
                # Раскрываем путь к последней записи и выбираем её
                self._expand_path_to_note(last_note_id)
                self._select_note_by_id(last_note_id)
            else:
                # Если нет записей в целевой ветке, выбираем саму ветку
                self._select_note_by_id(target_root_id)

        # Сохраняем последнюю активную ветку
        self._last_active_branch = target_branch

        # Устанавливаем фокус в редактор
        self.editor.setFocus()
