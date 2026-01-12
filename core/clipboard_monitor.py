"""Модуль для мониторинга буфера обмена и автоматического создания записей."""
from datetime import datetime
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
                self.last_text = mime_data.text()
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
    
    def _get_or_create_time_node(self, parent_id):
        """Создать узел времени ЧЧ.ММ.СС под указанным родителем."""
        time_str = datetime.now().strftime("%H:%M:%S")
        time_note_id = self.repo.create_note(parent_id, time_str)
        return time_note_id
    
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
            
            if text_content.strip() == last_plain_text:
                return True
        
        # Сравнение изображений (по байтам первого вложения)
        if image_data:
            attachments = self.repo.get_attachments(note_id)
            if attachments and len(attachments) > 0:
                last_image_bytes = attachments[0][2]  # bytes поле
                if image_data == last_image_bytes:
                    return True
        
        return False
    
    def _on_clipboard_changed(self):
        """Обработчик изменения буфера обмена."""
        mime_data = self.clipboard.mimeData()
        if not mime_data:
            return
        
        text_content = ""
        image_data = b""
        has_text = False
        has_image = False
        
        # Проверяем текст
        if mime_data.hasText():
            text_content = mime_data.text()
            if text_content and text_content.strip():
                has_text = True
        
        # Проверяем изображение
        if mime_data.hasImage():
            image = self.clipboard.image()
            if not image.isNull():
                from PySide6.QtCore import QBuffer, QIODevice
                buffer = QBuffer()
                buffer.open(QIODevice.WriteOnly)
                image.save(buffer, "PNG")
                image_data = buffer.data().data()
                if image_data:
                    has_image = True
        
        # Если нет ни текста, ни изображения - игнорируем
        if not has_text and not has_image:
            return
        
        # Проверка на дубликат
        if self._is_duplicate(text_content, image_data):
            return
        
        # Создаем иерархию: Буфер обмена -> Дата -> Время
        clipboard_root_id = self._get_or_create_clipboard_root()
        date_node_id = self._get_or_create_date_node(clipboard_root_id)
        time_node_id = self._get_or_create_time_node(date_node_id)
        
        # Сохраняем контент в созданную заметку
        if has_text:
            # Сохраняем текст как HTML (простой текст будет экранирован)
            from html import escape
            html_content = f"<p>{escape(text_content)}</p>"
            self.repo.save_note(time_node_id, datetime.now().strftime("%H:%M:%S"), html_content, 0)
        
        if has_image:
            # Добавляем изображение как вложение
            att_id = self.repo.add_attachment(time_node_id, "clipboard_image.png", image_data, "image/png")
            
            # Добавляем ссылку на изображение в body_html если еще нет текста
            if not has_text:
                html_content = f'<img src="noteimg://{att_id}" />'
                self.repo.save_note(time_node_id, datetime.now().strftime("%H:%M:%S"), html_content, 0)
            else:
                # Если есть текст, добавляем изображение после текста
                note_data = self.repo.get_note(time_node_id)
                if note_data:
                    existing_html = note_data[3] or ""
                    html_content = existing_html + f'<br/><img src="noteimg://{att_id}" />'
                    self.repo.save_note(time_node_id, datetime.now().strftime("%H:%M:%S"), html_content, 0)
        
        # Обновляем последнее состояние
        self.last_text = text_content
        self.last_image_data = image_data
        
        # Сигнализируем о создании новой записи
        self.clipboard_changed.emit(time_node_id)
    
    def enable(self):
        """Включить мониторинг."""
        self.clipboard.dataChanged.connect(self._on_clipboard_changed)
    
    def disable(self):
        """Отключить мониторинг."""
        try:
            self.clipboard.dataChanged.disconnect(self._on_clipboard_changed)
        except RuntimeError:
            pass  # Уже отключено
