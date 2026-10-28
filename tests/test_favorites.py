import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from httpx import ASGITransport, AsyncClient
from media_bot.api import app, library, owner
from media_bot.library import Library


class FavoritesTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistence_isolation_and_deletion(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            store = Library(root / 'data')
            source = root / 'song.mp3'
            source.write_bytes(b'music')
            own = store.save_local(source, 42)
            other = store.save_local(source, 99)
            app.dependency_overrides[library] = lambda: Library(store.root)
            app.dependency_overrides[owner] = lambda: 42
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                    url = f'/api/files/{own}/favorite'
                    self.assertEqual((await client.patch(url, json={'enabled':'true'})).status_code, 422)
                    self.assertEqual((await client.patch(f'/api/files/{other}/favorite', json={'enabled':True})).status_code, 404)
                    for _ in range(2):
                        self.assertEqual((await client.patch(url, json={'enabled':True})).status_code, 200)
                    data = (await client.get('/api/files?favorites_only=true&page_size=1')).json()
                    self.assertEqual(data['total'], 1)
                    self.assertEqual(data['favorites'], [own])
                    self.assertEqual(data['files'][0]['id'], own)
                    app.dependency_overrides[owner] = lambda: 99
                    self.assertEqual((await client.get('/api/files?favorites_only=true')).json()['total'], 0)
                    app.dependency_overrides[owner] = lambda: 42
                    await client.patch(url, json={'enabled':False})
                    self.assertEqual((await client.get('/api/files')).json()['favorites'], [])
                    await client.patch(url, json={'enabled':True})
                    store.delete(42, own)
                    self.assertEqual((await client.get('/api/files')).json()['favorites'], [])
                    with closing(store.connect()) as db:
                        self.assertEqual(db.execute('SELECT COUNT(*) FROM favorites').fetchone()[0], 0)
                    app.dependency_overrides.pop(owner)
                    self.assertEqual((await client.patch(url, json={'enabled':True})).status_code, 401)
            finally:
                app.dependency_overrides.clear()
