from pathlib import Path

import pytest

from app.providers.models import (
    ProviderCostClass,
    ProviderCreate,
    ProviderKind,
    ProviderUpdate,
)
from app.providers.service import (
    ProviderNameConflictError,
    ProviderService,
)
from app.providers.storage import ProviderStorage


@pytest.mark.asyncio
async def test_provider_crud(
    tmp_path: Path,
) -> None:
    storage = ProviderStorage(
        tmp_path / "providers.json",
    )

    service = ProviderService(storage)

    await service.initialize()

    created = await service.create_provider(
        ProviderCreate(
            name="OpenRouter Main",
            kind=ProviderKind.OPENROUTER,
            base_url="https://openrouter.ai/api/v1",
            api_key_env="OPENROUTER_API_KEY",
            default_model="example/model",
            enabled=True,
            max_concurrency=4,
        ),
    )

    assert created.name == "OpenRouter Main"
    assert created.kind == ProviderKind.OPENROUTER
    assert created.cost_class == ProviderCostClass.UNKNOWN
    assert created.has_api_key is False

    listing = await service.list_providers()

    assert listing.total == 1
    assert listing.enabled == 1
    assert listing.items[0].id == created.id

    updated = await service.update_provider(
        created.id,
        ProviderUpdate(
            name="OpenRouter Primary",
            max_concurrency=6,
        ),
    )

    assert updated.name == "OpenRouter Primary"
    assert updated.max_concurrency == 6

    fetched = await service.get_provider(created.id)

    assert fetched.id == created.id
    assert fetched.name == "OpenRouter Primary"

    await service.delete_provider(created.id)

    final_listing = await service.list_providers()

    assert final_listing.total == 0
    assert final_listing.enabled == 0


@pytest.mark.asyncio
async def test_duplicate_provider_name_rejected(
    tmp_path: Path,
) -> None:
    service = ProviderService(
        ProviderStorage(tmp_path / "providers.json"),
    )

    await service.initialize()

    payload = ProviderCreate(
        name="Gemini",
        kind=ProviderKind.GEMINI,
        api_key_env="GEMINI_API_KEY",
    )

    await service.create_provider(payload)

    with pytest.raises(ProviderNameConflictError):
        await service.create_provider(payload)
