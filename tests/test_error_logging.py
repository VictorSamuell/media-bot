import unittest
from types import SimpleNamespace

from telegram.error import NetworkError

from media_bot.bot import on_error


class ErrorLoggingTests(unittest.IsolatedAsyncioTestCase):
    async def test_logs_cause_types_without_sensitive_message(self):
        error = NetworkError('secret-token-in-url')
        error.__cause__ = TimeoutError('private-data')
        with self.assertLogs('media_bot.bot', level='ERROR') as logs:
            await on_error(None, SimpleNamespace(error=error))
        self.assertIn('NetworkError -> TimeoutError', logs.output[0])
        self.assertNotIn('secret-token', logs.output[0])
        self.assertNotIn('private-data', logs.output[0])

    async def test_cyclic_exception_chain_terminates(self):
        error = NetworkError('error')
        error.__cause__ = error
        with self.assertLogs('media_bot.bot', level='ERROR') as logs:
            await on_error(None, SimpleNamespace(error=error))
        self.assertEqual(logs.output[0].count('NetworkError'), 1)
