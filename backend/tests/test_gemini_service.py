import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock

from app.schemas.triage import IncomingMessage
from app.services.ai_provider import AIModelServiceError
from app.services.gemini_service import GeminiService


class GeminiServiceTests(TestCase):
    def test_multiple_tasks_use_the_expected_provider_wire_schema(self):
        generate = AsyncMock(return_value=SimpleNamespace(
            text='{"isActionableTask":true,"tasks":[{"title":"Fix checkout","description":"Repair payments","priority":"HIGH"}]}',
            candidates=[],
        ))
        service = GeminiService('test-key', 'test-model', SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)),
        ))
        result = asyncio.run(service.analyze_tasks(IncomingMessage(text='Fix checkout', user_name='Aisha')))
        self.assertEqual(result.tasks[0].title, 'Fix checkout')
        self.assertEqual(result.tasks[0].priority, 'HIGH')
        config = generate.await_args.kwargs['config']
        self.assertEqual(config.response_mime_type, 'application/json')
        self.assertEqual(config.response_schema['required'], ['isActionableTask', 'tasks'])
        self.assertEqual(config.response_schema['properties']['tasks']['items']['required'], ['title', 'description', 'priority'])

    def test_rejects_inconsistent_task_batches(self):
        generate = AsyncMock(return_value=SimpleNamespace(
            text='{"isActionableTask":true,"tasks":[]}', candidates=[],
        ))
        service = GeminiService('test-key', 'test-model', SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)),
        ))
        with self.assertRaisesRegex(AIModelServiceError, 'invalid structured data'):
            asyncio.run(service.analyze_tasks(IncomingMessage(text='Fix checkout', user_name='Aisha')))
