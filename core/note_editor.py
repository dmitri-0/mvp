from datetime import datetime
import sys
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Signal, QUrl, QMimeData, Qt
from PySide6.QtGui import QImage, QTextDocument, QTextCursor, QTextCharFormat, QKeyEvent
from PySide6.QtWidgets import QTextEdit, QApplication
import re
import base64


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
        """Вставка данных из буфера обмена (поддержка изображений)"""
        
        # ПРИОРИТЕТ 1: Обработка HTML (поддержка noteimg:// и data:base64)
        if source.hasHtml() and self.repo and self.current_note_id:
            html = source.html()
            current_html = html
            is_modified = False
            
            # A. Обработка noteimg:// (если скопировано внутри старой версии или без конвертации)
            pattern_noteimg = re.compile(r'src=["\']?noteimg://([0-9\.]+)["\']?')
            matches_noteimg = pattern_noteimg.findall(current_html)
            
            if matches_noteimg:
                id_map = {}
                processed_ids = set()
                
                for raw_id in matches_noteimg:
                    if raw_id in processed_ids: continue
                    processed_ids.add(raw_id)
                    
                    try:
                        att_id = self._parse_id_from_name(f"noteimg://{raw_id}")
                        if not att_id: continue
                        
                        att_data = self.repo.get_attachment(att_id)
                        if att_data:
                            _, _, name, img_bytes, mime = att_data
                            new_name = f"copy_{name}"
                            new_att_id = self.repo.add_attachment(self.current_note_id, new_name, img_bytes, mime)
                            
                            if img_bytes:
                                image = QImage.fromData(img_bytes)
                                url = QUrl(f"noteimg://{new_att_id}")
                                self.document().addResource(QTextDocument.ImageResource, url, image)
                            
                            id_map[raw_id] = new_att_id
                    except Exception as e:
                        print(f"Error processing attachment {raw_id}: {e}")
                
                if id_map:
                    def noteimg_replacer(match):
                        full = match.group(0)
                        old = match.group(1)
                        if old in id_map:
                            return full.replace(f"noteimg://{old}", f"noteimg://{id_map[old]}")
                        return full
                    current_html = pattern_noteimg.sub(noteimg_replacer, current_html)
                    is_modified = True

            # B. Обработка data:image/base64 (вставка из Word, браузера или после createMimeData)
            pattern_b64 = re.compile(r'src=["\']?data:(image/[^;]+);base64,([^"\'>\s]+)["\']?')
            
            if pattern_b64.search(current_html):
                def b64_replacer(match):
                    nonlocal is_modified
                    mime_type = match.group(1)
                    b64_data = match.group(2)
                    
                    try:
                        img_bytes = base64.b64decode(b64_data)
                        ext = mime_type.split('/')[-1]
                        name = f"pasted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                        
                        att_id = self.repo.add_attachment(self.current_note_id, name, img_bytes, mime_type)
                        
                        image = QImage.fromData(img_bytes)
                        url = QUrl(f"noteimg://{att_id}")
                        self.document().addResource(QTextDocument.ImageResource, url, image)
                        
                        is_modified = True
                        return f'src="noteimg://{att_id}"'
                    except Exception as e:
                        print(f"Error importing base64 image: {e}")
                        return match.group(0)

                current_html = pattern_b64.sub(b64_replacer, current_html)
            
            if is_modified:
                new_source = QMimeData()
                new_source.setHtml(current_html)
                if source.hasText():
                    new_source.setText(source.text())
                super().insertFromMimeData(new_source)
                return

        # ПРИОРИТЕТ 2: Чистое изображение (скриншот, файл)
        # Срабатывает только если HTML не был обработан или его нет
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

        super().insertFromMimeData(source)
