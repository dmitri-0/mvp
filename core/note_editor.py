from datetime import datetime
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Signal, QUrl, QMimeData
from PySide6.QtGui import QImage, QTextDocument
from PySide6.QtWidgets import QTextEdit
import re


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
        # Если есть изображение в буфере (скриншот или копирование картинки)
        if source.hasImage() and self.repo and self.current_note_id:
            # Проверяем, нет ли HTML с noteimg (при копировании выделения текста+картинки)
            # hasImage() часто True только если в буфере чистое изображение.
            # Если выделен текст и картинка, hasImage может быть False, но hasHtml True.
            # Однако, иногда (в зависимости от OS) может быть и то и то.
            # Приоритет отдаем обработке HTML, если там есть наши картинки.
            pass

        # Обработка HTML для поддержки копирования картинок между заметками
        if source.hasHtml() and self.repo and self.current_note_id:
            html = source.html()
            
            # Поиск всех ссылок на изображения noteimg://
            pattern = re.compile(r'src=["\']noteimg://(\d+)["\']')
            matches = pattern.findall(html)
            
            if matches:
                new_html = html
                found_replacements = False
                processed_ids = set()

                for old_att_id in matches:
                    if old_att_id in processed_ids:
                        continue
                    processed_ids.add(old_att_id)

                    # Проверяем, загружен ли ресурс. Если нет или если это новая заметка - копируем.
                    # Даже если ресурс есть, при вставке в НОВУЮ заметку лучше создать копию,
                    # чтобы вложения были независимыми.
                    
                    try:
                        att_id_int = int(old_att_id)
                        att_data = self.repo.get_attachment(att_id_int)
                        
                        if att_data:
                            _, _, name, img_bytes, mime = att_data
                            
                            # Создаем новое вложение для текущей заметки
                            new_name = f"copy_{name}"
                            new_att_id = self.repo.add_attachment(self.current_note_id, new_name, img_bytes, mime)
                            
                            # Регистрируем ресурс
                            if img_bytes:
                                image = QImage.fromData(img_bytes)
                                url = QUrl(f"noteimg://{new_att_id}")
                                self.document().addResource(QTextDocument.ImageResource, url, image)
                            
                            # Заменяем ID в HTML
                            # Используем regex для замены только точных вхождений
                            new_html = new_html.replace(f'noteimg://{old_att_id}', f'noteimg://{new_att_id}')
                            found_replacements = True
                    except Exception as e:
                        print(f"Error processing attachment {old_att_id}: {e}")
                
                if found_replacements:
                    new_source = QMimeData()
                    new_source.setHtml(new_html)
                    if source.hasText():
                        new_source.setText(source.text())
                    super().insertFromMimeData(new_source)
                    return

        # Стандартная обработка чистого изображения (если не перехвачено HTML выше)
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
