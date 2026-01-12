from datetime import datetime
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStatusBar,
    QPushButton,
    QWidget,
    QStyle
)
from PySide6.QtCore import Qt

class HistoryDialog(QDialog):
    """Окно истории недавно измененных заметок"""
    
    def __init__(self, repo, main_window, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.main_window = main_window
        self.setWindowTitle("История изменений")
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Список заметок
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_item_changed)
        self.list_widget.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self.list_widget)
        
        # Строка состояния
        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        layout.addWidget(self.status_bar)
        
        # Кнопка очистки в статус баре справа
        self.clear_btn = QPushButton("🗑") # Используем символ Unicode вместо иконки для лучшей видимости
        self.clear_btn.setToolTip("Очистить историю")
        self.clear_btn.setFlat(True)
        self.clear_btn.setFixedSize(30, 24)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_history)
        
        # Добавляем кнопку как постоянный виджет (справа)
        self.status_bar.addPermanentWidget(self.clear_btn)
        
        self.load_history()
        
    def load_history(self):
        self.list_widget.clear()
        # Получаем 50 последних измененных
        notes = self.repo.get_recently_updated_notes(50)
        
        for note in notes:
            # note: (id, title, updated_at)
            nid, title, updated_at = note
            
            # Форматируем дату
            try:
                # updated_at is iso format string
                display_time = str(updated_at)[:16].replace('T', ' ')
            except Exception:
                display_time = str(updated_at)
                
            item_text = f"[{display_time}] {title}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, nid)
            self.list_widget.addItem(item)
            
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self.list_widget.setFocus() # Устанавливаем фокус на список
    
    def clear_history(self):
        """Очистить историю"""
        self.repo.clear_history()
        self.load_history() # Перезагрузить список (будет пустым)
            
    def _on_item_changed(self, current, previous):
        if not current:
            self.status_bar.clearMessage()
            return
            
        note_id = current.data(Qt.UserRole)
        # Показываем путь в строке состояния
        path = self.repo.get_note_path(note_id)
        if path:
            self.status_bar.showMessage(path)
        else:
            self.status_bar.clearMessage()
            
    def _on_item_activated(self, item):
        note_id = item.data(Qt.UserRole)
        # Переходим к заметке в главном окне
        self.main_window._select_note_by_id(note_id)
        self.accept()
