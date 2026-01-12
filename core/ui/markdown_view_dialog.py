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
            # Using pixels (px) instead of points (pt) often behaves more predictably in Qt's rich text engine.
            # Using font-weight: 600 instead of 'bold' sometimes helps.
            
            style = """
            <style>
                body { 
                    font-family: sans-serif; 
                    font-size: 18px; 
                    line-height: 1.6; 
                    color: #ddd;
                    background-color: #2b2b2b;
                }
                
                /* Force base font size */
                p, ul, ol, li, dl, dt, dd, table, th, td, blockquote {
                    font-size: 18px;
                }
                
                h1 { font-size: 36px; font-weight: 600; color: #fff; margin-top: 20px; margin-bottom: 10px; text-decoration: underline; }
                h2 { font-size: 28px; font-weight: 600; color: #eee; margin-top: 18px; margin-bottom: 9px; }
                h3 { font-size: 24px; font-weight: 600; color: #ddd; margin-top: 16px; margin-bottom: 8px; }
                h4 { font-size: 20px; font-weight: 600; color: #ccc; margin-top: 14px; margin-bottom: 7px; }
                
                table { border-collapse: collapse; width: 100%; margin-bottom: 1em; }
                th, td { border: 1px solid #555; padding: 8px; }
                th { background-color: #444; color: #fff; font-weight: 600; }
                
                code { 
                    background-color: #444; 
                    padding: 2px 5px; 
                    border-radius: 3px; 
                    font-family: 'Courier New', monospace; 
                    font-size: 18px; 
                }
                pre { 
                    background-color: #333; 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin: 1em 0; 
                    font-size: 18px; 
                }
                
                blockquote { 
                    border-left: 4px solid #777; 
                    padding-left: 10px; 
                    color: #aaa; 
                    margin-left: 0; 
                }
                
                ul, ol { margin-left: 20px; padding-left: 20px; }
                li { margin-bottom: 5px; }
                
                del { text-decoration: line-through; color: #888; }
                a { color: #5dade2; text-decoration: none; }
            </style>
            """
            return style + html
            
        except Exception as e:
            return f"<h3>Ошибка рендеринга:</h3><pre>{e}</pre>"
