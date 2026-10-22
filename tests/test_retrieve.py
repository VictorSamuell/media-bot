import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram.error import TelegramError

from media_bot.bot import MediaBot
from media_bot.config import Settings
from media_bot.library import Library


class RetrieveTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.bot = MediaBot(Settings('123456:TOKEN'))
        self.bot.library = Library(root / 'library')
        source = root / 'documento.pdf'
        source.write_bytes(b'documento de teste')
        self.file_id = self.bot.library.save_local(source, 42)
        self.path = self.bot.library.root / self.file_id
        self.message = SimpleNamespace(reply_text=AsyncMock(), reply_document=AsyncMock())
        self.update = SimpleNamespace(message=self.message,
            effective_user=SimpleNamespace(id=42),
            effective_chat=SimpleNamespace(id=1, type='private'))
        self.context = SimpleNamespace(args=[self.file_id])

    async def test_resends_original_content_and_preserves_copy(self):
        async def send(**kwargs):
            self.assertEqual(kwargs['filename'], 'documento.pdf')
            self.assertEqual(kwargs['document'].read(), b'documento de teste')
        self.message.reply_document.side_effect = send
        await self.bot.retrieve(self.update, self.context)
        self.message.reply_document.assert_awaited_once()
        self.assertTrue(self.path.exists())

    async def test_other_owner_and_unknown_id_have_same_response(self):
        self.update.effective_user.id = 99
        await self.bot.retrieve(self.update, self.context)
        first = self.message.reply_text.call_args
        self.context.args = ['0' * 32]
        await self.bot.retrieve(self.update, self.context)
        self.assertEqual(first, self.message.reply_text.call_args)
        self.message.reply_document.assert_not_awaited()

    async def test_group_and_invalid_arguments_never_query_library(self):
        with patch.object(self.bot.library, 'get') as get:
            self.update.effective_chat.type = 'group'
            await self.bot.retrieve(self.update, self.context)
            self.update.effective_chat.type = 'private'
            for args in ([], ['../.env'], ['a' * 32, 'extra']):
                self.context.args = args
                await self.bot.retrieve(self.update, self.context)
            get.assert_not_called()
        self.message.reply_document.assert_not_awaited()

    async def test_missing_file_explains_problem(self):
        self.path.unlink()
        await self.bot.retrieve(self.update, self.context)
        self.message.reply_text.assert_awaited_once_with(
            'O registro existe, mas o arquivo não está mais no armazenamento.')
        self.message.reply_document.assert_not_awaited()

    async def test_send_failure_keeps_file(self):
        self.message.reply_document.side_effect = TelegramError('offline')
        await self.bot.retrieve(self.update, self.context)
        self.assertTrue(self.path.exists())
        self.message.reply_text.assert_awaited_once_with(
            'O envio falhou. O arquivo continua salvo; tente novamente.')

    async def test_size_limit_blocks_send(self):
        with patch('media_bot.bot.MAX_UPLOAD_BYTES', 1):
            await self.bot.retrieve(self.update, self.context)
        self.message.reply_document.assert_not_awaited()
        self.assertTrue(self.path.exists())

    async def test_listing_exposes_retrieval_command(self):
        await self.bot.files(self.update, SimpleNamespace(args=[]))
        self.assertIn('/baixar ' + self.file_id, self.message.reply_text.call_args.args[0])

    async def test_restricted_user_cannot_retrieve(self):
        self.bot.settings = Settings('123456:TOKEN', frozenset({99}))
        with patch.object(self.bot.library, 'get') as get:
            await self.bot.retrieve(self.update, self.context)
            get.assert_not_called()
        self.message.reply_document.assert_not_awaited()
