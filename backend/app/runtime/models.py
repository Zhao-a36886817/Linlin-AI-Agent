from __future__ import annotations

from fastapi import APIRouter

from app.providers.manager import provider_manager
from app.schemas.models import ModelInfo, ModelListResponse

router = APIRouter(
    prefix="/models",
    tags=["Models"],
)


@router.get(
    "",
    response_model=ModelListResponse,
)
async def list_models() -> ModelListResponse:

    models = await provider_manager.list_models("ollama")

    items: list[ModelInfo] = []

    for model in models:
        details = model.get("details", {})

        items.append(
            ModelInfo(
                provider="ollama",
                name=model["name"],
                family=details.get("family"),
                parameter_size=details.get("parameter_size"),
                quantization=details.get("quantization_level"),
                context_length=details.get("context_length"),
                embedding_length=details.get("embedding_length"),
                capabilities=model.get("capabilities", []),
            )
        )

    return ModelListResponse(
        items=items,
        total=len(items),
    )
