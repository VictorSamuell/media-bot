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

class PaginationTests(unittest.IsolatedAsyncioTestCase):
    async def test_pages_filters_sort_and_owner(self):
        from tempfile import TemporaryDirectory
        from media_bot.api import owner, library
        from media_bot.library import Library
        with TemporaryDirectory() as folder:
            store = Library(Path(folder))
            db = store.connect()
            with db:
                for i in range(55):
                    db.execute('INSERT INTO files(id,owner_id,name,size) VALUES (?,?,?,?)',
                               (f'{i:032x}',42, f'Vídeo {i:02d}.mp4' if i != 54 else 'Relatório final.pdf',i))
                db.execute('INSERT INTO files(id,owner_id,name,size) VALUES (?,?,?,?)',('f'*32,99,'Privado.pdf',999))
            db.close()
            app.dependency_overrides[owner] = lambda:42
            app.dependency_overrides[library] = lambda:store
            try:
                async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
                    first=(await client.get('/api/files')).json()
                    second=(await client.get('/api/files?page=2')).json()
                    last=(await client.get('/api/files?page=99')).json()
                    self.assertEqual((len(first['files']),len(second['files']),len(last['files'])),(24,24,7))
                    self.assertEqual((last['page'],last['pages'],last['total']),(3,3,55))
                    self.assertFalse({f['id'] for f in first['files']} & {f['id'] for f in second['files']})
                    self.assertEqual(first['usage'],{'count':55,'bytes':sum(range(55))})
                    result=(await client.get('/api/files?q=relatorio&kind=Documentos&page=3')).json()
                    self.assertEqual((result['total'],result['page']), (1,1))
                    result=(await client.get('/api/files?sort=size')).json()
                    self.assertEqual(result['files'][0]['size'],54)
                    result=(await client.get('/api/files?sort=name&q=video')).json()
                    self.assertEqual(result['files'][0]['name'],'Vídeo 00.mp4')
                    result=(await client.get('/api/files',params={'ids':f'{0:032x},'+ 'f'*32})).json()
                    self.assertEqual(result['total'],1)
                    self.assertEqual((await client.get('/api/files?ids=')).json()['total'],0)
                    for query in ('page=0','page_size=101','sort=oops','kind=oops'):
                        self.assertEqual((await client.get('/api/files?'+query)).status_code,422)
            finally:
                app.dependency_overrides.clear()

class DeleteApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirmation_owner_failure_and_deletion(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from media_bot.api import library, auth_store
        from media_bot.auth import AuthStore
        from media_bot.library import Library
        with TemporaryDirectory() as folder:
            root = Path(folder)
            store = Library(root / 'library')
            source = root / 'file.txt'
            source.write_bytes(b'content')
            own = store.save_local(source,42)
            other = store.save_local(source,99)
            auth = AuthStore(root)
            token,_ = auth.exchange(auth.issue(42))
            app.dependency_overrides[library] = lambda:store
            app.dependency_overrides[auth_store] = lambda:auth
            try:
                async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
                    url = f'/api/files/{own}'
                    headers={'Authorization':'Bearer '+token}
                    self.assertEqual((await client.request('DELETE',url,json={'confirmed':True})).status_code,401)
                    for body,status in [({},400),({'confirmed':False},400),({'confirmed':'true'},422)]:
                        self.assertEqual((await client.request('DELETE',url,headers=headers,json=body)).status_code,status)
                    self.assertTrue((store.root/own).exists())
                    self.assertEqual((await client.request('DELETE',f'/api/files/{other}',headers=headers,json={'confirmed':True})).status_code,404)
                    with patch.object(Path,'unlink',side_effect=PermissionError()):
                        self.assertEqual((await client.request('DELETE',url,headers=headers,json={'confirmed':True})).status_code,503)
                    self.assertIsNotNone(store.get(42,own))
                    self.assertEqual((await client.request('DELETE',url,headers=headers,json={'confirmed':True})).status_code,200)
                    self.assertFalse((store.root/own).exists())
                    self.assertIsNone(store.get(42,own))
                    self.assertTrue((store.root/other).exists())
                    self.assertEqual((await client.get('/api/files',headers=headers)).json()['total'],0)
            finally:
                app.dependency_overrides.clear()
