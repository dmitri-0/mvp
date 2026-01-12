from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit
from PySide6.QtCore import Qt
import markdown

class MarkdownViewDialog(QDialog):
    """Окно для просмотра (превью) Markdown, отрендеренного в HTML"""
    
    def __init__(self, plain_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Markdown Preview")
        self.resize(1200, 800)  # Увеличен размер окна
        
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
            # 'sane_lists' помогает с корректной вложенностью списков
            extensions = [
                'markdown.extensions.tables',
                'markdown.extensions.fenced_code',
                'markdown.extensions.nl2br',
                'markdown.extensions.sane_lists', 
                'pymdownx.strike',  # Для зачеркнутого текста (требует pymdown-extensions)
                'markdown.extensions.abbr'
            ]
            
            # Если pymdownx недоступен, пробуем встроенный del (если есть в новых версиях) или простой регексп
            # Но лучше использовать стандартный подход через tilde. 
            # Стандартный python-markdown не поддерживает ~~text~~ из коробки без сторонних расширений.
            # Попробуем простейший хак для зачеркивания перед рендерингом, если расширения нет.
            
            # Проверка на наличие расширения pymdownx (обычно нужно ставить отдельно)
            # Если нет, используем простую замену
            try:
                html = markdown.markdown(text, extensions=['pymdownx.strike'])
            except ImportError:
                # Простая замена ~~text~~ на <del>text</del>
                import re
                text = re.sub(r'~~(.*?)~~', r'<del>\1</del>', text)
                html = markdown.markdown(text, extensions=extensions[:4])
            else:
                 # Если импорт прошел (в блоке try был просто тест), рендерим с полным набором (если установлено)
                 # Но так как мы не знаем окружения, лучше использовать безопасный список
                 html = markdown.markdown(text, extensions=extensions[:4])

            
            # Добавляем CSS
            # font-size: 14pt для основного текста
            # margin-left для вложенных списков
            style = """
            <style>
                body { font-family: sans-serif; font-size: 14pt; line-height: 1.6; }
                h1, h2, h3 { color: #ddd; margin-top: 1.5em; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 1em; font-size: 13pt; }
                th, td { border: 1px solid #555; padding: 8px; }
                th { background-color: #333; color: #fff; font-weight: bold; }
                code { background-color: #333; padding: 2px 5px; border-radius: 3px; font-family: 'Consolas', 'Courier New', monospace; font-size: 13pt; }
                pre { background-color: #2b2b2b; padding: 15px; border-radius: 5px; overflow-x: auto; margin: 1em 0; }
                pre code { background-color: transparent; padding: 0; }
                blockquote { border-left: 4px solid #555; padding-left: 1em; color: #bbb; margin-left: 0; }
                
                /* Списки */
                ul, ol { margin-left: 20px; padding-left: 20px; }
                li { margin-bottom: 0.5em; }
                
                del { text-decoration: line-through; color: #888; }
            </style>
            """
            return style + html
            
        except Exception as e:
            return f"<h3>Ошибка рендеринга:</h3><pre>{e}</pre>"
