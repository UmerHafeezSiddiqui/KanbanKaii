import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, Mock

import httpx
from arq import Retry
from postgrest.exceptions import APIError
from google.genai.errors import ServerError, ClientError
from ollama import ResponseError

from app.database.ticket_repository import TicketRepositoryError
from app.integrations.slack.processing.queued_processor import SlackQueuedEventError
from app.services.ai_provider import AIModelConfigurationError, AIModelServiceError, AIModelUnavailableError
from app.workers.slack_worker import process_slack_event, WorkerSettings


def wrapped_error(cause):
    error = TicketRepositoryError('Supabase could not commit Slack tickets')
    error.__cause__ = cause
    return error


class WorkerRetryTests(TestCase):
    def test_transient_failure_retries_then_recovers(self):
        handler = SimpleNamespace(repository=SimpleNamespace(update_webhook_delivery=Mock()), handle=AsyncMock(side_effect=[httpx.ConnectError('temporary outage'), None]))
        with self.assertRaises(Retry) as caught:
            asyncio.run(process_slack_event({'slack_handler': handler, 'job_try': 1}, 'event-1'))
        self.assertEqual(caught.exception.defer_score, 5000)
        self.assertEqual(handler.repository.update_webhook_delivery.call_args.args[1], 'RECEIVED')
        asyncio.run(process_slack_event({'slack_handler': handler, 'job_try': 2}, 'event-1'))
        self.assertEqual(handler.handle.await_count, 2)
        handler.handle.assert_awaited_with('event-1')

    def test_retry_limit_propagates_the_original_failure(self):
        failure = TimeoutError('temporary timeout')
        handler = SimpleNamespace(repository=SimpleNamespace(update_webhook_delivery=Mock()), handle=AsyncMock(side_effect=failure))
        with self.assertRaises(Retry) as caught:
            asyncio.run(process_slack_event({'slack_handler': handler, 'job_try': 2}, 'event-1'))
        self.assertEqual(caught.exception.defer_score, 15000)
        with self.assertRaises(TimeoutError) as caught:
            asyncio.run(process_slack_event({'slack_handler': handler, 'job_try': WorkerSettings.max_tries}, 'event-1'))
        self.assertIs(caught.exception, failure)
        self.assertEqual(handler.repository.update_webhook_delivery.call_args.args[1], 'FAILED')
        self.assertEqual(WorkerSettings.max_tries, 3)

    def test_wrapped_database_failures_are_classified_by_cause(self):
        for code, retry in (('40001', True), ('40P01', True), ('08006', True), ('PGRST002', True), ('23514', False), ('42501', False), ('PGRST202', False)):
            with self.subTest(code=code):
                error = wrapped_error(APIError({'code': code, 'message': 'test failure', 'details': None, 'hint': None}))
                handler = SimpleNamespace(repository=SimpleNamespace(update_webhook_delivery=Mock()), handle=AsyncMock(side_effect=error))
                with self.assertRaises(Retry if retry else TicketRepositoryError):
                    asyncio.run(process_slack_event({'slack_handler': handler, 'job_try': 1}, 'event-1'))

    def test_provider_http_errors_retry_only_temporary_statuses(self):
        for status, retry in ((429, True), (503, True), (401, False), (403, False), (404, False)):
            with self.subTest(status=status):
                cause = httpx.HTTPStatusError('provider failure', request=httpx.Request('GET', 'https://example.invalid'), response=httpx.Response(status))
                error = AIModelUnavailableError('provider unavailable')
                error.__cause__ = cause
                handler = SimpleNamespace(repository=SimpleNamespace(update_webhook_delivery=Mock()), handle=AsyncMock(side_effect=error))
                with self.assertRaises(Retry if retry else AIModelUnavailableError):
                    asyncio.run(process_slack_event({'slack_handler': handler, 'job_try': 1}, 'event-1'))

    def test_permanent_errors_are_terminal(self):
        for error in (SlackQueuedEventError('invalid payload'), AIModelConfigurationError('missing key'), AIModelServiceError('invalid structured data'), httpx.UnsupportedProtocol('bad URL scheme'), ValueError('invalid input'), RuntimeError('programming error')):
            with self.subTest(error=type(error).__name__):
                handler = SimpleNamespace(repository=SimpleNamespace(update_webhook_delivery=Mock()), handle=AsyncMock(side_effect=error))
                with self.assertRaises(type(error)) as caught:
                    asyncio.run(process_slack_event({'slack_handler': handler, 'job_try': 1}, 'event-1'))
                self.assertIs(caught.exception, error)

    def test_actual_provider_sdk_statuses_survive_wrapping(self):
        for cause, retry in (
            (ServerError(503, {'error': {'code': 503, 'message': 'busy'}}), True),
            (ClientError(403, {'error': {'code': 403, 'message': 'invalid key'}}), False),
            (ResponseError('busy', status_code=503), True),
            (ResponseError('model missing', status_code=404), False),
        ):
            with self.subTest(cause=type(cause).__name__):
                error = AIModelUnavailableError('provider failed')
                error.__cause__ = cause
                handler = SimpleNamespace(repository=SimpleNamespace(update_webhook_delivery=Mock()), handle=AsyncMock(side_effect=error))
                with self.assertRaises(Retry if retry else AIModelUnavailableError):
                    asyncio.run(process_slack_event({'slack_handler': handler, 'job_try': 1}, 'event-1'))

    def test_failure_recording_outage_does_not_hide_retry_or_original_error(self):
        handler = SimpleNamespace(repository=SimpleNamespace(update_webhook_delivery=Mock(side_effect=ConnectionError('database offline'))), handle=AsyncMock(side_effect=TimeoutError('original failure')))
        with self.assertLogs('kanbankaii.slack.worker', level='ERROR'):
            with self.assertRaises(Retry):
                asyncio.run(process_slack_event({'slack_handler': handler, 'job_try': 1}, 'event-1'))
            with self.assertRaisesRegex(TimeoutError, 'original failure'):
                asyncio.run(process_slack_event({'slack_handler': handler, 'job_try': 3}, 'event-1'))

