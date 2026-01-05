# main.py
import sys
import threading
import sqlite3
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QAction, QIcon, QPixmap, QImage
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QTextEdit, 
    QSplitter, QSystemTrayIcon, QMenu, QStyle
)
from pynput import keyboard


# === Database Repository ===
class NoteRepository:
    def __init__(self, db_path="notes.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                title TEXT NOT NULL,
                body_html TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(parent_id) REFERENCES notes(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                kind TEXT,
                name TEXT,
                bytes BLOB,
                mime TEXT,
                FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS note_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_note_id INTEGER NOT NULL,
                to_object_type TEXT,
                to_object_id INTEGER,
                FOREIGN KEY(from_note_id) REFERENCES notes(id) ON DELETE CASCADE
            )
        """)
        self.conn.commit()

    def get_all_notes(self):
        """Вернёт список (id, parent_id, title, body_html, updated_at)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, parent_id, title, body_html, updated_at FROM notes ORDER BY id")
        return cursor.fetchall()

    def save_note(self, note_id, title, body_html):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE notes SET title=?, body_html=?, updated_at=? WHERE id=?
        """, (title, body_html, datetime.now().isoformat(sep=" "), note_id))
        self.conn.commit()

    def create_note(self, parent_id, title):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO notes(parent_id, title, body_html) VALUES (?, ?, '')
        """, (parent_id, title))
        self.conn.commit()
        return cursor.lastrowid

    def get_attachments(self, note_id):
        """Список (id, name, bytes, mime)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, bytes, mime FROM attachments WHERE note_id=? AND kind='image'", (note_id,))
        return cursor.fetchall()

    def add_attachment(self, note_id, name, image_bytes, mime):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO attachments(note_id, kind, name, bytes, mime) VALUES (?, 'image', ?, ?, ?)
        """, (note_id, name, image_bytes, mime))
        self.conn.commit()
        return cursor.lastrowid


# === Custom Editor ===
class NoteEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = None
        self.get_current_note_id = None

    def set_context(self, repo, get_note_id_func):
        self.repo = repo
        self.get_current_note_id = get_note_id_func

    def canInsertFromMimeData(self, source):
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage() and self.repo and self.get_current_note_id:
            note_id = self.get_current_note_id()
            if note_id:
                image = source.imageData()
                if isinstance(image, QImage):
                    # Convert QImage to PNG bytes
                    ba = QByteArray()
                    buff = QBuffer(ba)
                    buff.open(QIODevice.WriteOnly)
                    image.save(buff, "PNG")
                    img_bytes = ba.data()
                    
                    # Generate name and save
                    name = f"pasted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    att_id = self.repo.add_attachment(note_id, name, img_bytes, "image/png")
                    
                    # Register resource and insert HTML
                    url = f"noteimg://{att_id}"
                    self.document().addResource(QTextEdit.ImageResource, url, image)
                    self.textCursor().insertHtml(f'<img src="{url}" />')
                    return
        
        super().insertFromMimeData(source)


# === Main Window ===
class MainWindow(QMainWindow):
    def __init__(self, repo: NoteRepository):
        super().__init__()
        self.repo = repo
        self.setWindowTitle("Notes Manager")
        self.resize(1000, 600)

        # Левая панель - дерево заметок
        self.tree_notes = QTreeWidget()
        self.tree_notes.setHeaderLabel("Notes")
        self.tree_notes.currentItemChanged.connect(self.on_note_selected)
        
        # Правая панель - редактор (всегда редактирование)
        self.editor = NoteEditor()
        self.editor.setAcceptRichText(True)
        self.editor.set_context(self.repo, lambda: self.current_note_id)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tree_notes)
        splitter.addWidget(self.editor)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        self.setCentralWidget(splitter)

        # Автосохранение с debounce
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_current_note)
        self.editor.textChanged.connect(lambda: self._save_timer.start(500))

        self.current_note_id = None
        self.load_notes_tree()

    def load_notes_tree(self):
        """Загрузка дерева заметок из БД"""
        self.tree_notes.clear()
        notes = self.repo.get_all_notes()
        
        # Построение дерева (parent_id -> children)
        items_map = {}
        root_items = []
        
        for note_id, parent_id, title, body_html, updated_at in notes:
            item = QTreeWidgetItem([title])
            item.setData(0, Qt.UserRole, note_id)
            items_map[note_id] = item
            
            if parent_id is None:
                root_items.append(item)
            else:
                if parent_id in items_map:
                    items_map[parent_id].addChild(item)
                else:
                    root_items.append(item)  # fallback если родитель не найден
        
        self.tree_notes.addTopLevelItems(root_items)
        
        # Выбрать первую заметку
        if root_items:
            self.tree_notes.setCurrentItem(root_items[0])

    def on_note_selected(self, current_item, previous_item):
        """Переключение на другую заметку"""
        if previous_item and self.current_note_id:
            self.save_current_note()
        
        if not current_item:
            return
        
        note_id = current_item.data(0, Qt.UserRole)
        self.current_note_id = note_id
        
        # Загрузить содержимое заметки
        notes = self.repo.get_all_notes()
        for nid, _, title, body_html, _ in notes:
            if nid == note_id:
                self.editor.blockSignals(True)  # Блокируем сигнал textChanged
                self.editor.setHtml(body_html or "")
                
                # Загрузить картинки в ресурсы документа
                attachments = self.repo.get_attachments(note_id)
                for att_id, name, img_bytes, mime in attachments:
                    if img_bytes:
                        image = QImage.fromData(img_bytes)
                        self.editor.document().addResource(
                            QTextEdit.ImageResource, 
                            f"noteimg://{att_id}", 
                            image
                        )
                
                self.editor.blockSignals(False)
                break

    def save_current_note(self):
        """Сохранение текущей заметки"""
        if not self.current_note_id:
            return
        
        html = self.editor.toHtml()
        current_item = self.tree_notes.currentItem()
        if current_item:
            title = current_item.text(0)
            self.repo.save_note(self.current_note_id, title, html)

    def show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self):
        self.hide()

    def quit_app(self):
        if self.current_note_id:
            self.save_current_note()
        QApplication.instance().quit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide_to_tray()
            event.accept()
        else:
            super().keyPressEvent(event)


# === Tray Controller ===
class TrayController:
    def __init__(self, window: MainWindow):
        self.window = window
        # Используем стандартную иконку, чтобы не было предупреждения "No Icon set"
        icon = window.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon)
        
        menu = QMenu()
        act_toggle = QAction("Show/Hide")
        act_toggle.triggered.connect(self.toggle)
        act_quit = QAction("Quit")
        act_quit.triggered.connect(self.window.quit_app)
        menu.addAction(act_toggle)
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda _: self.toggle())
        self.tray.show()

    def toggle(self):
        if self.window.isVisible():
            self.window.hide_to_tray()
        else:
            self.window.show_and_focus()


# === Hotkey Controller ===
class HotkeySignals(QObject):
    show_signal = Signal()
    hide_signal = Signal()
    quit_signal = Signal()


class HotkeyController:
    def __init__(self, window: MainWindow):
        self.window = window
        self.signals = HotkeySignals()
        self.signals.show_signal.connect(window.show_and_focus)
        self.signals.hide_signal.connect(window.hide_to_tray)
        self.signals.quit_signal.connect(window.quit_app)
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        # Удален глобальный Esc, теперь он обрабатывается в окне
        with keyboard.GlobalHotKeys({
            '<alt>+s': self.signals.show_signal.emit,
            '<shift>+<esc>': self.signals.quit_signal.emit,
        }) as h:
            h.join()


# === Main Entry Point ===
def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Чтобы не закрывалось при hide
    
    repo = NoteRepository("notes.db")
    
    # Создать тестовую заметку если БД пустая
    if not repo.get_all_notes():
        root_id = repo.create_note(None, "Первая заметка")
        repo.create_note(root_id, "Дочерняя заметка")
    
    window = MainWindow(repo)
    tray = TrayController(window)
    hotkeys = HotkeyController(window)
    hotkeys.start()
    
    window.show_and_focus()  # Показываем окно при старте
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
