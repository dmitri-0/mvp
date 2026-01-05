# core/tray_controller.py
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QStyle


class TrayController:
    """Контроллер системного трея"""
    
    def __init__(self, window):
        self.window = window
        icon = window.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon)
        
        menu = QMenu()
        act_toggle = QAction("Show/Hide")
        act_toggle.triggered.connect(self.toggle)
        act_quit = QAction("Quit")
        act_quit.triggered.connect(self.window.quit_app)
        menu.addAction(act_toggle)
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda _: self.toggle())
        self.tray.show()

    def toggle(self):
        """Переключение видимости окна"""
        if self.window.isVisible():
            self.window.hide_to_tray()
        else:
            self.window.show_and_focus()
