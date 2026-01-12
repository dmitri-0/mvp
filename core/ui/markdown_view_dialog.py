from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit
from PySide6.QtCore import Qt
import markdown
import re

class MarkdownViewDialog(QDialog):
    """Окно для просмотра (превью) Markdown, отрендеренного в HTML"""
    
    def __init__(self, plain_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Markdown Preview")
        self.resize(1200, 800)
        
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
            extensions = [
                'markdown.extensions.tables',
                'markdown.extensions.fenced_code',
                'markdown.extensions.nl2br',
                'markdown.extensions.sane_lists', 
                'pymdownx.strike',
                'markdown.extensions.abbr'
            ]
            
            try:
                html = markdown.markdown(text, extensions=['pymdownx.strike'])
            except ImportError:
                text = re.sub(r'~~(.*?)~~', r'<del>\1</del>', text)
                html = markdown.markdown(text, extensions=extensions[:4])
            else:
                 html = markdown.markdown(text, extensions=extensions[:4])

            # FORCE INLINE STYLES
            # Qt's CSS engine often ignores stylesheet rules for headers when using setHtml.
            # We will inject inline styles directly into tags using regex.
            
            header_styles = {
                'h1': 'font-size: 36px; font-weight: 600; margin-top: 20px; color: #ffffff; text-decoration: underline;',
                'h2': 'font-size: 30px; font-weight: 600; margin-top: 18px; color: #eeeeee;',
                'h3': 'font-size: 26px; font-weight: 600; margin-top: 16px; color: #dddddd;',
                'h4': 'font-size: 22px; font-weight: 600; margin-top: 14px; color: #cccccc;',
                'h5': 'font-size: 20px; font-weight: 600; margin-top: 12px; color: #cccccc;',
                'h6': 'font-size: 18px; font-weight: 600; margin-top: 12px; color: #cccccc;',
            }

            for tag, style in header_styles.items():
                # Replace <hX> with <hX style="...">
                html = re.sub(f'<{tag}>', f'<{tag} style="{style}">', html)

            # Global styles for body and other elements via CSS block (works better for general tags)
            # But we also wrap everything in a div with explicit font size
            base_style = """
            <style>
                body { background-color: #2b2b2b; color: #ddd; font-family: sans-serif; font-size: 18px; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 1em; font-size: 18px; }
                th, td { border: 1px solid #555; padding: 8px; }
                th { background-color: #444; color: #fff; font-weight: 600; }
                code { background-color: #444; padding: 2px 5px; border-radius: 3px; font-family: 'Courier New', monospace; font-size: 18px; color: #e0e0e0; }
                pre { background-color: #333; padding: 15px; border-radius: 5px; margin: 1em 0; font-size: 18px; color: #e0e0e0; }
                blockquote { border-left: 4px solid #777; padding-left: 10px; color: #aaa; margin-left: 0; }
                ul, ol { margin-left: 20px; padding-left: 20px; font-size: 18px; }
                li { margin-bottom: 5px; }
                p { font-size: 18px; margin-bottom: 10px; }
                del { text-decoration: line-through; color: #888; }
                a { color: #5dade2; text-decoration: none; }
            </style>
            """
            
            return base_style + html
            
        except Exception as e:
            return f"<h3>Ошибка рендеринга:</h3><pre>{e}</pre>"
