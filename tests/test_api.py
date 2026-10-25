import unittest
import os
import subprocess
import sys
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from media_bot.api import app


class ApiTests(unittest.IsolatedAsyncioTestCase):
    def test_api_import_does_not_load_bot_settings(self):
        # Processo novo impede que um import anterior esconda dependências de inicialização.
        environment = os.environ.copy()
        environment.pop('TELEGRAM_BOT_TOKEN', None)
        result = subprocess.run(
            [sys.executable, '-c',
             'from unittest.mock import patch\n'
             'with patch("media_bot.config.Settings.load", side_effect=RuntimeError("Bot settings must not load")):\n'
             '    from media_bot.api import app\n'
             '    assert any(route.path == "/health" for route in app.routes)\n'],
            cwd=Path(__file__).resolve().parents[1],
            env=environment, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    async def test_health_returns_json(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            response = await client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertEqual(response.headers['content-type'], 'application/json')

class LibraryApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_authorization_listing_and_download(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from media_bot.api import library
        from media_bot.library import Library
        with TemporaryDirectory() as folder:
            root = Path(folder)
            store = Library(root / 'library')
            source = root / 'real.txt'
            source.write_text('conteudo real', encoding='utf-8')
            own = store.save_local(source, 42)
            other = store.save_local(source, 99)
            app.dependency_overrides[library] = lambda: store
            try:
                with patch.dict(os.environ, {'PANEL_OWNER_ID':'42', 'PANEL_ACCESS_KEY':'x'*32}):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                        self.assertEqual((await client.get('/api/files')).status_code, 401)
                        headers = {'Authorization':'Bearer ' + 'x'*32}
                        response = await client.get('/api/files', headers=headers)
                        self.assertEqual([f['id'] for f in response.json()['files']], [own])
                        response = await client.get(f'/api/files/{own}/download', headers=headers)
                        self.assertEqual(response.content, b'conteudo real')
                        self.assertIn('attachment', response.headers['content-disposition'])
                        self.assertEqual((await client.get(f'/api/files/{other}/download', headers=headers)).status_code,404)
                        (store.root / own).unlink()
                        self.assertEqual((await client.get(f'/api/files/{own}/download', headers=headers)).status_code,404)
                        self.assertEqual((await client.get('/api/files/not-a-uuid/download', headers=headers)).status_code,404)
                with patch.dict(os.environ, {'PANEL_OWNER_ID':'', 'PANEL_ACCESS_KEY':''}):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                        self.assertEqual((await client.get('/api/files')).status_code,503)
            finally:
                app.dependency_overrides.clear()
