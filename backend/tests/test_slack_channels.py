import asyncio
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet

from app.integrations.slack.security.encryption import TokenCipher
from app.integrations.slack.services.channels import SlackChannelService


class SlackChannelNameTests(TestCase):
    def test_name_resolution_preserves_normalized_preference_and_fallback(self):
        async def check():
            cipher = TokenCipher(Fernet.generate_key().decode())
            repository = SimpleNamespace(get_installation=lambda owner: SimpleNamespace(token_ciphertext=cipher.encrypt('test-token')))
            for channel, expected in (
                ({'name_normalized': ' #payments ', 'name': 'fallback'}, 'payments'),
                ({'name_normalized': ' ', 'name': ' #support '}, 'support'),
                ({'name': ' '}, None),
            ):
                with self.subTest(channel=channel):
                    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'ok': True, 'channel': channel}))
                    async with httpx.AsyncClient(transport=transport) as client:
                        service = SlackChannelService(repository, cipher, client)
                        self.assertEqual(await service.display_name(uuid4(), 'T-test', 'C-test'), expected)
        asyncio.run(check())
