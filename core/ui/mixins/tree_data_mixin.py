from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QTreeWidgetItem, QTreeWidgetItemIterator


class TreeDataMixin:
    """Mixin: загрузка дерева заметок и восстановление состояния."""

    def load_notes_tree(self):
        """Загрузка дерева заметок из БД"""
        self._is_reloading_tree = True
        self.tree_notes.blockSignals(True)

        try:
            # Сохраняем состояние раскрытия
            expanded_ids = set()
            iterator = QTreeWidgetItemIterator(self.tree_notes)
            while iterator.value():
                item = iterator.value()
                if item.isExpanded():
                    expanded_ids.add(item.data(0, Qt.UserRole))
                iterator += 1

            current_selected_id = None
            cur_item = self.tree_notes.currentItem()
            if cur_item is not None:
                current_selected_id = cur_item.data(0, Qt.UserRole)

            self.tree_notes.clear()
            notes = self.repo.get_all_notes()

            # 1) создаем все item'ы
            items_map: dict[int, QTreeWidgetItem] = {}
            for note_id, parent_id, title, body_html, cursor_pos, updated_at in notes:
                item = QTreeWidgetItem([title])
                item.setData(0, Qt.UserRole, note_id)
                items_map[note_id] = item

            # 2) собираем иерархию (порядок в БД теперь не важен)
            root_items = []
            for note_id, parent_id, title, body_html, cursor_pos, updated_at in notes:
                item = items_map[note_id]
                if parent_id is None or parent_id not in items_map:
                    root_items.append(item)
                else:
                    items_map[parent_id].addChild(item)

            self.tree_notes.addTopLevelItems(root_items)

            # Восстанавливаем состояние раскрытия или раскрываем всё если пусто
            if not expanded_ids:
                # При первой загрузке дерево свернуто полностью
                # Раскрытие только до last_opened_note_id произойдет в _restore_last_state
                pass
            else:
                iterator = QTreeWidgetItemIterator(self.tree_notes)
                while iterator.value():
                    item = iterator.value()
                    if item.data(0, Qt.UserRole) in expanded_ids:
                        item.setExpanded(True)
                    iterator += 1

            # Восстанавливаем выделение (если было)
            if current_selected_id:
                item = items_map.get(current_selected_id)
                if item is not None:
                    self.tree_notes.setCurrentItem(item)

        finally:
            self.tree_notes.blockSignals(False)
            self._is_reloading_tree = False

    def _restore_last_state(self):
        """Восстановление последней открытой заметки"""
        last_id_str = self.repo.get_state("last_opened_note_id")
        if last_id_str:
            try:
                last_id = int(last_id_str)
                # Раскрываем только путь к этой заметке
                self._expand_path_to_note(last_id)
                self._select_note_by_id(last_id)
                if self.tree_notes.currentItem():
                    self.tree_notes.setFocus()
            except ValueError:
                pass

        # Если ничего не выбрали, выбираем первую
        if not self.tree_notes.currentItem():
            it = QTreeWidgetItemIterator(self.tree_notes)
            if it.value():
                self.tree_notes.setCurrentItem(it.value())
