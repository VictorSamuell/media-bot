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
