import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace
from httpx import ASGITransport, AsyncClient
from media_bot.api import app, library, auth_store
from media_bot.auth import AuthStore
from media_bot.library import Library
from media_bot import launcher


class DirectMediaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Library(self.root/'library')
        self.auth = AuthStore(self.root/'auth')
        self.auth.configure_password('my local password')
        app.dependency_overrides[library] = lambda:self.store
        app.dependency_overrides[auth_store] = lambda:self.auth
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url='http://test')
        response = await self.client.post('/api/auth/password', json={'password':'my local password'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.headers = {'Authorization':'Bearer '+response.json()['token']}

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        self.tmp.cleanup()

    async def test_upload_ownership_limit_and_bad_names(self):
        self.assertEqual((await self.client.post('/api/import/file?name=song.mp3', content=b'music')).status_code,401)
        for name in ['../outside.mp3', 'bad/name.mp3', '..']:
            response = await self.client.post('/api/import/file',params={'name':name},content=b'music', headers=self.headers)
            self.assertEqual(response.status_code,400)
        self.assertEqual((await self.client.post('/api/import/file?name=empty',content=b'',headers=self.headers)).status_code,400)
        with patch('media_bot.ingest.MAX_UPLOAD_BYTES',5):
            response = await self.client.post('/api/import/file?name=big.mp3',content=b'12345',headers=self.headers)
            self.assertEqual(response.status_code,413)
        self.assertEqual(self.store.usage(-1)['count'],0)
        response = await self.client.post('/api/import/file?name=song.mp3',content=b'music',headers=self.headers)
        self.assertEqual(response.status_code,201)
        file_id=response.json()['id']
        self.assertEqual((self.store.root/file_id).read_bytes(),b'music')
        self.assertEqual(self.store.get(-1,file_id)['name'],'song.mp3')
        self.assertIsNone(self.store.get(42,file_id))
        self.assertEqual((await self.client.get(f'/api/files/{file_id}/download',headers=self.headers)).content,b'music')

    async def test_link_success_failure_and_busy(self):
        paths=[]
        started=asyncio.Event()
        release=asyncio.Event()
        async def fake(url,mode,folder,location):
            paths.append(folder)
            started.set()
            await release.wait()
            path=folder/'media.mp3'
            path.write_bytes(b'audio')
            return path
        with patch('media_bot.ingest.download_async',side_effect=fake), patch('media_bot.config.Settings.load',return_value=SimpleNamespace(ffmpeg_location=None)):
            self.assertEqual((await self.client.post('/api/import/link',json={'url':'http://127.0.0.1'},headers=self.headers)).status_code,400)
            task=asyncio.create_task(self.client.post('/api/import/link',json={'url':'https://youtu.be/example','mode':'audio','name':'Minha musica'},headers=self.headers))
            await asyncio.wait_for(started.wait(),5)
            try:
                self.assertEqual((await self.client.post('/api/import/file?name=a',content=b'a',headers=self.headers)).status_code,409)
            finally:
                release.set()
            response=await task
            self.assertEqual(response.status_code,201)
            self.assertEqual(response.json()['name'],'Minha musica.mp3')
            self.assertFalse(paths[0].exists())
        with patch('media_bot.ingest.download_async',side_effect=ValueError('private details')), patch('media_bot.config.Settings.load',return_value=SimpleNamespace(ffmpeg_location=None)):
            response=await self.client.post('/api/import/link',json={'url':'https://youtu.be/example'},headers=self.headers)
            self.assertEqual(response.status_code,400)
            self.assertNotIn('private details',response.text)
        self.assertEqual(self.store.usage(-1)['count'],1)

    async def test_password_api_invalid_and_logout(self):
        response=await self.client.post('/api/auth/password',json={'password':'wrong'})
        self.assertEqual(response.status_code,401)
        self.assertEqual((await self.client.post('/api/auth/password',json={'password':'x'*129})).status_code,422)
        await self.client.post('/api/auth/logout',headers=self.headers)
        self.assertEqual((await self.client.get('/api/files',headers=self.headers)).status_code,401)

    async def test_launcher_without_telegram(self):
        root=self.root
        dist=root/'frontend'/'dist'
        dist.mkdir(parents=True)
        (dist/'index.html').write_text('ready')
        AuthStore(root/'data').configure_password('local launch password')
        runtime=root/'.runtime'
        server=SimpleNamespace(started=False,should_exit=False)
        async def serve(**kwargs):
            server.started=True
            while not server.should_exit:
                await asyncio.sleep(.01)
        server.serve=serve
        with patch.multiple(launcher,ROOT=root,RUNTIME=runtime,STATUS=runtime/'instance.json',STOP=runtime/'stop'), patch('media_bot.config.Settings.load',return_value=SimpleNamespace(token='')), patch('media_bot.bot.build_application') as build, patch('uvicorn.Server',return_value=server), patch('media_bot.launcher.create_socket'), patch('media_bot.launcher.webbrowser.open',side_effect=lambda url:launcher.request_stop()):
            await launcher.run()
            build.assert_not_called()
            self.assertFalse((runtime/'instance.json').exists())
