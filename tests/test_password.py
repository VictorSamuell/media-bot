import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from media_bot.auth import AuthStore


class LocalPasswordTests(unittest.TestCase):
    def test_password_is_hashed_persistent_expires_and_rotation_revokes(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            auth = AuthStore(root)
            self.assertFalse(auth.password_ready())
            with self.assertRaises(ValueError):
                auth.configure_password('short')
            auth.configure_password('a secure password', 42)
            self.assertNotIn(b'a secure password', (root/'auth.sqlite3').read_bytes())
            self.assertTrue(AuthStore(root).password_ready())
            self.assertEqual(auth.exchange_password('incorrect')[1], 'invalid')
            with patch('media_bot.auth.time.time', return_value=1000):
                token, error = auth.exchange_password('a secure password')
                self.assertIsNone(error)
                self.assertEqual(auth.owner(token), 42)
            with patch('media_bot.auth.time.time', return_value=8200):
                self.assertIsNone(auth.owner(token))
            token, _ = auth.exchange_password('a secure password')
            auth.configure_password('a replacement password', 42)
            self.assertIsNone(auth.owner(token))
            self.assertEqual(auth.exchange_password('a secure password')[1], 'invalid')

    def test_password_attempt_limit(self):
        with TemporaryDirectory() as folder:
            auth = AuthStore(Path(folder))
            auth.configure_password('password for local use')
            for _ in range(10):
                self.assertEqual(auth.exchange_password('wrong')[1], 'invalid')
            self.assertEqual(auth.exchange_password('password for local use')[1], 'limited')
