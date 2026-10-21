import asyncio
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from telegram.error import TelegramError
from yt_dlp.utils import DownloadError
from media_bot.bot import MediaBot, build_application
from media_bot.config import Settings
from media_bot.downloader import download_async, validate_url

""" python -m unittest discover -s tests -v """

class Tests(unittest.IsolatedAsyncioTestCase):
    def test_validation(self):
        self.assertEqual(validate_url('https://youtu.be/a'), 'https://youtu.be/a')
        for url in ['file:///etc/passwd', 'https://youtube.com.evil.test/a', 'http://localhost', 'https://u@youtube.com/a', 'https://youtube.com:invalid', 'https://youtu.be/a https://youtu.be/b']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)

    def test_build(self):
        app = build_application(Settings('123456:TEST_TOKEN'))
        self.assertEqual(len(app.handlers[0]), 7)

    async def test_delivery_and_cleanup(self):
        for case in ['success', 'upload_error', 'download_error', 'too_large']:
            with self.subTest(case=case):
                status = SimpleNamespace(edit_text=AsyncMock())
                msg = SimpleNamespace(reply_text=AsyncMock(return_value=status), reply_document=AsyncMock())
                update = SimpleNamespace(message=msg, effective_chat=SimpleNamespace(id=1), effective_user=SimpleNamespace(id=2))
                folders = []
                async def fake(url, mode, folder, location):
                    folders.append(folder)
                    path = folder / 'media.mp4'
                    path.write_bytes(b'media')
                    (folder / 'partial.part').write_bytes(b'partial')
                    if case == 'download_error':
                        raise DownloadError('failed')
                    return path
                if case == 'upload_error':
                    msg.reply_document.side_effect = TelegramError('offline')
                with (
                    patch('media_bot.bot.download_async', side_effect=fake),
                    patch(
                        'media_bot.bot.MAX_UPLOAD_BYTES',
                        5 if case == 'too_large' else 50_000_000,
                    ),
                    patch('media_bot.bot.Library.save_local') as save_local,
                ):
                    await MediaBot(Settings('123456:TOKEN')).process(
                        update, 'https://youtu.be/a'
                    )

                    if case in ('success', 'upload_error'):
                        save_local.assert_called_once_with(
                        folders[0] / 'media.mp4',
                        2,
                    )
                    else:
                        save_local.assert_not_called()
                            
                self.assertFalse(folders[0].exists())
                self.assertEqual(folders[0].parent, Path(__file__).resolve().parents[1] / 'work')
                self.assertEqual(msg.reply_document.await_count, int(case in ['success', 'upload_error']))

    async def test_audio_once(self):
        status = SimpleNamespace(edit_text=AsyncMock())
        msg = SimpleNamespace(reply_text=AsyncMock(return_value=status), reply_document=AsyncMock())
        update = SimpleNamespace(message=msg, effective_chat=SimpleNamespace(id=1), effective_user=SimpleNamespace(id=2))
        bot = MediaBot(Settings('123456:TOKEN'))
        await bot.audio(update, SimpleNamespace(args=[]))
        await bot.process(update, 'invalid')
        async def fake(url, mode, folder, location):
            path = folder / ('media.mp3' if mode == 'audio' else 'media.mp4')
            path.write_bytes(b'media')
            return path
        with patch('media_bot.bot.download_async', side_effect=fake) as downloader:
            await bot.process(update, 'https://youtu.be/a')
            self.assertEqual(downloader.call_args.args[1], 'audio')
            await bot.process(update, 'https://youtu.be/a')
            self.assertEqual(downloader.call_args.args[1], 'video')
        restricted = MediaBot(Settings('123456:TOKEN', frozenset({99})))
        self.assertFalse(await restricted.authorized(update))

    async def test_cancel_waits_for_worker(self):
        started, finish = threading.Event(), threading.Event()
        def worker(*args):
            started.set()
            finish.wait(5)
            return Path('media.mp4')
        with patch('media_bot.downloader.download', side_effect=worker):
            task = asyncio.create_task(download_async('url', 'video', Path('.')))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 5))
                task.cancel()
                await asyncio.sleep(0.02)
                self.assertFalse(task.done())
            finally:
                finish.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
    
    async def test_search_command(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            message=message,
            effective_chat=SimpleNamespace(id=1, type='private'),
            effective_user=SimpleNamespace(id=42),
        )
        bot = MediaBot(Settings('123456:TOKEN'))

        with patch.object(bot.library, 'search') as search:
            # Sem palavra: explica o uso e não consulta o banco.
            await bot.search(update, SimpleNamespace(args=[]))
            search.assert_not_called()
            message.reply_text.assert_awaited_once_with(
                'Use /buscar seguido de um nome. Exemplo: /buscar final'
            )

            message.reply_text.reset_mock()

            # Com resultado: passa usuário e termo para a biblioteca.
            search.return_value = [
                {'name': 'relatorio-final.pdf', 'size': 100}
            ]
            await bot.search(
                update, SimpleNamespace(args=['relatorio', 'final'])
            )
            search.assert_called_once_with(42, 'relatorio final')
            message.reply_text.assert_awaited_once_with(
                'Arquivos encontrados:\nrelatorio-final.pdf (100 bytes)'
            )

            message.reply_text.reset_mock()
            search.reset_mock()

            # Sem resultado: informa que não encontrou.
            search.return_value = []
            await bot.search(update, SimpleNamespace(args=['inexistente']))
            message.reply_text.assert_awaited_once_with(
                'Nenhum arquivo encontrado.'
            )

            message.reply_text.reset_mock()
            search.reset_mock()

            # Em grupo: não consulta nem mostra os arquivos.
            update.effective_chat.type = 'group'
            await bot.search(update, SimpleNamespace(args=['final']))
            search.assert_not_called()
            message.reply_text.assert_awaited_once_with(
                'Pesquise na conversa privada com o bot.'
            )
if __name__ == '__main__':
    unittest.main()
