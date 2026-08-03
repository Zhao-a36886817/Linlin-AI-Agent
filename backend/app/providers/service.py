import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.providers.models import (
    ProviderConfig,
    ProviderCreate,
    ProviderListResponse,
    ProviderPublic,
    ProviderUpdate,
)
from app.providers.storage import ProviderStorage


class ProviderNotFoundError(LookupError):
    """Raised when a provider ID does not exist."""


class ProviderNameConflictError(ValueError):
    """Raised when a provider name is already in use."""


class ProviderService:
    """Provider configuration business logic."""

    def __init__(self, storage: ProviderStorage) -> None:
        self._storage = storage

    async def initialize(self) -> None:
        await self._storage.initialize()

    async def list_providers(self) -> ProviderListResponse:
        providers = await self._storage.list_all()
        providers.sort(
            key=lambda item: (
                item.priority,
                item.name.casefold(),
            ),
        )

        public_items = [self._to_public(provider) for provider in providers]

        return ProviderListResponse(
            items=public_items,
            total=len(public_items),
            enabled=sum(1 for provider in public_items if provider.enabled),
        )

    async def get_provider(
        self,
        provider_id: UUID,
    ) -> ProviderPublic:
        providers = await self._storage.list_all()

        provider = self._find_provider(
            providers,
            provider_id,
        )

        return self._to_public(provider)

    async def create_provider(
        self,
        payload: ProviderCreate,
    ) -> ProviderPublic:
        providers = await self._storage.list_all()

        self._ensure_unique_name(
            providers=providers,
            name=payload.name,
        )

        now = datetime.now(UTC)

        provider = ProviderConfig(
            id=uuid4(),
            name=payload.name,
            kind=payload.kind,
            base_url=payload.base_url,
            api_key_env=payload.api_key_env,
            default_model=payload.default_model,
            enabled=payload.enabled,
            timeout_seconds=payload.timeout_seconds,
            max_concurrency=payload.max_concurrency,
            priority=payload.priority,
            metadata=payload.metadata,
            created_at=now,
            updated_at=now,
        )

        providers.append(provider)
        await self._storage.replace_all(providers)

        return self._to_public(provider)

    async def update_provider(
        self,
        provider_id: UUID,
        payload: ProviderUpdate,
    ) -> ProviderPublic:
        providers = await self._storage.list_all()

        current = self._find_provider(
            providers,
            provider_id,
        )

        update_data = payload.model_dump(
            exclude_unset=True,
        )

        if "name" in update_data:
            self._ensure_unique_name(
                providers=providers,
                name=update_data["name"],
                ignored_provider_id=provider_id,
            )

        updated = current.model_copy(
            update={
                **update_data,
                "updated_at": datetime.now(UTC),
            },
        )

        updated_providers = [
            updated if item.id == provider_id else item for item in providers
        ]

        await self._storage.replace_all(updated_providers)

        return self._to_public(updated)

    async def delete_provider(
        self,
        provider_id: UUID,
    ) -> None:
        providers = await self._storage.list_all()

        self._find_provider(
            providers,
            provider_id,
        )

        remaining = [item for item in providers if item.id != provider_id]

        await self._storage.replace_all(remaining)

    async def count_enabled(self) -> int:
        providers = await self._storage.list_all()

        return sum(1 for provider in providers if provider.enabled)

    @staticmethod
    def _find_provider(
        providers: list[ProviderConfig],
        provider_id: UUID,
    ) -> ProviderConfig:
        for provider in providers:
            if provider.id == provider_id:
                return provider

        raise ProviderNotFoundError(
            f"Provider {provider_id} was not found.",
        )

    @staticmethod
    def _ensure_unique_name(
        providers: list[ProviderConfig],
        name: str,
        ignored_provider_id: UUID | None = None,
    ) -> None:
        normalized_name = name.strip().casefold()

        for provider in providers:
            if ignored_provider_id == provider.id:
                continue

            if provider.name.strip().casefold() == normalized_name:
                raise ProviderNameConflictError(
                    f"Provider name '{name}' already exists.",
                )

    @staticmethod
    def _to_public(
        provider: ProviderConfig,
    ) -> ProviderPublic:
        has_api_key = bool(provider.api_key_env and os.getenv(provider.api_key_env))

        return ProviderPublic(
            id=provider.id,
            name=provider.name,
            kind=provider.kind,
            base_url=provider.base_url,
            api_key_env=provider.api_key_env,
            has_api_key=has_api_key,
            default_model=provider.default_model,
            enabled=provider.enabled,
            timeout_seconds=provider.timeout_seconds,
            max_concurrency=provider.max_concurrency,
            priority=provider.priority,
            metadata=provider.metadata,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )


_settings = get_settings()

provider_storage = ProviderStorage(
    _settings.data_root / "providers.json",
)

provider_service = ProviderService(provider_storage)
