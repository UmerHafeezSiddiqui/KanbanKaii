from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from starlette.concurrency import run_in_threadpool
from app.auth.dependencies import get_current_user_id
from app.routes.tickets import get_ticket_repository
from app.integrations.slack.routes.webhooks import get_slack_ai_rate_limiter
from app.redis.rate_limiter import AIRateLimiterError, PerUserAIRateLimiter

from app.database.ticket_repository import (
    TicketRepository,
    TicketRepositoryError,
)
from app.schemas.ticket import TriageResponse
from app.schemas.triage import TriageRequest
from app.services.ai_provider import (
    AIModelConfigurationError,
    AIModelService,
    AIModelServiceError,
    AIModelUnavailableError,
)
from app.services.model_service import get_ai_model_service
from app.services.ticket_factory import create_ticket_from_analysis


router = APIRouter(prefix="/api/webhook", tags=["triage"])


def get_configured_ollama_service() -> AIModelService:
    try:
        return get_ai_model_service()
    except AIModelConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


@router.post("/triage", response_model=TriageResponse)
async def triage_message(
    message: TriageRequest,
    response: Response,
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
    ollama_service: Annotated[
        AIModelService,
        Depends(get_configured_ollama_service),
    ],
    ticket_repository: Annotated[
        TicketRepository,
        Depends(get_ticket_repository),
    ],
    rate_limiter: Annotated[PerUserAIRateLimiter, Depends(get_slack_ai_rate_limiter)],
) -> TriageResponse:
    if message.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Ticket owner must match the signed-in user")
    try:
        if not await rate_limiter.acquire(f"triage:{uuid4()}", [owner_id]):
            raise HTTPException(status_code=429, detail="AI request limit reached")
        analysis = await ollama_service.analyze(message)
        if not analysis.isActionableTask:
            return TriageResponse(status="ignored", analysis=analysis)

        ticket_data = create_ticket_from_analysis(
            owner_id=owner_id,
            message=message,
            analysis=analysis,
            source=message.source,
        )
        ticket = await run_in_threadpool(ticket_repository.create, ticket_data)
        response.status_code = status.HTTP_201_CREATED
        return TriageResponse(
            status="created",
            analysis=analysis,
            ticket=ticket,
        )
    except AIRateLimiterError as error:
        raise HTTPException(status_code=503, detail="AI rate limiter is unavailable") from error
    except AIModelUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except AIModelServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    except TicketRepositoryError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
