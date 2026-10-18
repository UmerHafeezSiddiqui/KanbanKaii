import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, Mock

import httpx
from postgrest import SyncPostgrestClient
from app.integrations.slack.data.repository import SlackRepository
from app.workers.slack_worker import reconcile_slack_deliveries, STALE_DELIVERY_SECONDS, WorkerSettings


class DeliveryRecoveryTests(TestCase):
    def test_only_old_uncommitted_pending_deliveries_are_selected(self):
        def respond(request):
            params = request.url.params
            self.assertEqual(params['provider'], 'eq.SLACK')
            self.assertEqual(params['status'], 'in.(RECEIVED,PROCESSING)')
            self.assertEqual(params['tickets_committed_at'], 'is.null')
            self.assertEqual(params['received_at'], 'lt.2026-10-18T00:00:00+00:00')
            self.assertEqual(params['limit'], '100')
            self.assertEqual(params['order'], 'received_at.asc')
            return httpx.Response(200, json=[{'external_event_id': 'lost-event'}])
        with httpx.Client(transport=httpx.MockTransport(respond)) as http:
            repo = SlackRepository(SyncPostgrestClient('https://example.invalid', http_client=http))
            self.assertEqual(repo.list_stale_deliveries('2026-10-18T00:00:00+00:00'), ['lost-event'])

    def test_recovery_uses_stable_job_ids_even_when_a_job_already_exists(self):
        repo = SimpleNamespace(list_stale_deliveries=Mock(return_value=['lost-event', 'queued-event']))
        redis = SimpleNamespace(enqueue_job=AsyncMock(side_effect=[object(), None]))
        asyncio.run(reconcile_slack_deliveries({'slack_repository': repo, 'redis': redis}))
        self.assertEqual(redis.enqueue_job.await_count, 2)
        redis.enqueue_job.assert_any_await('process_slack_event', 'lost-event', _job_id='slack:lost-event')
        redis.enqueue_job.assert_any_await('process_slack_event', 'queued-event', _job_id='slack:queued-event')
        self.assertIsNotNone(datetime.fromisoformat(repo.list_stale_deliveries.call_args.args[0]).tzinfo)
        self.assertGreater(STALE_DELIVERY_SECONDS, WorkerSettings.job_timeout * WorkerSettings.max_tries + 20)
