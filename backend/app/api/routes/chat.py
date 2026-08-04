from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_service

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a normalized chat request",
)
async def create_chat(request: ChatRequest) -> ChatResponse:
    try:
        return await chat_service.chat(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post(
    "/stream",
    summary="Stream normalized chat events with Server-Sent Events",
)
async def stream_chat(request: ChatRequest) -> EventSourceResponse:
    async def event_generator() -> AsyncIterator[dict[str, str]]:
        try:
            async for event in chat_service.stream(request):
                event_name = "done" if event.done else "message"

                yield {
                    "event": event_name,
                    "data": json.dumps(
                        event.model_dump(mode="json"),
                        ensure_ascii=False,
                    ),
                }
        except (RuntimeError, ValueError, TypeError) as exc:
            yield {
                "event": "error",
                "data": json.dumps(
                    {"detail": str(exc)},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(event_generator())
