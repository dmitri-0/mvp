import sqlite3
from datetime import datetime


class NoteRepository:
    """Репозиторий для работы с базой данных заметок"""

    def __init__(self, db_path="notes.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        # Для надежной работы ON DELETE CASCADE в SQLite
        try:
            self.conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                title TEXT NOT NULL,
                body_html TEXT,
                cursor_position INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(parent_id) REFERENCES notes(id) ON DELETE CASCADE
            )
        """)

        # Миграция для старых баз: добавление колонки cursor_position
        try:
            cursor.execute("ALTER TABLE notes ADD COLUMN cursor_position INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует

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
        # Таблица состояния приложения
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.conn.commit()

    def get_all_notes(self):
        """Получить все заметки (id, parent_id, title, body_html, cursor_position, updated_at)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, parent_id, title, body_html, cursor_position, updated_at FROM notes ORDER BY id")
        return cursor.fetchall()

    def get_note(self, note_id: int):
        """Получить одну заметку (id, parent_id, title, body_html, cursor_position, updated_at)"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, parent_id, title, body_html, cursor_position, updated_at FROM notes WHERE id=?",
            (note_id,),
        )
        return cursor.fetchone()

    def save_note(self, note_id, title, body_html, cursor_pos=0):
        """Сохранить изменения в заметке"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE notes SET title=?, body_html=?, cursor_position=?, updated_at=? WHERE id=?
        """, (title, body_html, cursor_pos, datetime.now().isoformat(sep=" "), note_id))
        self.conn.commit()

    def create_note(self, parent_id, title):
        """Создать новую заметку"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO notes(parent_id, title, body_html) VALUES (?, ?, '')
        """, (parent_id, title))
        self.conn.commit()
        return cursor.lastrowid

    def delete_note(self, note_id):
        """Удалить заметку"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.conn.commit()

    def get_note_by_title(self, title, parent_id=None):
        """Найти заметку по заголовку и родителю"""
        cursor = self.conn.cursor()
        if parent_id is None:
            cursor.execute("SELECT id, parent_id, title FROM notes WHERE title=? AND parent_id IS NULL", (title,))
        else:
            cursor.execute("SELECT id, parent_id, title FROM notes WHERE title=? AND parent_id=?", (title, parent_id))
        return cursor.fetchone()

    def get_attachments(self, note_id):
        """Получить вложения заметки (id, name, bytes, mime)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, bytes, mime FROM attachments WHERE note_id=? AND kind='image'", (note_id,))
        return cursor.fetchall()

    def get_attachment(self, attachment_id):
        """Получить вложение по ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, note_id, name, bytes, mime FROM attachments WHERE id=?", (attachment_id,))
        return cursor.fetchone()

    def add_attachment(self, note_id, name, image_bytes, mime):
        """Добавить вложение к заметке"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO attachments(note_id, kind, name, bytes, mime) VALUES (?, 'image', ?, ?, ?)
        """, (note_id, name, image_bytes, mime))
        self.conn.commit()
        return cursor.lastrowid

    def set_state(self, key, value):
        """Сохранить значение состояния"""
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO state(key, value) VALUES (?, ?)", (key, str(value)))
        self.conn.commit()

    def get_state(self, key, default=None):
        """Получить значение состояния"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM state WHERE key=?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    def vacuum(self):
        """Сжатие базы данных (освобождение места на диске)"""
        self.conn.execute("VACUUM")

    def get_last_descendant(self, root_id):
        """
        Найти последнюю (по ID) заметку, которая находится в поддереве указанного корня.
        Предполагается структура Root -> Date -> Time (3 уровня), но ищем просто max(id) среди потомков 2-го уровня.
        """
        cursor = self.conn.cursor()
        # Ищем среди внуков (детей детей корня)
        query = """
            SELECT n.id, n.parent_id, n.title, n.body_html 
            FROM notes n 
            JOIN notes p ON n.parent_id = p.id 
            WHERE p.parent_id = ? 
            ORDER BY n.id DESC 
            LIMIT 1
        """
        cursor.execute(query, (root_id,))
        row = cursor.fetchone()
        
        # Если внуков нет, ищем среди детей
        if not row:
            cursor.execute("SELECT id, parent_id, title, body_html FROM notes WHERE parent_id=? ORDER BY id DESC LIMIT 1", (root_id,))
            row = cursor.fetchone()
            
        return row
