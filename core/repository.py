# core/repository.py
import sqlite3
from datetime import datetime


class NoteRepository:
    """Репозиторий для работы с базой данных заметок"""
    
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
        """Получить все заметки (id, parent_id, title, body_html, updated_at)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, parent_id, title, body_html, updated_at FROM notes ORDER BY id")
        return cursor.fetchall()

    def save_note(self, note_id, title, body_html):
        """Сохранить изменения в заметке"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE notes SET title=?, body_html=?, updated_at=? WHERE id=?
        """, (title, body_html, datetime.now().isoformat(sep=" "), note_id))
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

    def add_attachment(self, note_id, name, image_bytes, mime):
        """Добавить вложение к заметке"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO attachments(note_id, kind, name, bytes, mime) VALUES (?, 'image', ?, ?, ?)
        """, (note_id, name, image_bytes, mime))
        self.conn.commit()
        return cursor.lastrowid
