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

    def _process_mixed_content(self, note_id, html_content):
        """
        Разбирает HTML, сохраняет порядок контента.
        Текст очищается от стилей, картинки сохраняются вложениями.
        Возвращает (итоговый_html, было_ли_сохранено_что_то).
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
                        
                        # Пытаемся получить изображение из ресурсов документа
                        # QTextDocument автоматически парсит data:base64 в ресурсы
                        image_variant = doc.resource(QTextDocument.ImageResource, QUrl(name))
                        
                        if isinstance(image_variant, QImage) and not image_variant.isNull():
                            img = image_variant
                        else:
                            # Попытка загрузить по имени (если это локальный путь или что-то еще)
                            img = QImage(name)

                        if not img.isNull():
                            from PySide6.QtCore import QBuffer, QIODevice
                            ba = QBuffer()
                            ba.open(QIODevice.WriteOnly)
                            img.save(ba, "PNG")
                            img_bytes = ba.data().data()
                            
                            # Генерируем уникальное имя
                            att_name = f"clip_{datetime.now().strftime('%H%M%S%f')}.png"
                            att_id = self.repo.add_attachment(note_id, att_name, img_bytes, "image/png")
                            
                            block_content.append(f'<img src="noteimg://{att_id}" />')
                            has_content = True
                    else:
                        text = fragment.text()
                        if text:
                            # Экранируем HTML спецсимволы, чтобы текст остался текстом
                            block_content.append(escape(text))
                            if text.strip():
                                has_content = True
                
                it += 1
            
            # Собираем блок (строку)
            if block_content:
                final_html_parts.append("".join(block_content))
            
            block = block.next()
        
        # Объединяем блоки через <br/> или <p>, чтобы сохранить структуру строк
        # Используем <pre>-like стиль для простоты или просто <br>
        # Чтобы сохранить переносы строк, лучше всего соединить <br/>
        final_html = "<br/>".join(final_html_parts)
        
        # Оборачиваем в div/pre для сохранения шрифта, если нужно, или оставляем как есть.
        # Пользователь просил plain text, так что просто текст + картинки + br.
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

        # 3. Логика сохранения (Mixed Content: Text + Image)
        
        # Если есть HTML, используем его для извлечения текста и картинок в правильном порядке
        if has_html:
            processed_html, has_mixed_content = self._process_mixed_content(time_node_id, html_content)
            if has_mixed_content:
                final_html_to_save = processed_html
                saved_something = True
        
        # Если HTML не дал результата (или его нет), но есть Raw Image
        # Это может случиться, если скопировали файл картинки или скриншот (HTML часто нет)
        # Или если HTML был, но пустой/невалидный
        if not saved_something and has_raw_image:
            att_id = self.repo.add_attachment(time_node_id, "clipboard_image.png", image_data, "image/png")
            # Если был и текст, добавляем его (хотя порядок неизвестен, ставим текст сверху)
            if has_text:
                final_html_to_save = f'{escape(text_content)}<br/><img src="noteimg://{att_id}" />'
            else:
                final_html_to_save = f'<img src="noteimg://{att_id}" />'
            saved_something = True
        
        # Если нет картинок, только текст
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
