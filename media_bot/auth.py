"""Códigos e sessões compartilhados entre bot e API, sem segredos em texto no banco."""
import hashlib
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class AuthStore:
    def __init__(self, root: Path):
        self.root = root

    @contextmanager
    def db(self):
        self.root.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.root / 'auth.sqlite3', timeout=10)
        try:
            db.execute('CREATE TABLE IF NOT EXISTS codes (owner INTEGER PRIMARY KEY, hash TEXT UNIQUE, expires REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS sessions (hash TEXT PRIMARY KEY, owner INTEGER, expires REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS attempts (time REAL)')
            db.commit()
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        finally:
            db.close()

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def issue(self, owner):
        code = secrets.token_hex(8).upper()
        now = time.time()
        with self.db() as db:
            db.execute('DELETE FROM codes WHERE expires <= ?', (now,))
            db.execute('INSERT OR REPLACE INTO codes VALUES (?, ?, ?)', (owner, self.digest(code), now + 300))
        return code

    def exchange(self, code):
        now = time.time()
        with self.db() as db:
            db.execute('DELETE FROM attempts WHERE time <= ?', (now - 60,))
            db.execute('DELETE FROM sessions WHERE expires <= ?', (now,))
            if db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] >= 30:
                return None, 'limited'
            db.execute('INSERT INTO attempts VALUES (?)', (now,))
            row = db.execute('SELECT owner FROM codes WHERE hash = ? AND expires > ?',
                             (self.digest(code.strip().upper()), now)).fetchone()
            if row is None:
                return None, 'invalid'
            db.execute('DELETE FROM codes WHERE owner = ?', row)
            token = secrets.token_urlsafe(32)
            db.execute('INSERT INTO sessions VALUES (?, ?, ?)', (self.digest(token), row[0], now + 7200))
            return token, None

    def owner(self, token):
        with self.db() as db:
            row = db.execute('SELECT owner FROM sessions WHERE hash = ? AND expires > ?',
                             (self.digest(token), time.time())).fetchone()
            return row[0] if row else None

    def revoke(self, token):
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE hash = ?', (self.digest(token),))
