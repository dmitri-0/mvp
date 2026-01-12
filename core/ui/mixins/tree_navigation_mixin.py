from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem, QTreeWidgetItemIterator


class TreeNavigationMixin:
    """Mixin: вспомогательные методы работы с деревом заметок."""

    def _set_tree_current_item(self, item: QTreeWidgetItem | None):
        if item is None:
            return
        self.tree_notes.setCurrentItem(item)
        self.tree_notes.scrollToItem(item)

    def _navigate_tree_from_editor(self, direction: str):
        """Навигация по дереву, не забирая фокус у редактора."""
        # Требование: работает только когда фокус в заметке.
        if not self.editor.hasFocus():
            return

        current = self.tree_notes.currentItem()
        if current is None:
            first = self.tree_notes.topLevelItem(0)
            self._set_tree_current_item(first)
            return

        if direction == "up":
            self._set_tree_current_item(self.tree_notes.itemAbove(current))
            return

        if direction == "down":
            self._set_tree_current_item(self.tree_notes.itemBelow(current))
            return

        if direction == "page_up":
            # Эмуляция PageUp - смещение на 15 элементов вверх
            target = current
            for _ in range(15):
                prev = self.tree_notes.itemAbove(target)
                if not prev:
                    break
                target = prev
            self._set_tree_current_item(target)
            return

        if direction == "page_down":
            # Эмуляция PageDown - смещение на 15 элементов вниз
            target = current
            for _ in range(15):
                nxt = self.tree_notes.itemBelow(target)
                if not nxt:
                    break
                target = nxt
            self._set_tree_current_item(target)
            return

        if direction == "left":
            if current.isExpanded():
                current.setExpanded(False)
            else:
                self._set_tree_current_item(current.parent())
            return

        if direction == "right":
            if current.childCount() <= 0:
                return
            if not current.isExpanded():
                current.setExpanded(True)
            else:
                self._set_tree_current_item(current.child(0))
            return

    def _get_root_branch_name(self, item: QTreeWidgetItem | None) -> str:
        """Получить имя корневой ветки для указанного элемента."""
        if not item:
            return "Текущие"  # По умолчанию

        # Поднимаемся до корневого элемента
        current = item
        while current.parent() is not None:
            current = current.parent()

        return current.text(0)

    def _find_item_by_id(self, note_id: int):
        iterator = QTreeWidgetItemIterator(self.tree_notes)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) == note_id:
                return item
            iterator += 1
        return None

    def _select_note_by_id(self, note_id: int):
        """Выбрать заметку по ID в дереве"""
        iterator = QTreeWidgetItemIterator(self.tree_notes)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) == note_id:
                self.tree_notes.setCurrentItem(item)
                break
            iterator += 1

    def _expand_path_to_note(self, note_id: int):
        """Раскрыть только те элементы дерева, которые ведут к указанной заметке"""
        # Получаем путь от корня до заметки
        path_ids = []
        current_id = note_id

        # Строим путь снизу вверх
        while current_id is not None:
            note_data = self.repo.get_note(current_id)
            if not note_data:
                break
            path_ids.append(current_id)
            current_id = note_data[1]  # parent_id

        # Раскрываем элементы по пути (кроме самой заметки)
        for path_id in path_ids[1:]:  # Пропускаем саму заметку
            item = self._find_item_by_id(path_id)
            if item:
                item.setExpanded(True)
