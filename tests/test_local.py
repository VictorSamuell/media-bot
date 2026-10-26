import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from media_bot.api import mount_frontend
from media_bot import launcher


class LocalTests(unittest.IsolatedAsyncioTestCase):
    async def test_static_site_does_not_expose_parent_or_mask_api(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            dist = root / 'dist'
            dist.mkdir()
            (dist / 'index.html').write_text('<h1>Media Saver</h1>')
            (root / '.env').write_text('private')
            app = FastAPI()
            mount_frontend(app, dist)
            async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
                self.assertIn('Media Saver',(await client.get('/')).text)
                self.assertEqual((await client.get('/api/missing')).status_code,404)
                self.assertEqual((await client.get('/%2e%2e/.env')).status_code,404)
                self.assertEqual((await client.get('/.env')).status_code,404)

    async def test_launcher_starts_and_stops_owned_services(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            dist = root / 'frontend' / 'dist'
            dist.mkdir(parents=True)
            (dist / 'index.html').write_text('ready')
            runtime = root / '.runtime'
            bot = SimpleNamespace(initialize=AsyncMock(),start=AsyncMock(),stop=AsyncMock(),
                shutdown=AsyncMock(),running=True,updater=SimpleNamespace(
                    start_polling=AsyncMock(),stop=AsyncMock(),running=True))
            server = SimpleNamespace(started=False,should_exit=False)
            async def serve(**kwargs):
                server.started=True
                while not server.should_exit:
                    await asyncio.sleep(.01)
            server.serve=serve
            with patch.multiple(launcher,ROOT=root,RUNTIME=runtime,STATUS=runtime/'instance.json',STOP=runtime/'stop'), \
                 patch('media_bot.config.Settings.load'), patch('media_bot.bot.build_application',return_value=bot), \
                 patch('uvicorn.Server',return_value=server), patch('media_bot.launcher.create_socket') as socket, \
                 patch('media_bot.launcher.webbrowser.open',side_effect=lambda url:launcher.request_stop()):
                await launcher.run()
                bot.initialize.assert_awaited_once()
                bot.updater.start_polling.assert_awaited_once()
                bot.updater.stop.assert_awaited_once()
                bot.stop.assert_awaited_once()
                bot.shutdown.assert_awaited_once()
                socket.return_value.close.assert_called_once()
                self.assertFalse((runtime/'instance.json').exists())

    async def test_busy_port_does_not_start_bot(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'frontend'/'dist').mkdir(parents=True)
            (root/'frontend'/'dist'/'index.html').write_text('ready')
            with patch.object(launcher,'ROOT',root), patch('media_bot.config.Settings.load'), \
                 patch('media_bot.launcher.create_socket') as socket, patch('media_bot.bot.build_application') as build:
                socket.return_value.bind.side_effect=OSError()
                with self.assertRaisesRegex(RuntimeError,'ocupada'):
                    await launcher.run()
                build.assert_not_called()
