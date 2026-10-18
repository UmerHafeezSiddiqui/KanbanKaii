from typing import Any

import httpx
from ollama import AsyncClient, ResponseError
from pydantic import ValidationError

from app.core.config import get_ollama_host, get_ollama_model
from app.prompts.triage import SLACK_MULTI_TASK_PROMPT, TRIAGE_SYSTEM_PROMPT
from app.schemas.task_response import TASK_BATCH_RESPONSE_SCHEMA
from app.schemas.triage import AIAnalysisResult, AITaskBatchResult, IncomingMessage
from app.services.ai_provider import (
    AIModelConfigurationError,
    AIModelServiceError,
    AIModelUnavailableError,
)
from app.services.triage_rules import deterministic_non_actionable
from app.core.logging import get_application_logger


logger = get_application_logger("ollama")


class OllamaConfigurationError(AIModelConfigurationError):
    """Raised when local Ollama configuration is invalid."""


class OllamaUnavailableError(AIModelUnavailableError):
    """Raised when the local Ollama server cannot be reached."""


class OllamaServiceError(AIModelServiceError):
    """Raised when Ollama fails or returns invalid structured data."""


class OllamaService:
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
        client: Any | None = None,
    ) -> None:
        if not host.strip():
            raise OllamaConfigurationError("OLLAMA_HOST is not configured")
        if not model.strip():
            raise OllamaConfigurationError("OLLAMA_MODEL is not configured")

        self.host = host
        self.model = model
        self.client = client

    async def analyze(self, message: IncomingMessage) -> AIAnalysisResult:
        rule_result = deterministic_non_actionable(message.text)
        if rule_result is not None:
            logger.info("Triage rule ignored a status-only question")
            return rule_result

        return await self._generate(message, TRIAGE_SYSTEM_PROMPT, AIAnalysisResult)

    async def analyze_tasks(self, message: IncomingMessage) -> AITaskBatchResult:
        rule_result = deterministic_non_actionable(message.text)
        if rule_result is not None:
            logger.info("Triage rule ignored a status-only question")
            return AITaskBatchResult(isActionableTask=False, tasks=[])
        return await self._generate(
            message,
            SLACK_MULTI_TASK_PROMPT,
            AITaskBatchResult,
            num_predict=700,
            response_schema=TASK_BATCH_RESPONSE_SCHEMA,
        )

    async def _generate(
        self,
        message,
        system_prompt,
        response_type,
        num_predict=300,
        response_schema=None,
    ):
        user_content = (
            f"Author: {message.user_name}\n"
            f"Message: <message>{message.text}</message>"
        )

        try:
            chat_options = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "format": response_schema or response_type.model_json_schema(),
                "options": {"temperature": 0, "num_predict": num_predict},
                "think": False,
            }
            if self.client is not None:
                response = await self.client.chat(**chat_options)
            else:
                async with AsyncClient(host=self.host, timeout=120.0) as client:
                    response = await client.chat(**chat_options)

            if getattr(response, "done_reason", None) == "length":
                raise OllamaServiceError(
                    "Ollama response was truncated by the output token limit"
                )

            content = response.message.content
            if not isinstance(content, str) or not content.strip():
                raise OllamaServiceError("Ollama returned an empty response")

            return response_type.model_validate_json(content)
        except OllamaServiceError:
            raise
        except (ValidationError, ValueError, TypeError, KeyError, IndexError) as error:
            logger.warning("Ollama returned invalid structured data: %s", error)
            raise OllamaServiceError("Ollama returned invalid structured data") from error
        except ResponseError as error:
            if error.status_code == 404:
                raise OllamaUnavailableError(
                    f"Ollama model '{self.model}' is not installed"
                ) from error
            logger.error("Ollama returned HTTP %s: %s", error.status_code, error.error)
            raise OllamaServiceError("Ollama request failed") from error
        except (httpx.ConnectError, httpx.TimeoutException) as error:
            raise OllamaUnavailableError(
                "Ollama is not running at the configured host"
            ) from error


def get_ollama_service() -> OllamaService:
    return OllamaService(host=get_ollama_host(), model=get_ollama_model())
