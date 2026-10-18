from typing import Any

from pydantic import ValidationError

from app.core.config import get_gemini_api_key, get_gemini_model
from app.core.logging import get_application_logger
from app.prompts.triage import SLACK_MULTI_TASK_PROMPT, TRIAGE_SYSTEM_PROMPT
from app.schemas.task_response import TASK_BATCH_RESPONSE_SCHEMA
from app.schemas.triage import AIAnalysisResult, AITaskBatchResult, IncomingMessage
from app.services.ai_provider import (
    AIModelConfigurationError,
    AIModelServiceError,
    AIModelUnavailableError,
)
from app.services.triage_rules import deterministic_non_actionable


logger = get_application_logger("gemini")


GEMINI_TRIAGE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "isActionableTask": {"type": "boolean"},
        "extractedTitle": {"type": "string"},
        "cleanDescription": {"type": "string"},
        "estimatedPriority": {
            "type": "string",
            "enum": ["HIGH", "MEDIUM", "LOW"],
        },
    },
    "required": [
        "isActionableTask",
        "extractedTitle",
        "cleanDescription",
        "estimatedPriority",
    ],
}


class GeminiService:
    def __init__(
        self,
        api_key: str,
        model: str,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip():
            raise AIModelConfigurationError("GEMINI_API_KEY is not configured")
        if not model.strip():
            raise AIModelConfigurationError("GEMINI_MODEL is not configured")

        self.api_key = api_key
        self.model = model
        self.client = client

    async def analyze(self, message: IncomingMessage) -> AIAnalysisResult:
        rule_result = deterministic_non_actionable(message.text)
        if rule_result is not None:
            logger.info("Triage rule ignored a status-only question")
            return rule_result

        return await self._generate(
            message=message,
            system_prompt=TRIAGE_SYSTEM_PROMPT,
            response_type=AIAnalysisResult,
            max_output_tokens=220,
        )

    async def analyze_tasks(self, message: IncomingMessage) -> AITaskBatchResult:
        rule_result = deterministic_non_actionable(message.text)
        if rule_result is not None:
            logger.info("Triage rule ignored a status-only question")
            return AITaskBatchResult(isActionableTask=False, tasks=[])

        return await self._generate(
            message=message,
            system_prompt=SLACK_MULTI_TASK_PROMPT,
            response_type=AITaskBatchResult,
            max_output_tokens=520,
        )

    async def _generate(
        self,
        message: IncomingMessage,
        system_prompt: str,
        response_type: type[AIAnalysisResult] | type[AITaskBatchResult],
        max_output_tokens: int,
    ) -> AIAnalysisResult | AITaskBatchResult:
        user_content = f"author={message.user_name}\nmessage={message.text}"

        try:
            client = self.client or self._build_client()
            response = await client.aio.models.generate_content(
                model=self.model,
                contents=user_content,
                config=self._build_config(
                    system_prompt=system_prompt,
                    response_type=response_type,
                    max_output_tokens=max_output_tokens,
                ),
            )

            if self._is_truncated(response):
                raise AIModelServiceError(
                    "Gemini response was truncated by the output token limit"
                )

            content = getattr(response, "text", None)
            if not isinstance(content, str) or not content.strip():
                raise AIModelServiceError("Gemini returned an empty response")

            return response_type.model_validate_json(content)
        except AIModelServiceError:
            raise
        except (ValidationError, ValueError, TypeError, KeyError, IndexError) as error:
            logger.warning("Gemini returned invalid structured data: %s", error)
            raise AIModelServiceError("Gemini returned invalid structured data") from error
        except ImportError as error:
            raise AIModelConfigurationError(
                "google-genai is not installed. Install backend requirements first."
            ) from error
        except Exception as error:
            logger.exception("Gemini request failed")
            raise AIModelUnavailableError("Gemini request failed") from error

    def _build_client(self) -> Any:
        from google import genai

        return genai.Client(api_key=self.api_key)

    def _build_config(
        self,
        system_prompt: str,
        response_type: type[AIAnalysisResult] | type[AITaskBatchResult],
        max_output_tokens: int,
    ) -> Any:
        from google.genai import types

        kwargs: dict[str, Any] = {
            "system_instruction": system_prompt,
            "temperature": 0.0,
            "max_output_tokens": max_output_tokens,
            "response_mime_type": "application/json",
            "response_schema": self._response_schema(response_type),
        }

        thinking_config = getattr(types, "ThinkingConfig", None)
        if thinking_config is not None:
            kwargs["thinking_config"] = thinking_config(thinking_budget=0)

        return types.GenerateContentConfig(**kwargs)

    @staticmethod
    def _response_schema(
        response_type: type[AIAnalysisResult] | type[AITaskBatchResult],
    ) -> dict[str, Any]:
        if response_type is AIAnalysisResult:
            return GEMINI_TRIAGE_RESPONSE_SCHEMA
        if response_type is AITaskBatchResult:
            return TASK_BATCH_RESPONSE_SCHEMA
        raise AIModelServiceError("Unsupported Gemini response schema")

    @staticmethod
    def _is_truncated(response: Any) -> bool:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return False
        finish_reason = getattr(candidates[0], "finish_reason", None)
        return str(finish_reason).upper().endswith("MAX_TOKENS")


def get_gemini_service() -> GeminiService:
    return GeminiService(api_key=get_gemini_api_key(), model=get_gemini_model())
