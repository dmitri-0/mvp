from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit
from PySide6.QtCore import Qt
from markdownify import markdownify as md
import re

class MarkdownViewDialog(QDialog):
    """Окно для просмотра содержимого заметки в формате Markdown"""
    
    def __init__(self, html_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Markdown View")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        self.viewer = QTextEdit()
        self.viewer.setReadOnly(True)
        
        # Конвертация
        markdown_text = self._html_to_markdown(html_content)
        self.viewer.setPlainText(markdown_text)
        
        layout.addWidget(self.viewer)
        
    def _html_to_markdown(self, html_content: str) -> str:
        """Конвертация HTML в Markdown"""
        try:
            # Обрабатываем изображения noteimg://
            html_content = re.sub(
                r'<img[^>]*src="noteimg://([0-9\.]+)"[^>]*>',
                r'![Image](noteimg://\1)',
                html_content
            )
            return md(html_content, heading_style="ATX")
        except Exception as e:
            return f"Ошибка конвертации: {e}"
