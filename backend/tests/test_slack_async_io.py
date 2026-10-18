import asyncio
import threading
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from app.integrations.slack.config import SlackOAuthSettings
from app.integrations.slack.services.channels import SlackChannelService
from app.integrations.slack.services.connection import SlackConnectionService
from app.integrations.slack.services.oauth import SlackOAuthService
from app.integrations.slack.services.users import SlackUserService


class SlackAsyncDatabaseTests(TestCase):
    def assert_database_does_not_block_loop(self, operation, result=None):
        async def check():
            entered, release = threading.Event(), threading.Event()
            loop_thread = threading.get_ident()

            def database_call(*args, **kwargs):
                self.assertNotEqual(threading.get_ident(), loop_thread, 'Synchronous database I/O ran on the event loop')
                entered.set()
                if not release.wait(2):
                    raise AssertionError('Event loop could not release the blocked database call')
                return result

            task = asyncio.create_task(operation(database_call))
            try:
                await asyncio.sleep(0)
                if task.done():
                    await task
                self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                self.assertFalse(task.done(), 'The unrelated coroutine must progress while the database is blocked')
            finally:
                release.set()
            return await task
        return asyncio.run(check())

    def test_user_lookup_allows_other_coroutines_to_progress(self):
        def operation(call):
            return SlackUserService(SimpleNamespace(get_installation=call), None).display_name(uuid4(), 'U-test')
        self.assertEqual(self.assert_database_does_not_block_loop(operation), 'U-test')

    def test_channel_lookup_allows_other_coroutines_to_progress(self):
        def operation(call):
            return SlackChannelService(SimpleNamespace(get_installation=call), None).display_name(uuid4(), 'T-test', 'C-test')
        self.assertIsNone(self.assert_database_does_not_block_loop(operation))

    def test_connection_status_allows_other_coroutines_to_progress(self):
        def operation(call):
            return SlackConnectionService(SimpleNamespace(get_installation=call), None).status(uuid4())
        self.assertIsNone(self.assert_database_does_not_block_loop(operation))

    def test_oauth_ownership_check_allows_other_coroutines_to_progress(self):
        async def store(*args):
            return None
        def operation(call):
            settings = SlackOAuthSettings('id', 'secret', 'https://example.invalid/callback', 'http://localhost:5173/settings', 'unused')
            service = SlackOAuthService(settings, SimpleNamespace(is_organization_owner=call), None, SimpleNamespace(create=store))
            return service.create_authorization_url(uuid4(), uuid4())
        url = self.assert_database_does_not_block_loop(operation, result=True)
        self.assertTrue(url.startswith('https://slack.com/oauth/v2/authorize?'))
