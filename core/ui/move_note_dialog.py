from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton, QHBoxLayout, QLabel


class MoveNoteDialog(QDialog):
    """Диалог выбора родительской заметки для перемещения"""

    def __init__(self, repo, current_note_ids, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_note_ids = current_note_ids
        self.selected_parent_id = None

        self.setWindowTitle("Переместить заметку")
        self.resize(400, 500)

        # Основной layout
        layout = QVBoxLayout()

        # Информационный текст
        if len(current_note_ids) == 1:
            info_label = QLabel("Выберите новый родитель для заметки:")
        else:
            info_label = QLabel(f"Выберите новый родитель для {len(current_note_ids)} заметок:")
        layout.addWidget(info_label)

        # Дерево заметок для выбора
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Заметки")
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        # Кнопки
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Загрузка дерева
        self._load_tree()

    def _load_tree(self):
        """Загрузка дерева заметок (без перемещаемых заметок и их потомков)"""
        notes = self.repo.get_all_notes()

        # Создаем множество ID заметок, которые нельзя выбрать
        # (сами перемещаемые заметки + их потомки)
        excluded_ids = set(self.current_note_ids)
        
        # Находим всех потомков перемещаемых заметок
        def add_descendants(parent_id):
            for note_id, p_id, _, _, _, _ in notes:
                if p_id == parent_id and note_id not in excluded_ids:
                    excluded_ids.add(note_id)
                    add_descendants(note_id)
        
        for note_id in self.current_note_ids:
            add_descendants(note_id)

        # Создаем все item'ы (только те, которые не исключены)
        items_map = {}
        for note_id, parent_id, title, _, _, _ in notes:
            if note_id not in excluded_ids:
                item = QTreeWidgetItem([title])
                item.setData(0, Qt.UserRole, note_id)
                items_map[note_id] = item

        # Собираем иерархию
        root_items = []
        for note_id, parent_id, title, _, _, _ in notes:
            if note_id in excluded_ids:
                continue
            
            item = items_map[note_id]
            if parent_id is None or parent_id not in items_map:
                if title != 'Буфер обмена':
                    root_items.append(item)
            else:
                items_map[parent_id].addChild(item)

        self.tree.addTopLevelItems(root_items)
        
        # Раскрываем корневые элементы
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setExpanded(True)

    def _on_item_double_clicked(self, item, column):
        """Обработчик двойного клика - принять выбор"""
        self.accept()

    def accept(self):
        """Сохранить выбранный родитель и закрыть диалог"""
        current_item = self.tree.currentItem()
        if current_item:
            self.selected_parent_id = current_item.data(0, Qt.UserRole)
        super().accept()

    def keyPressEvent(self, event):
        """Обработка навигации курсором и Enter"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.accept()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
