from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QToolButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QTextDocument, QTextCursor


class SearchWidget(QWidget):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.current_theme = "light"  # Default theme
        self.setup_ui()
        self.hide()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Кнопка закрытия
        self.btn_close = QToolButton()
        self.btn_close.setText("✕")
        self.btn_close.setToolTip("Закрыть поиск (Esc)")
        self.btn_close.clicked.connect(self.hide_search)
        self.btn_close.setStyleSheet("border: none; background: transparent; font-weight: bold;")
        layout.addWidget(self.btn_close)

        # Поле ввода
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Найти...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self.find_next)
        layout.addWidget(self.search_input)

        # Кнопка "Назад"
        self.btn_prev = QToolButton()
        self.btn_prev.setText("▲")
        self.btn_prev.setToolTip("Предыдущее совпадение (Shift+Enter)")
        self.btn_prev.clicked.connect(self.find_prev)
        layout.addWidget(self.btn_prev)

        # Кнопка "Вперед"
        self.btn_next = QToolButton()
        self.btn_next.setText("▼")
        self.btn_next.setToolTip("Следующее совпадение (Enter)")
        self.btn_next.clicked.connect(self.find_next)
        layout.addWidget(self.btn_next)

        # Применяем дефолтную тему
        self.update_theme("light")

        # Шорткат Esc для закрытия
        self.shortcut_esc = QShortcut(QKeySequence(Qt.Key_Escape), self.search_input)
        self.shortcut_esc.activated.connect(self.hide_search)

        # Shift+Enter для поиска назад (если фокус в поле ввода)
        self.shortcut_prev = QShortcut(QKeySequence("Shift+Return"), self.search_input)
        self.shortcut_prev.activated.connect(self.find_prev)

    def update_theme(self, theme_name):
        """Обновить стили виджета в зависимости от темы"""
        self.current_theme = theme_name
        
        if theme_name == "dark":
            # Темная тема
            self.setStyleSheet("""
                SearchWidget {
                    background-color: #252526;
                    border-bottom: 1px solid #3e3e42;
                }
                QToolButton {
                    color: #d4d4d4;
                    border: 1px solid transparent;
                    border-radius: 4px;
                    padding: 4px;
                    background: transparent;
                }
                QToolButton:hover {
                    background-color: #3e3e42;
                    border: 1px solid #505050;
                }
            """)
            self.search_input.setStyleSheet("""
                QLineEdit {
                    background-color: #3c3c3c;
                    color: #d4d4d4;
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
            # Кнопка закрытия должна быть видна
            self.btn_close.setStyleSheet("border: none; background: transparent; font-weight: bold; color: #d4d4d4;")
            
        else:
            # Светлая тема
            self.setStyleSheet("""
                SearchWidget {
                    background-color: #f5f5f5;
                    border-bottom: 1px solid #ddd;
                }
                QToolButton {
                    color: black;
                    border: 1px solid transparent;
                    border-radius: 4px;
                    padding: 4px;
                    background: transparent;
                }
                QToolButton:hover {
                    background-color: #e0e0e0;
                    border: 1px solid #ccc;
                }
            """)
            self.search_input.setStyleSheet("""
                QLineEdit {
                    background-color: white;
                    color: black;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
            self.btn_close.setStyleSheet("border: none; background: transparent; font-weight: bold; color: black;")

    def show_search(self):
        self.show()
        self.search_input.setFocus()
        self.search_input.selectAll()

        # Если в редакторе есть выделенный текст, копируем его в поле поиска
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            if selected_text:
                self.search_input.setText(selected_text)
                self.search_input.selectAll()

    def hide_search(self):
        self.hide()
        self.editor.setFocus()

    def find_next(self):
        text = self.search_input.text()
        if not text:
            return

        # Ищем вперед
        found = self.editor.find(text)

        # Если не нашли - пробуем с начала
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            found = self.editor.find(text)

        self._update_style(found)

    def find_prev(self):
        text = self.search_input.text()
        if not text:
            return

        # Ищем назад
        found = self.editor.find(text, QTextDocument.FindBackward)

        # Если не нашли - пробуем с конца
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.editor.setTextCursor(cursor)
            found = self.editor.find(text, QTextDocument.FindBackward)

        self._update_style(found)

    def _update_style(self, found):
        if found:
            # Восстанавливаем стандартный стиль для текущей темы
            if self.current_theme == "dark":
                self.search_input.setStyleSheet("""
                    QLineEdit {
                        background-color: #3c3c3c;
                        color: #d4d4d4;
                        border: 1px solid #3e3e42;
                        border-radius: 4px;
                        padding: 4px;
                    }
                """)
            else:
                self.search_input.setStyleSheet("""
                    QLineEdit {
                        background-color: white;
                        color: black;
                        border: 1px solid #ccc;
                        border-radius: 4px;
                        padding: 4px;
                    }
                """)
        else:
            # Стиль "Не найдено"
            if self.current_theme == "dark":
                self.search_input.setStyleSheet("""
                    QLineEdit {
                        background-color: #5a1d1d;
                        color: #d4d4d4;
                        border: 1px solid #be1100;
                        border-radius: 4px;
                        padding: 4px;
                    }
                """)
            else:
                self.search_input.setStyleSheet("""
                    QLineEdit {
                        background-color: #fff0f0;
                        color: black;
                        border: 1px solid #ff9999;
                        border-radius: 4px;
                        padding: 4px;
                    }
                """)
