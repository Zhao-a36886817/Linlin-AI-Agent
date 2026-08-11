from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.providers.manager import provider_manager
from app.schemas.models import ModelInfo, ModelListResponse
from app.services.cloud_provider_service import cloud_provider_service

router = APIRouter(
    prefix="/models",
    tags=["Models"],
)


@router.get(
    "",
    response_model=ModelListResponse,
    summary="List available models",
)
async def list_models(
    local_only: bool = Query(default=False),
    include_cloud: bool = Query(default=False),
) -> ModelListResponse:
    ollama_error: RuntimeError | None = None
    try:
        models = await provider_manager.list_models("ollama")
    except RuntimeError as exc:
        models = []
        ollama_error = exc

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

        local = not bool(model.get("remote_host") or model.get("remote_model"))
        if local_only and not local:
            continue

        items.append(
            ModelInfo(
                provider="ollama",
                provider_label="Ollama",
                name=name,
                local=local,
                family=details.get("family"),
                parameter_size=details.get("parameter_size"),
                quantization=details.get("quantization_level"),
                context_length=details.get("context_length"),
                embedding_length=details.get("embedding_length"),
                capabilities=[str(capability) for capability in capabilities],
            ),
        )

    if include_cloud and not local_only:
        items.extend(
            ModelInfo.model_validate(model)
            for model in await cloud_provider_service.model_items()
        )

    if not items and ollama_error is not None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(ollama_error),
        ) from ollama_error

    return ModelListResponse(
        items=items,
        total=len(items),
    )
