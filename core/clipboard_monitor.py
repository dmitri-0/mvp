"""Модуль для мониторинга буфера обмена и автоматического создания записей."""
from datetime import datetime
import re
import base64
from html import escape
from PySide6.QtCore import QObject, Signal, QMimeData, QUrl
from PySide6.QtGui import QClipboard, QImage, QTextDocument
from PySide6.QtWidgets import QApplication
from core.repository import NoteRepository


class ClipboardMonitor(QObject):
    """Мониторинг буфера обмена и автоматическое сохранение в дерево заметок."""

    clipboard_changed = Signal(int)  # Signal с ID созданной заметки

    def __init__(self, repo: NoteRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.clipboard = QApplication.clipboard()
        self.last_text = ""
        self.last_image_data = b""

        # Подключаемся к изменениям буфера обмена
        self.clipboard.dataChanged.connect(self._on_clipboard_changed)

        # Инициализируем последние данные
        self._update_last_state()

    def _update_last_state(self):
        """Обновить состояние последних данных из буфера."""
        mime_data = self.clipboard.mimeData()
        if mime_data:
            if mime_data.hasText():
                self.last_text = mime_data.text().strip()
            if mime_data.hasImage():
                image = self.clipboard.image()
                if not image.isNull():
                    from PySide6.QtCore import QBuffer, QIODevice
                    buffer = QBuffer()
                    buffer.open(QIODevice.WriteOnly)
                    image.save(buffer, "PNG")
                    self.last_image_data = buffer.data().data()

    def _get_or_create_clipboard_root(self):
        """Получить или создать корневой узел 'Буфер обмена'."""
        root = self.repo.get_note_by_title("Буфер обмена")
        if not root:
            root_id = self.repo.create_note(None, "Буфер обмена")
        else:
            root_id = root[0]
        return root_id

    def _get_or_create_date_node(self, parent_id):
        """Получить или создать узел даты ГГ.ММ.ДД под указанным родителем."""
        date_str = datetime.now().strftime("%y.%m.%d")
        date_note = self.repo.get_note_by_title(date_str, parent_id)
        if not date_note:
            date_note_id = self.repo.create_note(parent_id, date_str)
        else:
            date_note_id = date_note[0]
        return date_note_id

    def _generate_note_title(self, text_content, image_data, has_html):
        """Генерация заголовка для новой заметки на основе содержимого."""
        if text_content:
            lines = text_content.split('\n')
            for line in lines:
                clean_line = line.strip()
                if clean_line and clean_line not in ['---', '***', '___', '===']:
                    title = clean_line[:80]
                    title = re.sub(r'[<>:"/\\|?*\r\n]', '', title)
                    return title if title else datetime.now().strftime("%H:%M:%S")
            return datetime.now().strftime("%H:%M:%S")
        
        if image_data:
            try:
                image = QImage.fromData(image_data)
                if not image.isNull():
                    width = image.width()
                    height = image.height()
                    fmt = "PNG"
                    return f"Image {width}x{height} {fmt}"
            except Exception:
                pass
            return "Image"
        
        return datetime.now().strftime("%H:%M:%S")

    def _is_duplicate(self, text_content, image_data):
        """Проверить, является ли контент дубликатом последней записи в 'Буфер обмена'."""
        clipboard_root_id = self._get_or_create_clipboard_root()
        last_note = self.repo.get_last_descendant(clipboard_root_id)

        if not last_note:
            return False

        note_id = last_note[0]
        body_html = last_note[3] or ""

        if text_content:
            doc = QTextDocument()
            doc.setHtml(body_html)
            last_plain_text = doc.toPlainText().strip()
            if text_content == last_plain_text:
                return True

        if image_data and not text_content:
            attachments = self.repo.get_attachments(note_id)
            if attachments and len(attachments) > 0:
                last_image_bytes = attachments[0][2]
                if image_data == last_image_bytes:
                    return True

        return False

    def _parse_id_from_name(self, name: str) -> int | None:
        """Извлечение числового ID из URL noteimg://"""
        clean = name.replace("noteimg://", "")
        try:
            return int(clean)
        except ValueError:
            pass
        if clean.count('.') == 3:
            try:
                parts = list(map(int, clean.split('.')))
                if len(parts) == 4:
                    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]
            except ValueError:
                pass
        return None

    def _process_mixed_content(self, note_id, html_content):
        """
        Разбирает HTML, сохраняет порядок контента.
        Текст очищается от стилей, картинки сохраняются вложениями.
        """
        doc = QTextDocument()
        doc.setHtml(html_content)
        
        final_html_parts = []
        has_content = False
        
        block = doc.begin()
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
                        
                        img_bytes = None
                        mime_type = "image/png"
                        
                        # 1. Попытка noteimg:// (если скопировано из приложения)
                        if name.startswith("noteimg://"):
                            att_id = self._parse_id_from_name(name)
                            if att_id:
                                att_data = self.repo.get_attachment(att_id)
                                if att_data:
                                    _, _, _, img_bytes, mime_type = att_data

                        # 2. Попытка data:image/base64
                        elif name.startswith("data:image"):
                            try:
                                # name example: data:image/png;base64,.....
                                header, b64 = name.split(",", 1)
                                if ";base64" in header:
                                    mime_type = header.split(":")[1].split(";")[0]
                                    img_bytes = base64.b64decode(b64)
                            except Exception as e:
                                print(f"Error parsing data URI: {e}")

                        # 3. Попытка достать ресурс из QTextDocument (если Qt сам распарсил)
                        if img_bytes is None:
                            image_variant = doc.resource(QTextDocument.ImageResource, QUrl(name))
                            if isinstance(image_variant, QImage) and not image_variant.isNull():
                                from PySide6.QtCore import QBuffer, QIODevice
                                ba = QBuffer()
                                ba.open(QIODevice.WriteOnly)
                                image_variant.save(ba, "PNG")
                                img_bytes = ba.data().data()
                                mime_type = "image/png"

                        if img_bytes:
                            # Сохраняем как новое вложение
                            att_name = f"clip_{datetime.now().strftime('%H%M%S%f')}.png"
                            new_att_id = self.repo.add_attachment(note_id, att_name, img_bytes, mime_type)
                            block_content.append(f'<img src="noteimg://{new_att_id}" />')
                            has_content = True
                            
                    else:
                        text = fragment.text()
                        if text:
                            # Заменяем \n на <br/>, чтобы сохранить переносы внутри фрагмента
                            # и экранируем
                            txt = escape(text).replace("\n", "<br/>")
                            block_content.append(txt)
                            if text.strip():
                                has_content = True
                
                it += 1
            
            # Добавляем блок. Если пустой - это пустая строка.
            final_html_parts.append("".join(block_content))
            
            block = block.next()
        
        final_html = "<br/>".join(final_html_parts)
        return final_html, has_content

    def _on_clipboard_changed(self):
        """Обработчик изменения буфера обмена."""
        mime_data = self.clipboard.mimeData()
        if not mime_data:
            return

        # 1. Получаем данные
        text_content = ""
        if mime_data.hasText():
            text_content = mime_data.text().strip()
        has_text = bool(text_content)

        image_data = b""
        has_raw_image = False
        if mime_data.hasImage():
            image = self.clipboard.image()
            if not image.isNull():
                from PySide6.QtCore import QBuffer, QIODevice
                buffer = QBuffer()
                buffer.open(QIODevice.WriteOnly)
                image.save(buffer, "PNG")
                image_data = buffer.data().data()
                if image_data:
                    has_raw_image = True

        html_content = ""
        has_html = False
        if mime_data.hasHtml():
            html_content = mime_data.html()
            if html_content:
                has_html = True

        if not has_text and not has_raw_image and not has_html:
            return

        if self._is_duplicate(text_content, image_data):
            return

        # 2. Создаем структуру заметок
        clipboard_root_id = self._get_or_create_clipboard_root()
        date_node_id = self._get_or_create_date_node(clipboard_root_id)
        
        note_title = self._generate_note_title(text_content, image_data, has_html)
        time_node_id = self.repo.create_note(date_node_id, note_title)
        
        final_html_to_save = ""
        saved_something = False

        # 3. Логика сохранения (Mixed Content)
        
        if has_html:
            processed_html, has_mixed_content = self._process_mixed_content(time_node_id, html_content)
            if has_mixed_content:
                final_html_to_save = processed_html
                saved_something = True
        
        # Если HTML не сработал (пустой или без картинок и текста), пробуем Raw Image
        if not saved_something and has_raw_image:
            att_id = self.repo.add_attachment(time_node_id, "clipboard_image.png", image_data, "image/png")
            if has_text:
                final_html_to_save = f'{escape(text_content).replace(chr(10), "<br/>")}<br/><img src="noteimg://{att_id}" />'
            else:
                final_html_to_save = f'<img src="noteimg://{att_id}" />'
            saved_something = True
        
        # Если ничего не помогло, но есть текст
        if not saved_something and has_text:
            final_html_to_save = (
                '<pre style="white-space: pre-wrap; font-family: inherit; margin: 0;">'
                f"{escape(text_content)}"
                "</pre>"
            )
            saved_something = True

        # 4. Фиксация результата
        if saved_something and final_html_to_save:
            self.repo.save_note(time_node_id, note_title, final_html_to_save, 0)
            self.last_text = text_content
            self.last_image_data = image_data
            self.clipboard_changed.emit(time_node_id)
        else:
            self.repo.delete_note(time_node_id)

    def enable(self):
        self.clipboard.dataChanged.connect(self._on_clipboard_changed)

    def disable(self):
        try:
            self.clipboard.dataChanged.disconnect(self._on_clipboard_changed)
        except RuntimeError:
            pass
