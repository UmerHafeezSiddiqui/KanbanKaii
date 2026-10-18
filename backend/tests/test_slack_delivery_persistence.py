from unittest import TestCase

import httpx
from postgrest import SyncPostgrestClient

from app.integrations.slack.data.repository import SlackRepository, SlackRepositoryError


class SlackDeliveryPersistenceTests(TestCase):
    def test_stale_processing_or_failure_update_excludes_committed_batches(self):
        requests = []

        def respond(request):
            requests.append(request)
            if request.method == 'PATCH':
                self.assertEqual(request.url.params['tickets_committed_at'], 'is.null')
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[{'status': 'COMPLETED', 'payload': {}}])

        with httpx.Client(transport=httpx.MockTransport(respond)) as http:
            repository = SlackRepository(SyncPostgrestClient('https://example.invalid', http_client=http))
            repository.update_webhook_delivery('Ev-done', 'PROCESSING')
            repository.update_webhook_delivery('Ev-done', 'FAILED', 'late failure')
        self.assertEqual([request.method for request in requests], ['PATCH', 'GET', 'PATCH', 'GET'])

    def test_missing_delivery_still_reports_an_error(self):
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[]))) as http:
            repository = SlackRepository(SyncPostgrestClient('https://example.invalid', http_client=http))
            with self.assertRaises(SlackRepositoryError):
                repository.update_webhook_delivery('Ev-missing', 'FAILED')
