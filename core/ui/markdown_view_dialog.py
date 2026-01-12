from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit
from PySide6.QtCore import Qt
import markdown

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
                import re
                text = re.sub(r'~~(.*?)~~', r'<del>\1</del>', text)
                html = markdown.markdown(text, extensions=extensions[:4])
            else:
                 html = markdown.markdown(text, extensions=extensions[:4])

            # CSS
            # Qt's HTML engine is limited (HTML4/CSS2.1 subset).
            # It often ignores body font-size inheritance in lists/tables.
            # We must explicitly set font-size for specific tags.
            style = """
            <style>
                body { 
                    font-family: sans-serif; 
                    font-size: 14pt; 
                    line-height: 1.6; 
                    color: #ddd;
                    background-color: #2b2b2b;
                }
                
                /* Explicit inheritance fix for Qt */
                p, ul, ol, li, dl, dt, dd, table, th, td, blockquote {
                    font-size: 14pt;
                }
                
                h1 { font-size: 24pt; color: #fff; margin-top: 1em; }
                h2 { font-size: 20pt; color: #eee; margin-top: 1em; }
                h3 { font-size: 18pt; color: #ddd; margin-top: 1em; }
                
                table { border-collapse: collapse; width: 100%; margin-bottom: 1em; }
                th, td { border: 1px solid #555; padding: 8px; }
                th { background-color: #444; color: #fff; font-weight: bold; }
                
                /* Code blocks */
                code { 
                    background-color: #444; 
                    padding: 2px 5px; 
                    border-radius: 3px; 
                    font-family: 'Consolas', 'Courier New', monospace; 
                    font-size: 14pt; /* Explicitly match body size */
                }
                pre { 
                    background-color: #333; 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin: 1em 0; 
                    font-size: 14pt; /* Ensure block code is also big */
                }
                
                blockquote { 
                    border-left: 4px solid #777; 
                    padding-left: 1em; 
                    color: #aaa; 
                    margin-left: 0; 
                }
                
                ul, ol { margin-left: 20px; padding-left: 20px; }
                li { margin-bottom: 0.5em; }
                
                del { text-decoration: line-through; color: #888; }
                a { color: #5dade2; text-decoration: none; }
            </style>
            """
            return style + html
            
        except Exception as e:
            return f"<h3>Ошибка рендеринга:</h3><pre>{e}</pre>"
