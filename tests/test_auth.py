import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch, AsyncMock
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import time
from httpx import AsyncClient, ASGITransport
from media_bot.auth import AuthStore
from media_bot.api import app, auth_store
from media_bot.bot import MediaBot
from media_bot.config import Settings

class AuthTests(unittest.TestCase):
    def test_single_use_replacement_expiry_and_hashes(self):
        with TemporaryDirectory() as folder:
            store = AuthStore(Path(folder))
            with patch('media_bot.auth.time.time', return_value=1000):
                old = store.issue(42)
                code = store.issue(42)
                self.assertEqual(store.exchange(old),(None,'invalid'))
                token, error = store.exchange(code)
                self.assertIsNone(error)
                self.assertEqual(store.owner(token),42)
                self.assertEqual(store.exchange(code),(None,'invalid'))
                expiring = store.issue(99)
            with patch('media_bot.auth.time.time', return_value=1301):
                self.assertEqual(store.exchange(expiring),(None,'invalid'))
            with patch('media_bot.auth.time.time', return_value=44201):
                self.assertIsNone(store.owner(token))
            self.assertNotIn(token.encode(), (Path(folder)/'auth.sqlite3').read_bytes())

    def test_concurrent_redemption_and_rate_limit(self):
        with TemporaryDirectory() as folder:
            store = AuthStore(Path(folder))
            code = store.issue(42)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(store.exchange,[code,code]))
            self.assertEqual(sum(token is not None for token,_ in results),1)
            later = time.time() + 61
            with patch('media_bot.auth.time.time',return_value=later):
                for _ in range(30):
                    self.assertEqual(store.exchange('bad')[1],'invalid')
                self.assertEqual(store.exchange('bad')[1],'limited')
            with patch('media_bot.auth.time.time',return_value=later+61):
                self.assertEqual(store.exchange('bad')[1],'invalid')

class LoginTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_logout_and_two_owners(self):
        with TemporaryDirectory() as folder:
            store = AuthStore(Path(folder))
            app.dependency_overrides[auth_store] = lambda:store
            try:
                async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
                    for user in (42,99):
                        response = await client.post('/api/auth/login',json={'code':store.issue(user)})
                        self.assertEqual(response.status_code,200)
                        self.assertEqual(response.headers['cache-control'],'no-store')
                        token = response.json()['token']
                        self.assertEqual(store.owner(token),user)
                        response = await client.post('/api/auth/logout',headers={'Authorization':'Bearer '+token})
                        self.assertEqual(response.status_code,200)
                        self.assertIsNone(store.owner(token))
                        self.assertEqual((await client.get('/api/files',headers={'Authorization':'Bearer '+token})).status_code,401)
                    self.assertEqual((await client.post('/api/auth/login',json={'code':'wrong'})).status_code,401)
            finally:
                app.dependency_overrides.clear()

    async def test_bot_issues_only_in_authorized_private_chat(self):
        bot = MediaBot(Settings('token',frozenset({42})))
        update = SimpleNamespace(effective_user=SimpleNamespace(id=42),
            effective_chat=SimpleNamespace(id=1,type='group'),message=SimpleNamespace(reply_text=AsyncMock()))
        with patch('media_bot.bot.AuthStore') as factory:
            await bot.login(update,None)
            factory.assert_not_called()
            update.effective_chat.type='private'
            update.effective_user.id=99
            await bot.login(update,None)
            factory.assert_not_called()
            update.effective_user.id=42
            factory.return_value.issue.return_value='TESTCODE'
            await bot.login(update,None)
            factory.return_value.issue.assert_called_once_with(42)
