from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit
from PySide6.QtCore import Qt
import markdown

class MarkdownViewDialog(QDialog):
    """Окно для просмотра (превью) Markdown, отрендеренного в HTML"""
    
    def __init__(self, plain_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Markdown Preview")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        self.viewer = QTextEdit()
        self.viewer.setReadOnly(True)
        
        # Конвертация Markdown -> HTML
        html_content = self._render_markdown(plain_text)
        self.viewer.setHtml(html_content)
        
        layout.addWidget(self.viewer)
        
    def _render_markdown(self, text: str) -> str:
        """Рендеринг Markdown в HTML с поддержкой таблиц и кода"""
        try:
            # Подключаем расширения: таблицы, блоки кода
            extensions = [
                'markdown.extensions.tables',
                'markdown.extensions.fenced_code',
                'markdown.extensions.nl2br' # Переносы строк как <br>
            ]
            
            html = markdown.markdown(text, extensions=extensions)
            
            # Добавляем базовый CSS для таблиц и кода чтобы выглядело прилично
            style = """
            <style>
                table { border-collapse: collapse; width: 100%; margin-bottom: 1em; }
                th, td { border: 1px solid #555; padding: 6px; }
                th { background-color: #333; color: #fff; }
                code { background-color: #333; padding: 2px 4px; border-radius: 3px; font-family: monospace; }
                pre { background-color: #333; padding: 10px; border-radius: 5px; overflow-x: auto; }
                blockquote { border-left: 4px solid #555; padding-left: 1em; color: #aaa; }
            </style>
            """
            return style + html
            
        except Exception as e:
            return f"<h3>Ошибка рендеринга:</h3><pre>{e}</pre>"
