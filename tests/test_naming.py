import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from media_bot.bot import MediaBot
from media_bot.config import Settings

class NamingTests(unittest.IsolatedAsyncioTestCase):
    def update(self, user=2, chat=1, text='Minha aula'):
        return SimpleNamespace(effective_user=SimpleNamespace(id=user),
            effective_chat=SimpleNamespace(id=chat, type='private'),
            message=SimpleNamespace(text=text, reply_text=AsyncMock(),
                document=SimpleNamespace(file_name='original.pdf',file_size=100)))

    async def test_link_waits_and_preserves_audio_mode(self):
        bot = MediaBot(Settings('token'))
        update = self.update()
        bot.process = AsyncMock()
        await bot.audio(update, SimpleNamespace(args=['https://youtu.be/a']))
        bot.process.assert_not_awaited()
        await bot.text(update, None)
        bot.process.assert_awaited_once_with(update,'https://youtu.be/a','Minha aula.mp3','audio')
        self.assertFalse(bot.name_pending)

    async def test_document_validation_isolation_and_original(self):
        bot = MediaBot(Settings('token'))
        bot.library.save = AsyncMock()
        update = self.update(text='../escape')
        await bot.document(update,None)
        bot.library.save.assert_not_awaited()
        await bot.text(update,None)
        self.assertIn((1,2),bot.name_pending)
        await bot.original_name(self.update(user=3),None)
        await bot.original_name(self.update(chat=4),None)
        bot.library.save.assert_not_awaited()
        await bot.original_name(update,None)
        bot.library.save.assert_awaited_once_with(update.message.document,2,name=None)

    async def test_custom_document_cancel_expiry_and_duplicate(self):
        bot = MediaBot(Settings('token'))
        bot.library.save = AsyncMock()
        update = self.update()
        await bot.document(update,None)
        first = bot.name_pending[(1,2)]
        await bot.document(update,None)
        self.assertEqual(bot.name_pending[(1,2)],first)
        await bot.text(update,None)
        bot.library.save.assert_awaited_once_with(update.message.document,2,name='Minha aula.pdf')
        bot.library.save.reset_mock()
        await bot.document(update,None)
        await bot.cancel_delete(update,None)
        self.assertFalse(bot.name_pending)
        await bot.document(update,None)
        with patch('media_bot.bot.monotonic',return_value=first[3]+1000):
            await bot.text(update,None)
        bot.library.save.assert_not_awaited()
        self.assertFalse(bot.name_pending)

    def test_name_validation_and_extension(self):
        self.assertEqual(MediaBot.chosen_name('aula.mp4','media.mp4'),'aula.mp4')
        for name in ('', ' ', '..', 'a/b', 'a\\b', 'x'*201):
            with self.subTest(name=name), self.assertRaises(ValueError):
                MediaBot.chosen_name(name,'media.mp4')
