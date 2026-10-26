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
        from media_bot.api import library, auth_store
        from media_bot.auth import AuthStore
        from media_bot.library import Library
        with TemporaryDirectory() as folder:
            root = Path(folder)
            store = Library(root / 'library')
            source = root / 'real.txt'
            source.write_text('conteudo real', encoding='utf-8')
            own = store.save_local(source, 42)
            other = store.save_local(source, 99)
            app.dependency_overrides[library] = lambda: store
            auth = AuthStore(root)
            app.dependency_overrides[auth_store] = lambda: auth
            session, _ = auth.exchange(auth.issue(42))
            try:
                with patch.dict(os.environ, {'PANEL_OWNER_ID':'42', 'PANEL_ACCESS_KEY':'x'*32}):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                        self.assertEqual((await client.get('/api/files')).status_code, 401)
                        headers = {'Authorization':'Bearer ' + session}
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
                        self.assertEqual((await client.get('/api/files')).status_code,401)
            finally:
                app.dependency_overrides.clear()

    async def test_rename_persists_validates_and_isolates_owner(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from media_bot.api import library, auth_store
        from media_bot.auth import AuthStore
        from media_bot.library import Library
        with TemporaryDirectory() as folder:
            root = Path(folder)
            store = Library(root / 'library')
            source = root / 'original.txt'
            source.write_bytes(b'original content')
            own = store.save_local(source, 42)
            other = store.save_local(source, 99)
            app.dependency_overrides[library] = lambda: store
            auth = AuthStore(root)
            app.dependency_overrides[auth_store] = lambda: auth
            session, _ = auth.exchange(auth.issue(42))
            try:
                with patch.dict(os.environ, {'PANEL_OWNER_ID':'42', 'PANEL_ACCESS_KEY':'x'*32}):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                        headers = {'Authorization':'Bearer ' + session}
                        url = f'/api/files/{own}'
                        self.assertEqual((await client.patch(url, json={'name':'blocked.txt'})).status_code,401)
                        for name in ('', '   ', '../escape.txt', 'a/b.txt', 'a'*201):
                            with self.subTest(name=name):
                                self.assertEqual((await client.patch(url, headers=headers, json={'name':name})).status_code,400)
                        self.assertEqual((await client.patch(url, headers=headers, json={'name':123})).status_code,422)
                        for identifier in (other, '0'*32, 'invalid'):
                            self.assertEqual((await client.patch(f'/api/files/{identifier}', headers=headers, json={'name':'changed.txt'})).status_code,404)
                        self.assertEqual(store.get(99, other)['name'], 'original.txt')
                        response = await client.patch(url, headers=headers, json={'name':'  novo nome.txt  '})
                        self.assertEqual(response.status_code,200)
                        self.assertEqual(response.json()['name'],'novo nome.txt')
                        reopened = Library(store.root)
                        self.assertEqual(reopened.search(42, 'novo nome')[0]['id'],own)
                        self.assertEqual(reopened.get(42,own)['name'],'novo nome.txt')
                        self.assertEqual((await client.get('/api/files', headers=headers)).json()['files'][0]['name'],'novo nome.txt')
                        download = await client.get(url+'/download', headers=headers)
                        self.assertEqual(download.content,b'original content')
                        self.assertIn('novo%20nome.txt',download.headers['content-disposition'])
            finally:
                app.dependency_overrides.clear()

class CorsTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_configured_origin_can_preflight(self):
        from unittest.mock import patch
        from media_bot.api import create_app
        with patch.dict(os.environ, {'PANEL_ALLOWED_ORIGINS':'https://panel.pages.dev'}):
            application = create_app()
        async with AsyncClient(transport=ASGITransport(app=application), base_url='http://test') as client:
            for origin, expected in [('https://panel.pages.dev',200),('https://other.pages.dev',400)]:
                response = await client.options('/api/files',headers={
                    'Origin':origin, 'Access-Control-Request-Method':'PATCH',
                    'Access-Control-Request-Headers':'authorization,content-type'})
                self.assertEqual(response.status_code,expected)
                self.assertEqual(response.headers.get('access-control-allow-origin'),origin if expected==200 else None)
        with patch.dict(os.environ, {'PANEL_ALLOWED_ORIGINS':'*'}):
            with self.assertRaises(ValueError):
                create_app()
