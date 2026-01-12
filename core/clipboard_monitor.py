from datetime import datetime
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QMimeData
from PySide6.QtGui import QClipboard, QImage
import io


class ClipboardMonitor:
    """Мониторинг буфера обмена (текст и картинки)"""

    def __init__(self, repo, main_window):
        self.repo = repo
        self.main_window = main_window
        self.clipboard = QApplication.clipboard()
        self.last_text = ""
        self.last_image_data = None
        
        # Поллинг буфера каждые 500мс
        self.timer = QTimer()
        self.timer.timeout.connect(self._check_clipboard)
        self.timer.start(500)

    def _check_clipboard(self):
        """Проверка буфера обмена"""
        mime = self.clipboard.mimeData()
        if not mime:
            return

        # Приоритет картинкам
        if mime.hasImage():
            self._handle_image(mime)
        elif mime.hasText():
            self._handle_text(mime)

    def _handle_text(self, mime: QMimeData):
        """Обработка текста из буфера"""
        text = mime.text().strip()
        if not text or text == self.last_text:
            return

        # Проверка на дубликат: сравниваем с последней записью в Буфер обмена
        clipboard_root = self._get_or_create_clipboard_root()
        last_entry = self.repo.get_last_descendant(clipboard_root)
        
        if last_entry:
            last_html = last_entry[3] or ""
            # Упрощенное сравнение: просто проверяем, есть ли текст в HTML
            if text in last_html:
                self.last_text = text
                return

        self.last_text = text
        self._create_clipboard_entry(text, is_image=False)

    def _handle_image(self, mime: QMimeData):
        """Обработка картинки из буфера"""
        image = self.clipboard.image()
        if image.isNull():
            return

        # Конвертируем в байты для сравнения
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        image_data = buffer.getvalue()

        # Проверка на дубликат
        if image_data == self.last_image_data:
            return

        # Проверка с последней записью
        clipboard_root = self._get_or_create_clipboard_root()
        last_entry = self.repo.get_last_descendant(clipboard_root)
        
        if last_entry:
            attachments = self.repo.get_attachments(last_entry[0])
            if attachments:
                # Сравниваем последнее вложение
                last_att_bytes = attachments[-1][2]
                if image_data == last_att_bytes:
                    self.last_image_data = image_data
                    return

        self.last_image_data = image_data
        self._create_clipboard_entry(image, is_image=True, image_data=image_data)

    def _get_or_create_clipboard_root(self):
        """Получить или создать корневую запись 'Буфер обмена'"""
        root = self.repo.get_note_by_title("Буфер обмена")
        if not root:
            root_id = self.repo.create_note(None, "Буфер обмена")
        else:
            root_id = root[0]
        return root_id

    def _create_clipboard_entry(self, content, is_image=False, image_data=None):
        """Создать запись в иерархии: Буфер обмена -> дата -> время"""
        clipboard_root_id = self._get_or_create_clipboard_root()

        # Дата (ГГ.ММ.ДД)
        date_str = datetime.now().strftime("%y.%m.%d")
        date_note = self.repo.get_note_by_title(date_str, clipboard_root_id)
        if not date_note:
            date_note_id = self.repo.create_note(clipboard_root_id, date_str)
        else:
            date_note_id = date_note[0]

        # Время (ЧЧ.ММ.СС)
        time_str = datetime.now().strftime("%H:%M:%S")
        time_note_id = self.repo.create_note(date_note_id, time_str)

        if is_image:
            # Добавляем картинку как вложение
            att_id = self.repo.add_attachment(
                time_note_id,
                f"clipboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                image_data,
                "image/png"
            )
            # Создаем HTML со ссылкой на картинку
            html = f'<img src="noteimg://{att_id}"/>'
            self.repo.save_note(time_note_id, time_str, html)
        else:
            # Сохраняем текст как полное тело заметки
            # Преобразуем \n в <br> для HTML
            html_content = content.replace("\n", "<br>")
            self.repo.save_note(time_note_id, time_str, html_content)

        # Обновляем дерево в главном окне
        if self.main_window:
            self.main_window.load_notes_tree()
