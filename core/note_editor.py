from datetime import datetime
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Signal, QUrl
from PySide6.QtGui import QImage, QTextDocument
from PySide6.QtWidgets import QTextEdit


class NoteEditor(QTextEdit):
    """Кастомный редактор заметок с поддержкой вставки изображений"""

    focusOut = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = None
        self.current_note_id = None

    def set_context(self, repo):
        """Установить контекст для работы с БД"""
        self.repo = repo

    def set_current_note_id(self, note_id: int | None):
        """Задать id заметки, содержимое которой сейчас находится в редакторе"""
        self.current_note_id = note_id

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focusOut.emit()

    def canInsertFromMimeData(self, source):
        """Проверка возможности вставки из буфера обмена"""
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        """Вставка данных из буфера обмена (поддержка изображений)"""
        if source.hasImage() and self.repo and self.current_note_id:
            image = source.imageData()
            if isinstance(image, QImage):
                # Конвертация QImage в PNG bytes
                ba = QByteArray()
                buff = QBuffer(ba)
                buff.open(QIODevice.WriteOnly)
                image.save(buff, "PNG")
                img_bytes = ba.data()

                # Генерация имени и сохранение
                name = f"pasted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                att_id = self.repo.add_attachment(self.current_note_id, name, img_bytes, "image/png")

                # Регистрация ресурса и вставка HTML
                url = QUrl(f"noteimg://{att_id}")
                self.document().addResource(QTextDocument.ImageResource, url, image)
                self.textCursor().insertHtml(f'<img src="{url.toString()}" />')
                return

        super().insertFromMimeData(source)
