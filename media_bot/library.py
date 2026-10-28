"""Biblioteca local: metadados em SQLite e arquivos identificados por UUID."""
import sqlite3
"""Biblioteca qque permite copiar arquivos (shutil)"""
import shutil
import re
import unicodedata
from pathlib import Path
from uuid import uuid4


def normalize_search(text: str) -> str:
    """Normaliza apenas para comparação, preservando o nome original salvo."""
    return ''.join(
        character for character in unicodedata.normalize('NFD', text.casefold())
        if unicodedata.category(character) != 'Mn'
    )


class Library:
    def rename(self, owner_id: int, file_id: str, name: str):
        name = name.strip()
        if not name or len(name) > 200 or name in ('.', '..') or any(
            not c.isprintable() or c in '/\\:*?"<>|' for c in name
        ):
            raise ValueError('Use um nome de 1 a 200 caracteres, sem barras ou caracteres especiais de caminho.')
        db = self.connect()
        try:
            with db:
                return db.execute('UPDATE files SET name = ? WHERE owner_id = ? AND id = ?',
                                  (name, owner_id, file_id)).rowcount == 1
        finally:
            db.close()

    def set_favorite(self, owner_id: int, file_id: str, enabled: bool):
        db = self.connect()
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT id FROM files WHERE id = ? AND owner_id = ?',
                              (file_id, owner_id)).fetchone() is None:
                    return False
                if enabled:
                    db.execute('INSERT OR IGNORE INTO favorites(file_id) VALUES (?)', (file_id,))
                else:
                    db.execute('DELETE FROM favorites WHERE file_id = ?', (file_id,))
                return True
        finally:
            db.close()

    def usage(self, owner_id: int):
        db = self.connect()
        try:
            row = db.execute('SELECT COUNT(*) AS count, COALESCE(SUM(size), 0) AS bytes '
                             'FROM files WHERE owner_id = ?', (owner_id,)).fetchone()
            return dict(row)
        finally:
            db.close()

    def delete(self, owner_id: int, file_id: str):
        if not re.fullmatch(r'[0-9a-f]{32}', file_id):
            return False
        db = self.connect()
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT id FROM files WHERE owner_id = ? AND id = ?',
                                 (owner_id, file_id)).fetchone()
                if row is None:
                    return False
                # Se a remoção falhar, a transação mantém o registro para tentar novamente.
                (self.root / file_id).unlink(missing_ok=True)
                db.execute('DELETE FROM files WHERE owner_id = ? AND id = ?', (owner_id, file_id))
                return True
        finally:
            db.close()

    def __init__(self, root: Path):
        self.root = root

    def connect(self):
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.root / 'library.sqlite3')
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute('''CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL,
            name TEXT NOT NULL, size INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        connection.execute('CREATE INDEX IF NOT EXISTS files_owner ON files(owner_id)')
        connection.execute("""CREATE TABLE IF NOT EXISTS favorites (
            file_id TEXT PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE
        )""")
        return connection

    async def save(self, attachment, owner_id: int, name: str | None = None):
        file_id = uuid4().hex
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / file_id
        try:
            remote = await attachment.get_file()
            await remote.download_to_drive(custom_path=path)
            name = (name or attachment.file_name or 'documento').replace('\\', '/').rsplit('/', 1)[-1]
            name = ''.join(c for c in name if c.isprintable())[:200] or 'documento'
            db = self.connect()
            try:
                with db:
                    db.execute('INSERT INTO files(id, owner_id, name, size) VALUES (?, ?, ?, ?)',
                               (file_id, owner_id, name, path.stat().st_size))
            finally:
                db.close()
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return file_id
    
    def save_local(self, source: Path, owner_id: int):
        file_id = uuid4().hex
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / file_id

        try:
            shutil.copyfile(source, destination)

            db = self.connect()
            try:
                with db:
                    db.execute(
                        'INSERT INTO files(id, owner_id, name, size) VALUES (?, ?, ?, ?)',
                        (
                            file_id,
                            owner_id,
                            source.name,
                            destination.stat().st_size,
                        ),
                    )
            finally:
                db.close()
        except BaseException:
            destination.unlink(missing_ok=True)
            raise

        return file_id
    def recent(self, owner_id: int):
        db = self.connect()
        try:
            return db.execute('SELECT * FROM files WHERE owner_id = ? '
                              'ORDER BY created_at DESC, rowid DESC LIMIT 10', (owner_id,)).fetchall()
        finally:
            db.close()
            
    def search(self, owner_id: int, term: str):
        term = normalize_search(term.strip())
        if not term:
            return []
        db = self.connect()
        try:
            db.create_function('normalize_search', 1, normalize_search, deterministic=True)
            return db.execute(
                'SELECT * FROM files '
                'WHERE owner_id = ? AND instr(normalize_search(name), ?) > 0 '
                'ORDER BY created_at DESC, rowid DESC LIMIT 10',
                (owner_id, term),
            ).fetchall()
        finally:
            db.close()
            
    def get(self, owner_id: int, file_id: str):
        db = self.connect()
        try:
            return db.execute(
                'SELECT * FROM files WHERE owner_id = ? AND id = ?',
                (owner_id, file_id),
            ).fetchone()
        finally:
            db.close()
