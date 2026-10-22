import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from media_bot.bot import MediaBot
from media_bot.config import Settings
from media_bot.library import Library


class ManagementTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.bot = MediaBot(Settings('123456:TOKEN'))
        self.bot.library = Library(root / 'library')
        source = root / 'documento.pdf'
        source.write_bytes(b'hello')
        self.file_id = self.bot.library.save_local(source, 42)
        self.path = self.bot.library.root / self.file_id
        self.message = SimpleNamespace(reply_text=AsyncMock(), reply_document=AsyncMock())
        self.update = SimpleNamespace(message=self.message,
            effective_user=SimpleNamespace(id=42), effective_chat=SimpleNamespace(id=42, type='private'))

    def args(self, *args):
        return SimpleNamespace(args=list(args))

    async def request_delete(self):
        await self.bot.delete(self.update, self.args(self.file_id))
        return self.bot.delete_pending[self.bot.key(self.update)][1]

    async def test_rename_changes_search_and_download_name_not_content(self):
        await self.bot.rename(self.update, self.args(self.file_id, 'aula', 'Python.pdf'))
        self.assertEqual(self.bot.library.search(42, 'Python')[0]['name'], 'aula Python.pdf')
        self.assertEqual(self.path.read_bytes(), b'hello')
        await self.bot.retrieve(self.update, self.args(self.file_id))
        self.assertEqual(self.message.reply_document.call_args.kwargs['filename'], 'aula Python.pdf')

    async def test_invalid_names_and_other_owner_cannot_rename(self):
        for name in ('', '../x', 'a/b', 'a\\b', 'bad\nname', 'x' * 201):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.bot.library.rename(42, self.file_id, name)
        self.assertFalse(self.bot.library.rename(99, self.file_id, 'changed.pdf'))
        self.assertEqual(self.bot.library.get(42, self.file_id)['name'], 'documento.pdf')

    async def test_usage_is_per_owner_and_updates_after_deletion(self):
        self.assertEqual(self.bot.library.usage(99), {'count': 0, 'bytes': 0})
        await self.bot.space(self.update, self.args())
        self.assertIn('5 bytes', self.message.reply_text.call_args.args[0])
        code = await self.request_delete()
        await self.bot.confirm_delete(self.update, self.args(code))
        self.assertEqual(self.bot.library.usage(42), {'count': 0, 'bytes': 0})
        self.assertFalse(self.path.exists())

    async def test_delete_requires_correct_confirmation_and_is_single_use(self):
        code = await self.request_delete()
        self.assertTrue(self.path.exists())
        await self.bot.confirm_delete(self.update, self.args('wrong'))
        self.assertTrue(self.path.exists())
        await self.bot.confirm_delete(self.update, self.args(code))
        self.assertFalse(self.path.exists())
        self.assertIsNone(self.bot.library.get(42, self.file_id))
        with patch.object(self.bot.library, 'delete') as delete:
            await self.bot.confirm_delete(self.update, self.args(code))
            delete.assert_not_called()

    async def test_cancel_expiry_and_restart_preserve_file(self):
        code = await self.request_delete()
        await self.bot.cancel_delete(self.update, self.args())
        await self.bot.confirm_delete(self.update, self.args(code))
        self.assertTrue(self.path.exists())
        with patch('media_bot.bot.monotonic', return_value=100):
            code = await self.request_delete()
        with patch('media_bot.bot.monotonic', return_value=221):
            await self.bot.confirm_delete(self.update, self.args(code))
        self.assertTrue(self.path.exists())
        code = await self.request_delete()
        restarted = MediaBot(Settings('123456:TOKEN'))
        restarted.library = self.bot.library
        await restarted.confirm_delete(self.update, self.args(code))
        self.assertTrue(self.path.exists())

    async def test_confirmation_is_bound_to_user_and_chat(self):
        code = await self.request_delete()
        self.update.effective_user.id = 99
        await self.bot.confirm_delete(self.update, self.args(code))
        self.assertTrue(self.path.exists())
        self.assertFalse(self.bot.library.delete(99, self.file_id))
        self.update.effective_user.id = 42
        self.update.effective_chat.id = 123
        await self.bot.confirm_delete(self.update, self.args(code))
        self.assertTrue(self.path.exists())

    async def test_new_request_replaces_old_confirmation(self):
        with patch('media_bot.bot.secrets.token_hex', side_effect=['first', 'second']):
            first = await self.request_delete()
            second = await self.request_delete()
        await self.bot.confirm_delete(self.update, self.args(first))
        self.assertTrue(self.path.exists())
        await self.bot.confirm_delete(self.update, self.args(second))
        self.assertFalse(self.path.exists())

    async def test_unlink_failure_retains_record_and_reports_error(self):
        code = await self.request_delete()
        with patch.object(Path, 'unlink', side_effect=PermissionError('locked')):
            await self.bot.confirm_delete(self.update, self.args(code))
        self.assertTrue(self.path.exists())
        self.assertIsNotNone(self.bot.library.get(42, self.file_id))
        self.assertIn('Não consegui remover', self.message.reply_text.call_args.args[0])

    async def test_missing_file_can_remove_stale_record(self):
        self.path.unlink()
        self.assertTrue(self.bot.library.delete(42, self.file_id))
        self.assertIsNone(self.bot.library.get(42, self.file_id))
        self.assertFalse(self.bot.library.delete(42, '../outside'))

    async def test_group_and_restricted_users_cannot_manage(self):
        for restricted in (False, True):
            self.update.effective_chat.type = 'private' if restricted else 'group'
            self.bot.settings = Settings('123456:TOKEN', frozenset({99}) if restricted else frozenset())
            with patch.object(self.bot.library, 'rename') as rename, \
                 patch.object(self.bot.library, 'usage') as usage, \
                 patch.object(self.bot.library, 'get') as get:
                await self.bot.rename(self.update, self.args(self.file_id, 'new.pdf'))
                await self.bot.space(self.update, self.args())
                await self.bot.delete(self.update, self.args(self.file_id))
                await self.bot.confirm_delete(self.update, self.args('code'))
                await self.bot.cancel_delete(self.update, self.args())
                rename.assert_not_called()
                usage.assert_not_called()
                get.assert_not_called()
        self.assertTrue(self.path.exists())
