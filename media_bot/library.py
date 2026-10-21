"""Biblioteca local: metadados em SQLite e arquivos identificados por UUID."""
import sqlite3
"""Biblioteca qque permite copiar arquivos (shutil)"""
import shutil
from pathlib import Path
from uuid import uuid4


class Library:
    def __init__(self, root: Path):
        self.root = root

    def connect(self):
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.root / 'library.sqlite3')
        connection.row_factory = sqlite3.Row
        connection.execute('''CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL,
            name TEXT NOT NULL, size INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        connection.execute('CREATE INDEX IF NOT EXISTS files_owner ON files(owner_id)')
        return connection

    async def save(self, attachment, owner_id: int):
        file_id = uuid4().hex
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / file_id
        try:
            remote = await attachment.get_file()
            await remote.download_to_drive(custom_path=path)
            name = (attachment.file_name or 'documento').replace('\\', '/').rsplit('/', 1)[-1]
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
