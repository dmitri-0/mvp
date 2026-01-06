from datetime import datetime
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Signal, QUrl, QMimeData
from PySide6.QtGui import QImage, QTextDocument, QTextCursor, QTextCharFormat
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

    def createMimeDataFromSelection(self):
        """Создание MIME-данных при копировании (добавляем поддержку внешних приложений)"""
        mime = super().createMimeDataFromSelection()
        
        # Если выделена картинка, добавляем её как ImageData в буфер
        cursor = self.textCursor()
        if cursor.hasSelection() and not cursor.selection().isEmpty():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            
            # Проверяем, выделен ли ровно один символ (картинка - это 1 символ)
            if end - start == 1:
                tmp_cursor = QTextCursor(self.document())
                tmp_cursor.setPosition(start)
                tmp_cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
                fmt = tmp_cursor.charFormat()
                
                if fmt.isImageFormat():
                    name = fmt.toImageFormat().name()
                    if name.startswith("noteimg://"):
                        try:
                            att_id = int(name.replace("noteimg://", ""))
                            if self.repo:
                                att_data = self.repo.get_attachment(att_id)
                                if att_data:
                                    _, _, _, img_bytes, _ = att_data
                                    if img_bytes:
                                        img = QImage.fromData(img_bytes)
                                        mime.setImageData(img)
                        except Exception as e:
                            print(f"Error exporting image to clipboard: {e}")
                            
        return mime

    def canInsertFromMimeData(self, source):
        """Проверка возможности вставки из буфера обмена"""
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        """Вставка данных из буфера обмена (поддержка изображений)"""
        if source.hasImage() and self.repo and self.current_note_id:
            pass  # Fallthrough to logic below to prioritize HTML if available

        # Обработка HTML для поддержки копирования картинок между заметками
        if source.hasHtml() and self.repo and self.current_note_id:
            html = source.html()
            
            # Поиск всех ссылок на изображения noteimg://
            # Поддержка разных форматов атрибута src (с кавычками и без)
            pattern = re.compile(r'src=["\']?noteimg://(\d+)["\']?')
            matches = pattern.findall(html)
            
            if matches:
                id_map = {}
                processed_ids = set()

                for old_att_id in matches:
                    if old_att_id in processed_ids:
                        continue
                    processed_ids.add(old_att_id)
                    
                    try:
                        att_id_int = int(old_att_id)
                        att_data = self.repo.get_attachment(att_id_int)
                        
                        if att_data:
                            _, _, name, img_bytes, mime = att_data
                            
                            # Создаем копию вложения для текущей заметки
                            new_name = f"copy_{name}"
                            new_att_id = self.repo.add_attachment(self.current_note_id, new_name, img_bytes, mime)
                            
                            # Регистрируем ресурс в документе
                            if img_bytes:
                                image = QImage.fromData(img_bytes)
                                url = QUrl(f"noteimg://{new_att_id}")
                                self.document().addResource(QTextDocument.ImageResource, url, image)
                            
                            # Сохраняем маппинг для замены
                            id_map[old_att_id] = new_att_id
                    except Exception as e:
                        print(f"Error processing attachment {old_att_id}: {e}")
                
                if id_map:
                    # Функция замены для regex, чтобы менять только нужные ID в контексте src
                    def replacer(match):
                        full_match = match.group(0)
                        old_id = match.group(1)
                        if old_id in id_map:
                            return full_match.replace(f"noteimg://{old_id}", f"noteimg://{id_map[old_id]}")
                        return full_match

                    new_html = pattern.sub(replacer, html)
                    
                    new_source = QMimeData()
                    new_source.setHtml(new_html)
                    if source.hasText():
                        new_source.setText(source.text())
                    super().insertFromMimeData(new_source)
                    return

        # Стандартная обработка чистого изображения (если нет HTML или вставка из файла/скриншота)
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
