import asyncio
import os
from types import SimpleNamespace
from uuid import uuid4
from unittest import TestCase, skipUnless
from unittest.mock import AsyncMock, Mock

from arq.connections import RedisSettings, create_pool
from arq.constants import job_key_prefix, result_key_prefix, default_queue_name
from arq.worker import Worker
from app.integrations.slack.processing.queue import SlackJobQueue
from app.workers.slack_worker import process_slack_event, reconcile_slack_deliveries, WorkerSettings


@skipUnless(os.environ.get('TEST_REDIS_URL'), 'Set TEST_REDIS_URL to a dedicated test Redis instance')
class LiveDeliveryRecoveryTests(TestCase):
    def test_lost_job_is_recreated_once_and_worker_publishes_heartbeat(self):
        asyncio.run(self.check_recovery())

    async def check_recovery(self):
        redis = await create_pool(RedisSettings.from_dsn(os.environ['TEST_REDIS_URL']))
        event_id = 'recovery-test-' + str(uuid4())
        job_id = 'slack:' + event_id
        health_key = event_id + ':health'
        repo = SimpleNamespace(list_stale_deliveries=Mock(return_value=[event_id]))
        handler = SimpleNamespace(handle=AsyncMock())
        try:
            await SlackJobQueue(redis).enqueue(event_id)
            # Simulate loss of this queue record, without touching other Redis data.
            await redis.delete(job_key_prefix + job_id)
            await redis.zrem(default_queue_name, job_id)
            ctx = {'redis': redis, 'slack_repository': repo, 'slack_handler': handler}
            await reconcile_slack_deliveries(ctx)
            await reconcile_slack_deliveries(ctx)
            worker = Worker([process_slack_event], redis_pool=redis, burst=True,
                            ctx=ctx, handle_signals=False, poll_delay=0.01,
                            health_check_interval=WorkerSettings.health_check_interval,
                            health_check_key=health_key)
            await worker.async_run()
            handler.handle.assert_awaited_once_with(event_id)
            self.assertEqual(worker.jobs_complete, 1)
            self.assertTrue(await redis.exists(health_key))
            self.assertGreater(await redis.ttl(health_key), 0)
        finally:
            await redis.delete(job_key_prefix + job_id, result_key_prefix + job_id, health_key)
            await redis.zrem(default_queue_name, job_id)
            await redis.aclose(close_connection_pool=True)
