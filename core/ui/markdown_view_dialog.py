from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser
from PySide6.QtGui import QFont, QTextDocument
import markdown
import re

PREVIEW_VERSION = "2026-01-12.2223"

class MarkdownViewDialog(QDialog):
    """Окно для просмотра (превью) Markdown, отрендеренного в HTML"""

    def __init__(self, plain_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Markdown Preview v{PREVIEW_VERSION}")
        self.resize(1200, 800)

        layout = QVBoxLayout(self)

        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)

        html_body, css = self._render_markdown(plain_text)

        doc = QTextDocument(self.viewer)
        doc.setDefaultStyleSheet(css)
        doc.setDefaultFont(QFont("Segoe UI", 12))
        doc.setHtml(html_body)
        self.viewer.setDocument(doc)

        layout.addWidget(self.viewer)

    def _render_markdown(self, text: str) -> tuple[str, str]:
        """Рендеринг Markdown в HTML и возврат CSS отдельной строкой."""

        # 1) Strike: исправил регулярку (убрал лишние экранирования) и тег на <s> (более надежен в Qt)
        # Было: r"<del>\\1</del>" -> Стало: r"<s>\1</s>"
        text = re.sub(r"~~(.*?)~~", r"<s>\1</s>", text)

        # 2) Чекбоксы:
        # [x] -> ☑ (BALLOT BOX WITH CHECK)
        # [ ] -> ☐ (BALLOT BOX)
        # Делаем это ДО markdown рендера, чтобы списки не сломались, но нужно аккуратно.
        # Лучше всего заменить именно паттерн в начале строки списка или внутри текста.
        
        text = text.replace("[x]", "☑")
        text = text.replace("[ ]", "☐")

        # 3) HTML
        html = markdown.markdown(
            text,
            extensions=[
                "markdown.extensions.tables",
                "markdown.extensions.fenced_code",
                "markdown.extensions.nl2br",
                "markdown.extensions.sane_lists",
            ],
        )

        # 4) Принудительно ставим inline-стиль в заголовки
        header_styles = {
            "h1": "font-size: 36px; font-weight: 600;",
            "h2": "font-size: 30px; font-weight: 600;",
            "h3": "font-size: 26px; font-weight: 600;",
            "h4": "font-size: 22px; font-weight: 600;",
            "h5": "font-size: 20px; font-weight: 600;",
            "h6": "font-size: 18px; font-weight: 600;",
        }
        for tag, style in header_styles.items():
            html = re.sub(
                rf"<{tag}(\s[^>]*)?>",
                lambda m: f"<{tag}{m.group(1) or ''} style=\"{style}\">",
                html,
            )

        banner = (
            f"<div style='color:#888; font-size:12px; margin-bottom:10px;'>"
            f"Preview engine: {PREVIEW_VERSION}"
            f"</div>"
        )

        # CSS: добавил s { text-decoration: line-through }
        css = """
            body { background-color: #2b2b2b; color: #ddd; font-family: 'Segoe UI', sans-serif; font-size: 18px; line-height: 1.6; }
            p, ul, ol, li, table, th, td, blockquote { font-size: 18px; }

            h1 { margin: 18px 0 10px 0; }
            h2 { margin: 16px 0 9px 0; }
            h3 { margin: 14px 0 8px 0; }

            table { border-collapse: collapse; width: 100%; margin: 10px 0 16px 0; }
            th, td { border: 1px solid #555; padding: 8px; }
            th { background-color: #444; color: #fff; font-weight: 600; }

            code { background-color: #444; padding: 2px 5px; border-radius: 3px; font-family: 'Consolas','Courier New',monospace; font-size: 18px; color: #e0e0e0; }
            pre { background-color: #333; padding: 15px; border-radius: 5px; margin: 10px 0 16px 0; font-size: 18px; color: #e0e0e0; }

            blockquote { border-left: 4px solid #777; padding-left: 10px; color: #aaa; margin-left: 0; }

            ul, ol { margin-left: 22px; padding-left: 22px; }
            li { margin-bottom: 5px; }

            del, s { text-decoration: line-through; color: #888; }
            a { color: #5dade2; text-decoration: none; }
        """

        return banner + html, css
