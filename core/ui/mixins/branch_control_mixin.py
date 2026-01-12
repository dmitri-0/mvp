class BranchControlMixin:
    """Mixin: управление ветками (Текущие / Буфер обмена / Избранное)."""

    def toggle_current_clipboard_branch(self):
        """Переключение между ветками 'Текущие', 'Буфер обмена' и 'Избранное' с сохранением позиций."""
        # Ленивая инициализация словаря позиций, так как __init__ миксина не вызывается
        if not hasattr(self, '_branch_positions'):
            self._branch_positions = {}

        # Сохраняем текущую заметку перед переключением
        self.save_current_note()

        # Определяем текущую ветку и сохраняем позицию курсора
        current_item = self.tree_notes.currentItem()
        current_branch = self._get_root_branch_name(current_item)
        if current_branch and self.current_note_id:
            self._branch_positions[current_branch] = self.current_note_id

        # Определяем следующую ветку в цикле: Текущие -> Буфер обмена -> Избранное -> Текущие
        branch_cycle = ["Текущие", "Буфер обмена", "Избранное"]
        try:
            current_index = branch_cycle.index(current_branch) if current_branch in branch_cycle else -1
            target_branch = branch_cycle[(current_index + 1) % len(branch_cycle)]
        except (ValueError, IndexError):
            target_branch = "Текущие"  # Fallback

        # Получаем или создаем целевую ветку
        target_root = self.repo.get_note_by_title(target_branch)
        if not target_root:
            # Создаем корневую ветку если не существует
            target_root_id = self.repo.create_note(None, target_branch)
            self.load_notes_tree()
            self._select_note_by_id(target_root_id)
        else:
            target_root_id = target_root[0]
            
            # Проверяем, есть ли сохраненная позиция в этой ветке
            saved_note_id = self._branch_positions.get(target_branch)
            
            # Проверяем, существует ли сохраненная заметка
            note_exists = False
            if saved_note_id:
                note = self.repo.get_note(saved_note_id)
                # Дополнительно проверяем, что заметка действительно в этой ветке
                if note:
                    note_branch = self.repo.get_root_branch_name(saved_note_id)
                    if note_branch == target_branch:
                        note_exists = True
            
            if note_exists:
                # Возвращаемся на сохраненную позицию
                self._expand_path_to_note(saved_note_id)
                self._select_note_by_id(saved_note_id)
            else:
                # Если сохраненной позиции нет или заметка удалена, идем на последнюю запись
                last_note = self.repo.get_last_descendant(target_root_id)
                if last_note:
                    last_note_id = last_note[0]
                    self._expand_path_to_note(last_note_id)
                    self._select_note_by_id(last_note_id)
                else:
                    # Если нет записей в целевой ветке, выбираем саму ветку
                    self._select_note_by_id(target_root_id)

        # Сохраняем последнюю активную ветку
        self._last_active_branch = target_branch

        # Схлопываем все ветки кроме текущей
        self._collapse_all_except_current()

        # Устанавливаем фокус в редактор
        self.editor.setFocus()
