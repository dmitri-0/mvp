"""Модуль для мониторинга буфера обмена и автоматического создания записей."""
from datetime import datetime
import re
import base64
from html import escape
from PySide6.QtCore import QObject, Signal, QMimeData
from PySide6.QtGui import QClipboard, QImage
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
        # Если есть текст - берем первую значимую строку
        if text_content:
            lines = text_content.split('\n')
            for line in lines:
                clean_line = line.strip()
                # Пропускаем пустые строки и разделители
                if clean_line and clean_line not in ['---', '***', '___', '===']:
                    # Обрезаем до разумной длины и санитизируем
                    title = clean_line[:80]
                    # Убираем недопустимые символы для имени файла/заголовка
                    title = re.sub(r'[<>:"/\\|?*\r\n]', '', title)
                    return title if title else datetime.now().strftime("%H:%M:%S")
            # Если все строки пустые/разделители
            return datetime.now().strftime("%H:%M:%S")
        
        # Если только изображение - формируем заголовок с данными об изображении
        if image_data:
            try:
                image = QImage.fromData(image_data)
                if not image.isNull():
                    width = image.width()
                    height = image.height()
                    # Определяем формат (по умолчанию PNG)
                    fmt = "PNG"
                    return f"Image {width}x{height} {fmt}"
            except Exception:
                pass
            return "Image"
        
        # Fallback - используем время
        return datetime.now().strftime("%H:%M:%S")

    def _is_duplicate(self, text_content, image_data):
        """Проверить, является ли контент дубликатом последней записи в 'Буфер обмена'."""
        clipboard_root_id = self._get_or_create_clipboard_root()
        last_note = self.repo.get_last_descendant(clipboard_root_id)

        if not last_note:
            return False

        note_id = last_note[0]
        body_html = last_note[3] or ""

        # Сравнение текста
        if text_content:
            # Извлекаем простой текст из HTML для сравнения
            from PySide6.QtGui import QTextDocument
            doc = QTextDocument()
            doc.setHtml(body_html)
            last_plain_text = doc.toPlainText().strip()

            if text_content == last_plain_text:
                return True

        # Сравнение изображений (по байтам первого вложения)
        # Note: Это не сработает корректно для смешанного контента (текст + фото), 
        # но для базового предотвращения спама "одной и той же картинкой" пойдет.
        if image_data and not text_content:
            attachments = self.repo.get_attachments(note_id)
            if attachments and len(attachments) > 0:
                last_image_bytes = attachments[0][2]  # bytes поле
                if image_data == last_image_bytes:
                    return True

        return False

    def _process_html_and_extract_images(self, note_id, html):
        """
        Парсинг HTML и сохранение base64 картинок как вложений.
        Возвращает (обработанный_html, найдены_ли_картинки).
        """
        has_extracted_images = False
        
        # Regex для поиска src="data:image/..."
        # Группы: 1 - mime type, 2 - base64 data
        pattern_b64 = re.compile(r'src=["\']?data:(image/[^;]+);base64,([^"\'\>\s]+)["\']?')
        
        def replacer(match):
            nonlocal has_extracted_images
            mime_type = match.group(1)
            b64_data = match.group(2)
            
            try:
                img_bytes = base64.b64decode(b64_data)
                # Генерируем имя файла
                ext = mime_type.split('/')[-1]
                # Используем timestamp и часть хеша или длины для уникальности в рамках одной операции
                name = f"clip_{datetime.now().strftime('%H%M%S%f')}.{ext}"
                
                att_id = self.repo.add_attachment(note_id, name, img_bytes, mime_type)
                has_extracted_images = True
                return f'src="noteimg://{att_id}"'
            except Exception as e:
                print(f"Error saving clipboard image from HTML: {e}")
                return match.group(0)

        new_html = pattern_b64.sub(replacer, html)
        return new_html, has_extracted_images

    def _on_clipboard_changed(self):
        """Обработчик изменения буфера обмена."""
        mime_data = self.clipboard.mimeData()
        if not mime_data:
            return

        # 1. Получаем данные
        
        # Текст: обязательно делаем strip(), чтобы убрать лишние переносы
        text_content = ""
        if mime_data.hasText():
            text_content = mime_data.text().strip()
        
        has_text = bool(text_content)

        # Raw Image: стандартная картинка в буфере
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

        # HTML: для богатого контента (текст + картинки)
        html_content = ""
        has_html = False
        if mime_data.hasHtml():
            html_content = mime_data.html()
            if html_content:
                has_html = True

        # Если пусто - выходим
        if not has_text and not has_raw_image and not has_html:
            return

        # Проверка на дубликат (по тексту или сырой картинке)
        if self._is_duplicate(text_content, image_data):
            return

        # 2. Создаем структуру заметок
        clipboard_root_id = self._get_or_create_clipboard_root()
        date_node_id = self._get_or_create_date_node(clipboard_root_id)
        
        # Генерируем заголовок на основе содержимого
        note_title = self._generate_note_title(text_content, image_data, has_html)
        time_node_id = self.repo.create_note(date_node_id, note_title)
        
        final_html_to_save = ""
        saved_something = False

        # 3. Логика сохранения

        # ПРИОРИТЕТ: Изображения
        # Если есть HTML, пытаемся извлечь из него картинки
        html_images_found = False
        if has_html:
            processed_html, extracted_imgs = self._process_html_and_extract_images(time_node_id, html_content)
            
            if extracted_imgs:
                # Если найдены картинки в HTML - сохраняем ТОЛЬКО их (игнорируем текст)
                # Извлекаем src="noteimg://..." из обработанного HTML
                matcher = re.compile(r'src="(noteimg://[^"]+)"')
                found_srcs = matcher.findall(processed_html)
                if found_srcs:
                    final_html_to_save = "".join([f'<img src="{src}" /><br/>' for src in found_srcs])
                    saved_something = True
                    html_images_found = True

        # Если в HTML картинок не было, но есть Raw Image
        if not saved_something and has_raw_image:
            att_id = self.repo.add_attachment(time_node_id, "clipboard_image.png", image_data, "image/png")
            final_html_to_save = f'<img src="noteimg://{att_id}" />'
            saved_something = True

        # ПРИОРИТЕТ: Текст (только если нет картинок)
        if not saved_something and has_text:
            # Сохраняем как Plain Text, убирая всё форматирование
            final_html_to_save = (
                '<pre style="white-space: pre-wrap; font-family: inherit; margin: 0;">'
                f"{escape(text_content)}"
                "</pre>"
            )
            saved_something = True

        # 4. Фиксация результата
        if saved_something and final_html_to_save:
            self.repo.save_note(time_node_id, note_title, final_html_to_save, 0)
            
            # Обновляем последнее состояние
            self.last_text = text_content
            self.last_image_data = image_data
            
            self.clipboard_changed.emit(time_node_id)
        else:
            # Если ничего не сохранили (пустота), удаляем созданный узел
            self.repo.delete_note(time_node_id)

    def enable(self):
        """Включить мониторинг."""
        self.clipboard.dataChanged.connect(self._on_clipboard_changed)

    def disable(self):
        """Отключить мониторинг."""
        try:
            self.clipboard.dataChanged.disconnect(self._on_clipboard_changed)
        except RuntimeError:
            pass  # Уже отключено
