from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QSpinBox,
    QLineEdit,
    QPushButton,
    QFormLayout,
    QMessageBox,
)

from core.config import Config


class SettingsDialog(QDialog):
    """Диалог настроек приложения"""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.resize(400, 250)

        layout = QFormLayout()

        # Путь к базе данных
        self.db_path_edit = QLineEdit(config.get("database_path", "notes.db"))
        layout.addRow("Путь к базе данных:", self.db_path_edit)

        # Шрифт
        self.font_family_edit = QLineEdit(config.get("font_family", "Consolas"))
        layout.addRow("Шрифт:", self.font_family_edit)

        # Размер шрифта
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(config.get("font_size", 11))
        layout.addRow("Размер шрифта:", self.font_size_spin)

        # Шорткат смены фокуса
        hotkeys = config.get("hotkeys", {})
        # Поддержка вложенной структуры
        if "local" in hotkeys:
            current_focus_key = hotkeys["local"].get("toggle_focus", "F3")
        else:
            current_focus_key = hotkeys.get("toggle_focus", "F3")

        self.focus_key_edit = QLineEdit(current_focus_key)
        layout.addRow("Смена фокуса:", self.focus_key_edit)

        # Кнопки
        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)

        # Кнопка сжатия базы
        btn_vacuum = QPushButton("Сжать базу данных")
        btn_vacuum.clicked.connect(self.compact_db)

        btn_layout = QVBoxLayout()
        btn_layout.addWidget(btn_vacuum)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)

        layout.addRow("", btn_layout)
        self.setLayout(layout)

    def compact_db(self):
        """Вызов сжатия базы"""
        try:
            # Получаем репозиторий через родительское окно (MainWindow)
            repo = self.parent().repo
            repo.vacuum()
            QMessageBox.information(self, "Успех", "База данных успешно сжата.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сжатии базы данных: {e}")

    def save_settings(self):
        """Сохранение настроек"""
        self.config.set("database_path", self.db_path_edit.text())
        self.config.set("font_family", self.font_family_edit.text())
        self.config.set("font_size", self.font_size_spin.value())

        hotkeys = self.config.get("hotkeys", {})
        if "local" not in hotkeys:
            hotkeys["local"] = {}
        hotkeys["local"]["toggle_focus"] = self.focus_key_edit.text()
        self.config.set("hotkeys", hotkeys)

        QMessageBox.information(
            self,
            "Настройки",
            "Настройки сохранены. Изменения применены.",
        )
        self.accept()
