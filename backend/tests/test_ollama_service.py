import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock

from app.schemas.triage import AIAnalysisResult, AITaskBatchResult, IncomingMessage
from app.schemas.task_response import TASK_BATCH_RESPONSE_SCHEMA
from app.services.ollama_service import (
    OllamaService,
    OllamaServiceError,
)


class OllamaServiceTests(TestCase):
    def test_status_only_question_is_rejected_without_calling_model(self) -> None:
        async def should_not_run(**kwargs):
            raise AssertionError("Ollama should not run for a status-only question")

        service = OllamaService(client=SimpleNamespace(chat=should_not_run))

        result = asyncio.run(
            service.analyze(
                IncomingMessage(
                    text="When can I get the model fixed?",
                    user_name="Aisha",
                )
            )
        )

        self.assertFalse(result.isActionableTask)
        self.assertEqual(result.extractedTitle, "")

    def test_validates_structured_response(self) -> None:
        content = (
            '{"isActionableTask":true,"extractedTitle":"Fix checkout",'
            '"cleanDescription":"Resolve the checkout failure.",'
            '"estimatedPriority":"HIGH"}'
        )
        response = SimpleNamespace(
            done_reason="stop",
            message=SimpleNamespace(content=content),
        )
        chat = AsyncMock(return_value=response)
        service = OllamaService(client=SimpleNamespace(chat=chat))

        result = asyncio.run(
            service.analyze(
                IncomingMessage(text="Fix checkout", user_name="Aisha")
            )
        )

        self.assertTrue(result.isActionableTask)
        self.assertEqual(result.extractedTitle, "Fix checkout")
        request = chat.await_args.kwargs
        self.assertEqual(request["model"], "llama3.2:3b")
        self.assertEqual(request["options"]["num_predict"], 300)
        self.assertFalse(request["think"])
        self.assertEqual(request["format"], AIAnalysisResult.model_json_schema())

    def test_detects_truncated_response(self) -> None:
        response = SimpleNamespace(
            done_reason="length",
            message=SimpleNamespace(content='{"isActionableTask"'),
        )
        service = OllamaService(
            client=SimpleNamespace(chat=AsyncMock(return_value=response))
        )

        with self.assertRaisesRegex(
            OllamaServiceError,
            "Ollama response was truncated by the output token limit",
        ):
            asyncio.run(
                service.analyze(
                    IncomingMessage(text="Fix checkout", user_name="Aisha")
                )
            )

    def test_validates_multiple_task_response(self) -> None:
        content = (
            '{"isActionableTask":true,"tasks":['
            '{"title":"Fix checkout","description":"Fix checkout.","priority":"HIGH"},'
            '{"title":"Review tests","description":"Review payment tests.","priority":"MEDIUM"}]}'
        )
        chat = AsyncMock(
            return_value=SimpleNamespace(
                done_reason="stop",
                message=SimpleNamespace(content=content),
            )
        )
        service = OllamaService(client=SimpleNamespace(chat=chat))

        result = asyncio.run(
            service.analyze_tasks(
                IncomingMessage(text="Fix checkout and review tests", user_name="Aisha")
            )
        )

        self.assertEqual(len(result.tasks), 2)
        request = chat.await_args.kwargs
        self.assertEqual(request["format"], TASK_BATCH_RESPONSE_SCHEMA)
        self.assertEqual(request["options"]["num_predict"], 700)
