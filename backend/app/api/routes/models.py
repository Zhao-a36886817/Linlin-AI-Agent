from __future__ import annotations

import app.providers.adapters
from fastapi import APIRouter, HTTPException, status

from app.providers.manager import provider_manager
from app.schemas.models import ModelInfo, ModelListResponse


router = APIRouter(
    prefix="/models",
    tags=["Models"],
)


@router.get(
    "",
    response_model=ModelListResponse,
    summary="List available models",
)
async def list_models() -> ModelListResponse:
    try:
        models = await provider_manager.list_models("ollama")
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    items: list[ModelInfo] = []

    for model in models:
        details = model.get("details", {})

        if not isinstance(details, dict):
            details = {}

        capabilities = model.get("capabilities", [])

        if not isinstance(capabilities, list):
            capabilities = []

        name = model.get("name")

        if not isinstance(name, str) or not name:
            continue

        items.append(
            ModelInfo(
                provider="ollama",
                name=name,
                family=details.get("family"),
                parameter_size=details.get("parameter_size"),
                quantization=details.get("quantization_level"),
                context_length=details.get("context_length"),
                embedding_length=details.get("embedding_length"),
                capabilities=[
                    str(capability)
                    for capability in capabilities
                ],
            ),
        )

    return ModelListResponse(
        items=items,
        total=len(items),
    )
