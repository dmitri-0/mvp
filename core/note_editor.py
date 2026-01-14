from datetime import datetime
import sys
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Signal, QUrl, QMimeData, Qt
from PySide6.QtGui import QImage, QTextDocument, QTextCursor, QTextCharFormat, QKeyEvent
from PySide6.QtWidgets import QTextEdit, QApplication
import re
import base64
from html import escape


class NoteEditor(QTextEdit):
    """Кастомный редактор заметок с поддержкой вставки изображений"""

    focusOut = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = None
        self.current_note_id = None
        self.main_window = None  # Ссылка на главное окно

    def set_context(self, repo):
        """Установить контекст для работы с БД"""
        self.repo = repo

    def set_current_note_id(self, note_id: int | None):
        """Задать id заметки, содержимое которой сейчас находится в редакторе"""
        self.current_note_id = note_id
        
        # Обновляем read-only статус для заметок из буфера обмена
        if self.repo and note_id:
            is_clipboard = self.repo.is_clipboard_note(note_id)
            self.setReadOnly(is_clipboard)
        else:
            self.setReadOnly(False)

    def set_main_window(self, window):
        """Установить ссылку на главное окно"""
        self.main_window = window

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focusOut.emit()

    def loadResource(self, resource_type, url):
        """
        Ленивая загрузка ресурсов изображений из БД.
        Вызывается QTextDocument автоматически при рендеринге HTML,
        если ресурс не был предварительно зарегистрирован через addResource().
        """
        # Обрабатываем только изображения с noteimg:// схемой
        if resource_type == QTextDocument.ImageResource and url.scheme() == "noteimg":
            if not self.repo:
                return super().loadResource(resource_type, url)
            
            # Извлекаем ID вложения из URL
            att_id = self._parse_id_from_name(url.toString())
            if not att_id:
                return super().loadResource(resource_type, url)
            
            try:
                # Загружаем вложение из БД
                att_data = self.repo.get_attachment(att_id)
                if att_data:
                    _, _, name, img_bytes, mime = att_data
                    if img_bytes:
                        # Создаём QImage из байтов
                        image = QImage.fromData(img_bytes)
                        if not image.isNull():
                            # Регистрируем ресурс в документе для последующего использования
                            self.document().addResource(QTextDocument.ImageResource, url, image)
                            return image
            except Exception as e:
                print(f"Error loading image resource {url.toString()}: {e}")
        
        # Для остальных типов ресурсов используем стандартное поведение
        return super().loadResource(resource_type, url)

    def _is_clipboard_note(self):
        """Проверить, является ли текущая заметка из ветки 'Буфер обмена'"""
        if not self.repo or not self.current_note_id:
            return False
        return self.repo.is_clipboard_note(self.current_note_id)

    def _copy_and_paste_clipboard_note(self):
        """
        Специальное поведение Enter для заметок из буфера обмена:
        1. Копирует все содержимое заметки в буфер обмена
        2. Сворачивает приложение в трей
        3. Выполняет вставку Ctrl+V в активное окно
        """
        # Выбираем все содержимое
        cursor = self.textCursor()
        cursor.select(QTextCursor.Document)
        self.setTextCursor(cursor)
        
        # Копируем в буфер обмена
        self.copy()
        
        # Сбрасываем выделение
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.Start)
        self.setTextCursor(cursor)
        
        # Сворачиваем приложение в трей
        if self.main_window:
            self.main_window.hide_to_tray()
        
        # Небольшая задержка чтобы окно успело скрыться
        QApplication.processEvents()
        
        # Выполняем вставку через симуляцию Ctrl+V
        try:
            if sys.platform == 'win32':
                import ctypes
                import time
                
                # Небольшая задержка чтобы другое окно стало активным
                time.sleep(0.1)
                
                # Симуляция Ctrl+V
                VK_CONTROL = 0x11
                VK_V = 0x56
                KEYEVENTF_KEYUP = 0x0002
                
                user32 = ctypes.windll.user32
                
                # Нажатие Ctrl
                user32.keybd_event(VK_CONTROL, 0, 0, 0)
                time.sleep(0.05)
                
                # Нажатие V
                user32.keybd_event(VK_V, 0, 0, 0)
                time.sleep(0.05)
                
                # Отпускание V
                user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
                time.sleep(0.05)
                
                # Отпускание Ctrl
                user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            else:
                # Для Linux/Mac можно использовать xdotool или другие инструменты
                import subprocess
                import time
                time.sleep(0.1)
                # xdotool для Linux
                subprocess.run(['xdotool', 'key', 'ctrl+v'], check=False)
        except Exception as e:
            print(f"Error simulating paste: {e}")

    def keyPressEvent(self, event: QKeyEvent):
        """Переопределённая обработка нажатий клавиш"""
        # Обрабатываем Enter/Return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Специальное поведение для заметок из буфера обмена
            if self._is_clipboard_note():
                self._copy_and_paste_clipboard_note()
                event.accept()
                return
            
            # Стандартное поведение для обычных заметок
            # Вставляем новую строку через insertHtml для консистентности
            cursor = self.textCursor()
            cursor.insertHtml("<br/>")
            self.setTextCursor(cursor)
            event.accept()
            return
        
        # Для остальных клавиш используем стандартную обработку
        super().keyPressEvent(event)
    
    def _parse_id_from_name(self, name: str) -> int | None:
        """Извлечение числового ID из URL (поддержка формата IPv4 для Qt)"""
        # Удаляем схему
        clean = name.replace("noteimg://", "")
        
        # 1. Пробуем простое число
        try:
            return int(clean)
        except ValueError:
            pass
            
        # 2. Пробуем IPv4 (Qt может нормализовать noteimg://123 -> noteimg://0.0.0.123)
        if clean.count('.') == 3:
            try:
                parts = list(map(int, clean.split('.')))
                if len(parts) == 4:
                    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]
            except ValueError:
                pass
                
        return None

    def createMimeDataFromSelection(self):
        """Создание MIME-данных при копировании (добавляем поддержку внешних приложений)"""
        mime = super().createMimeDataFromSelection()
        
        # 1. Если выделена ОДНА картинка, добавляем её как ImageData (для вставки файла в проводник/мессенджеры)
        cursor = self.textCursor()
        if cursor.hasSelection() and not cursor.selection().isEmpty():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            
            if end - start == 1:
                tmp_cursor = QTextCursor(self.document())
                tmp_cursor.setPosition(start)
                tmp_cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
                fmt = tmp_cursor.charFormat()
                
                if fmt.isImageFormat():
                    name = fmt.toImageFormat().name()
                    if name.startswith("noteimg://"):
                        att_id = self._parse_id_from_name(name)
                        if att_id and self.repo:
                            try:
                                att_data = self.repo.get_attachment(att_id)
                                if att_data:
                                    _, _, _, img_bytes, _ = att_data
                                    if img_bytes:
                                        img = QImage.fromData(img_bytes)
                                        mime.setImageData(img)
                            except Exception as e:
                                print(f"Error exporting image to clipboard: {e}")

        # 2. Обработка HTML: Конвертация внутренних ссылок noteimg:// в Base64 для внешних приложений (Word, Browser)
        if mime.hasHtml() and self.repo:
            html = mime.html()
            # Regex для поиска src="noteimg://..."
            pattern = re.compile(r'src=["\']?noteimg://([0-9\.]+)["\']?')
            
            def replacer(match):
                full_match = match.group(0)
                raw_id = match.group(1)
                
                att_id = self._parse_id_from_name(f"noteimg://{raw_id}")
                if not att_id:
                    return full_match
                
                try:
                    att_data = self.repo.get_attachment(att_id)
                    if att_data:
                        _, _, _, img_bytes, mime_type = att_data
                        if img_bytes:
                            # Конвертация в Base64
                            b64_str = base64.b64encode(img_bytes).decode('utf-8')
                            if not mime_type: mime_type = "image/png"
                            # Заменяем на data URI
                            return f'src="data:{mime_type};base64,{b64_str}"'
                except Exception as e:
                    print(f"Error embedding image for clipboard: {e}")
                
                return full_match

            new_html = pattern.sub(replacer, html)
            mime.setHtml(new_html)
                            
        return mime

    def canInsertFromMimeData(self, source):
        """Проверка возможности вставки из буфера обмена"""
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        """Вставка данных из буфера обмена (поддержка изображений, очистка стилей текста)"""
        
        # ПРИОРИТЕТ 1: Обработка HTML (поддержка noteimg:// и data:base64)
        if source.hasHtml() and self.repo and self.current_note_id:
            html = source.html()
            
            # Используем временный QTextDocument для парсинга и очистки стилей
            temp_doc = QTextDocument()
            temp_doc.setHtml(html)
            
            final_html_parts = []
            
            block = temp_doc.begin()
            while block.isValid():
                block_content = []
                it = block.begin()
                while not it.atEnd():
                    fragment = it.fragment()
                    if fragment.isValid():
                        char_format = fragment.charFormat()
                        
                        if char_format.isImageFormat():
                            img_fmt = char_format.toImageFormat()
                            name = img_fmt.name()
                            
                            # 1. Попытка noteimg (внутренние копии)
                            att_id = None
                            if name.startswith("noteimg://"):
                                raw_id = name.replace("noteimg://", "")
                                att_id = self._parse_id_from_name(raw_id)
                                if att_id:
                                    try:
                                        att_data = self.repo.get_attachment(att_id)
                                        if att_data:
                                            _, _, old_name, img_bytes, mime = att_data
                                            new_name = f"copy_{old_name}"
                                            # Создаем копию вложения
                                            att_id = self.repo.add_attachment(self.current_note_id, new_name, img_bytes, mime)
                                            # Регистрируем ресурс
                                            image = QImage.fromData(img_bytes)
                                            url = QUrl(f"noteimg://{att_id}")
                                            self.document().addResource(QTextDocument.ImageResource, url, image)
                                    except Exception as e:
                                        print(f"Error copying attachment: {e}")
                                        att_id = None
                            
                            # 2. Попытка base64 или другие ресурсы (QTextDocument сам парсит data:base64)
                            if not att_id:
                                image_variant = temp_doc.resource(QTextDocument.ImageResource, QUrl(name))
                                if isinstance(image_variant, QImage) and not image_variant.isNull():
                                    try:
                                        ba = QBuffer()
                                        ba.open(QIODevice.WriteOnly)
                                        image_variant.save(ba, "PNG")
                                        img_bytes = ba.data().data()
                                        
                                        att_name = f"pasted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                                        att_id = self.repo.add_attachment(self.current_note_id, att_name, img_bytes, "image/png")
                                        
                                        url = QUrl(f"noteimg://{att_id}")
                                        self.document().addResource(QTextDocument.ImageResource, url, image_variant)
                                    except Exception as e:
                                        print(f"Error saving pasted image: {e}")
                            
                            if att_id:
                                block_content.append(f'<img src="noteimg://{att_id}" />')
                                
                        else:
                            # Текст: экранируем и вставляем без стилей, заменяя \n на <br/>
                            text = fragment.text()
                            if text:
                                txt = escape(text).replace("\n", "<br/>")
                                block_content.append(txt)
                    
                    it += 1
                
                # Добавляем блок. Даже если он пустой (пустая строка между параграфами)
                final_html_parts.append("".join(block_content))
                
                block = block.next()
            
            if final_html_parts:
                # Вставляем очищенный HTML
                cleaned_html = "<br/>".join(final_html_parts)
                
                # Используем QMimeData для вставки, чтобы редактор сам разобрался с undo/redo
                new_mime = QMimeData()
                new_mime.setHtml(cleaned_html)
                super().insertFromMimeData(new_mime)
                return

        # ПРИОРИТЕТ 2: Чистое изображение (скриншот, файл)
        # Если HTML не обработан (или его нет), но есть Raw Image
        if source.hasImage() and self.repo and self.current_note_id:
            image = source.imageData()
            if isinstance(image, QImage):
                ba = QByteArray()
                buff = QBuffer(ba)
                buff.open(QIODevice.WriteOnly)
                image.save(buff, "PNG")
                img_bytes = ba.data()

                name = f"pasted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                att_id = self.repo.add_attachment(self.current_note_id, name, img_bytes, "image/png")

                url = QUrl(f"noteimg://{att_id}")
                self.document().addResource(QTextDocument.ImageResource, url, image)
                self.textCursor().insertHtml(f'<img src="{url.toString()}" />')
                return

        # ПРИОРИТЕТ 3: Текст (удаление форматирования)
        if source.hasText():
            self.insertPlainText(source.text())
            return

        super().insertFromMimeData(source)
    
    def get_images_in_content(self):
        """Возвращает список изображений, присутствующих в тексте заметки"""
        images = []
        if not self.repo or not self.current_note_id:
            return images

        # Получаем HTML содержимое
        html = self.toHtml()
        
        # Regex для поиска src="noteimg://..."
        pattern_noteimg = re.compile(r'src=["\']?noteimg://([0-9\.]+)["\']?')
        pattern_noteimg = re.compile(r'src=["\']?noteimg://([0-9\.]+)["\']?')
        matches_noteimg = pattern_noteimg.findall(html)
        
        processed_ids = set()
        for raw_id in matches_noteimg:
            if raw_id in processed_ids: continue
            
            att_id = self._parse_id_from_name(f"noteimg://{raw_id}")
            if att_id:
                processed_ids.add(raw_id)
                # Получаем данные из репозитория
                att_data = self.repo.get_attachment(att_id)
                if att_data:
                    # att_data = (id, note_id, name, bytes, mime)
                    images.append(att_data)
        
        return images
