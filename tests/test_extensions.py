import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from httpx import ASGITransport, AsyncClient
from media_bot.api import app, library, owner
from media_bot.library import Library


class ExtensionTests(unittest.IsolatedAsyncioTestCase):
    async def test_extension_filters_before_pagination_and_isolates_owners(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            store = Library(root / 'data')
            ids = {}
            for name, user in [('song.MP3',42), ('other.mp3',42), ('song.mp3.txt',42), ('notes.pdf',42), ('README',42), ('private.flac',99)]:
                source = root / name
                source.write_bytes(b'content')
                ids[name] = store.save_local(source, user)
            store.set_favorite(42, ids['song.MP3'], True)
            app.dependency_overrides[library] = lambda: store
            app.dependency_overrides[owner] = lambda: 42
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                    data = (await client.get('/api/files?extension=.MP3&page_size=1&sort=name')).json()
                    self.assertEqual(data['total'], 2)
                    self.assertEqual(data['pages'], 2)
                    self.assertEqual(data['extensions'], ['mp3','pdf','txt'])
                    self.assertEqual(data['usage']['count'], 5)
                    data = (await client.get('/api/files?extension=mp3&q=song&favorites_only=true')).json()
                    self.assertEqual([row['id'] for row in data['files']], [ids['song.MP3']])
                    self.assertEqual((await client.get('/api/files?extension=flac')).json()['total'], 0)
                    self.assertEqual((await client.get('/api/files', params={'extension':"mp3' OR 1=1--"})).json()['total'], 0)
                    app.dependency_overrides[owner] = lambda: 99
                    self.assertEqual((await client.get('/api/files')).json()['extensions'], ['flac'])
            finally:
                app.dependency_overrides.clear()
