"""Менеджер темы приложения"""
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt


class ThemeManager:
    """Управление темой (светлая/темная) для всего приложения"""
    
    DARK_STYLESHEET = """
    QMainWindow, QDialog, QWidget {
        background-color: #1e1e1e;
        color: #d4d4d4;
    }
    
    /* Исправление заголовка дерева заметок */
    QHeaderView::section {
        background-color: #252526;
        color: #cccccc;
        border: 1px solid #3e3e42;
        padding: 4px;
    }
    
    QTreeWidget {
        background-color: #252526;
        color: #cccccc;
        border: 1px solid #3e3e42;
        alternate-background-color: #2d2d30;
    }
    
    QTreeWidget::item:selected {
        background-color: #094771;
        color: #ffffff;
    }
    
    QTreeWidget::item:hover {
        background-color: #2a2d2e;
    }
    
    /* Ветки дерева - светлый фон для видимости стрелок */
    QTreeWidget::branch {
        background-color: #252526;
    }
    
    /* Треугольник вправо (закрыто) - CSS треугольник */
    QTreeWidget::branch:closed:has-children {
        border: none;
        background: transparent;
        margin: 4px;
    }
    
    QTreeWidget::branch:closed:has-children:has-siblings {
        border-left: 6px solid #e0e0e0;
        border-top: 4px solid transparent;
        border-bottom: 4px solid transparent;
        width: 0;
        height: 0;
    }
    
    /* Треугольник вниз (открыто) - CSS треугольник */
    QTreeWidget::branch:open:has-children {
        border: none;
        background: transparent;
        margin: 4px;
    }
    
    QTreeWidget::branch:open:has-children:has-siblings {
        border-top: 6px solid #e0e0e0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        width: 0;
        height: 0;
    }
    
    QTextEdit {
        background-color: #1e1e1e;
        color: #d4d4d4;
        border: 1px solid #3e3e42;
        selection-background-color: #264f78;
        selection-color: #ffffff;
    }
    
    QLineEdit, QSpinBox {
        background-color: #3c3c3c;
        color: #cccccc;
        border: 1px solid #3e3e42;
        padding: 4px;
    }
    
    QLineEdit:focus, QSpinBox:focus {
        border: 1px solid #007acc;
    }
    
    QPushButton {
        background-color: #0e639c;
        color: #ffffff;
        border: none;
        padding: 6px 12px;
        border-radius: 2px;
    }
    
    QPushButton:hover {
        background-color: #1177bb;
    }
    
    QPushButton:pressed {
        background-color: #094771;
    }
    
    QPushButton:disabled {
        background-color: #3e3e42;
        color: #656565;
    }
    
    QComboBox {
        background-color: #3c3c3c;
        color: #cccccc;
        border: 1px solid #3e3e42;
        padding: 4px;
    }
    
    QComboBox:hover {
        border: 1px solid #007acc;
    }
    
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    
    QComboBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 6px solid #cccccc;
        margin-right: 6px;
    }
    
    QComboBox QAbstractItemView {
        background-color: #252526;
        color: #cccccc;
        selection-background-color: #094771;
        border: 1px solid #3e3e42;
    }
    
    QLabel {
        color: #cccccc;
    }
    
    QStatusBar {
        background-color: #007acc;
        color: #ffffff;
    }
    
    QScrollBar:vertical {
        background-color: #1e1e1e;
        width: 14px;
        border: none;
    }
    
    QScrollBar::handle:vertical {
        background-color: #424242;
        min-height: 20px;
        border-radius: 4px;
        margin: 2px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #4e4e4e;
    }
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    
    QScrollBar:horizontal {
        background-color: #1e1e1e;
        height: 14px;
        border: none;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #424242;
        min-width: 20px;
        border-radius: 4px;
        margin: 2px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #4e4e4e;
    }
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    
    QSplitter::handle {
        background-color: #3e3e42;
    }
    
    QSplitter::handle:hover {
        background-color: #007acc;
    }
    
    QMessageBox {
        background-color: #1e1e1e;
    }
    
    QMessageBox QLabel {
        color: #d4d4d4;
    }
    
    QInputDialog {
        background-color: #252526;
    }
    
    QMenu {
        background-color: #252526;
        color: #cccccc;
        border: 1px solid #3e3e42;
    }
    
    QMenu::item:selected {
        background-color: #094771;
    }
    
    QTabWidget::pane {
        border: 1px solid #3e3e42;
        background-color: #1e1e1e;
    }
    
    QTabBar::tab {
        background-color: #2d2d30;
        color: #cccccc;
        padding: 6px 12px;
        border: 1px solid #3e3e42;
        border-bottom: none;
    }
    
    QTabBar::tab:selected {
        background-color: #1e1e1e;
        color: #ffffff;
    }
    
    QTabBar::tab:hover {
        background-color: #2a2d2e;
    }
    """
    
    LIGHT_STYLESHEET = """
    QMainWindow, QDialog, QWidget {
        background-color: #f0f0f0;
        color: #000000;
    }
    
    QHeaderView::section {
        background-color: #e1e1e1;
        color: #000000;
        border: 1px solid #dcdcdc;
        padding: 4px;
    }

    QTreeWidget {
        background-color: #ffffff;
        color: #000000;
        border: 1px solid #c0c0c0;
        alternate-background-color: #f7f7f7;
    }
    
    QTreeWidget::item:selected {
        background-color: #0078d7;
        color: #ffffff;
    }
    
    QTreeWidget::item:hover {
        background-color: #e5f3ff;
    }
    
    QTextEdit {
        background-color: #ffffff;
        color: #000000;
        border: 1px solid #c0c0c0;
        selection-background-color: #0078d7;
        selection-color: #ffffff;
    }
    
    QLineEdit, QSpinBox {
        background-color: #ffffff;
        color: #000000;
        border: 1px solid #c0c0c0;
        padding: 4px;
    }
    
    QPushButton {
        background-color: #e1e1e1;
        color: #000000;
        border: 1px solid #adadad;
        padding: 6px 12px;
        border-radius: 2px;
    }
    
    QPushButton:hover {
        background-color: #e5f1fb;
        border: 1px solid #0078d7;
    }
    
    QPushButton:pressed {
        background-color: #cce4f7;
    }
    
    QStatusBar {
        background-color: #f0f0f0;
        color: #000000;
    }
    
    QMessageBox {
        background-color: #f0f0f0;
    }
    
    QMessageBox QLabel {
        color: #000000;
    }
    
    QLabel {
        color: #000000;
    }
    """
    
    @staticmethod
    def apply_theme(theme_name: str):
        """Применить тему к приложению
        
        Args:
            theme_name: 'dark' или 'light'
        """
        app = QApplication.instance()
        if not app:
            return
        
        if theme_name == "dark":
            ThemeManager._set_dark_palette(app)
            app.setStyleSheet(ThemeManager.DARK_STYLESHEET)
        else:
            app.setPalette(app.style().standardPalette())
            app.setStyleSheet(ThemeManager.LIGHT_STYLESHEET)
    
    @staticmethod
    def _set_dark_palette(app):
        """Установить темную палитру для приложения"""
        dark_palette = QPalette()
        
        # Основные цвета
        dark_palette.setColor(QPalette.Window, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.WindowText, QColor(212, 212, 212))
        dark_palette.setColor(QPalette.Base, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.AlternateBase, QColor(45, 45, 48))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(212, 212, 212))
        dark_palette.setColor(QPalette.ToolTipText, QColor(212, 212, 212))
        dark_palette.setColor(QPalette.Text, QColor(212, 212, 212))
        dark_palette.setColor(QPalette.Button, QColor(60, 60, 60))
        dark_palette.setColor(QPalette.ButtonText, QColor(212, 212, 212))
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(0, 122, 204))
        dark_palette.setColor(QPalette.Highlight, QColor(9, 71, 113))
        dark_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        
        # Неактивные цвета
        dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
        dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
        dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127))
        
        app.setPalette(dark_palette)
