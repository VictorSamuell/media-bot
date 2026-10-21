import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from media_bot.library import Library


class LibraryTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistence_and_owner_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            async def download(custom_path):
                custom_path.write_bytes(b'example')
            attachment = SimpleNamespace(file_name='../../notes.pdf', get_file=AsyncMock(
                return_value=SimpleNamespace(download_to_drive=download)))
            identifier = await Library(root).save(attachment, 42)
            reopened = Library(root)
            self.assertEqual(reopened.recent(99), [])
            rows = reopened.recent(42)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['name'], 'notes.pdf')
            self.assertEqual(rows[0]['size'], 7)
            self.assertEqual((root / identifier).read_bytes(), b'example')

    async def test_failed_download_removes_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            async def download(custom_path):
                custom_path.write_bytes(b'partial')
                raise OSError('interrupted')
            attachment = SimpleNamespace(file_name='notes.pdf', get_file=AsyncMock(
                return_value=SimpleNamespace(download_to_drive=download)))
            library = Library(root)
            with self.assertRaises(OSError):
                await library.save(attachment, 42)
            self.assertEqual(list(root.iterdir()), [])
            self.assertEqual(library.recent(42), [])
