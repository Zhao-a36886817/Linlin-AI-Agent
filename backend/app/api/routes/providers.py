from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.providers.models import (
    ProviderConnect,
    ProviderConnectResponse,
    ProviderCreate,
    ProviderDeleteResponse,
    ProviderDiscoverRequest,
    ProviderListResponse,
    ProviderPublic,
    ProviderUpdate,
)
from app.providers.service import (
    ProviderNameConflictError,
    ProviderNotFoundError,
    provider_service,
)
from app.services.cloud_provider_service import (
    CloudProviderError,
    cloud_provider_service,
)

router = APIRouter(
    prefix="/providers",
    tags=["Providers"],
)


@router.get(
    "",
    response_model=ProviderListResponse,
    summary="List configured model providers",
)
async def list_providers() -> ProviderListResponse:
    return await provider_service.list_providers()


@router.post(
    "/connect",
    response_model=ProviderConnectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Detect, verify, and securely activate a cloud provider",
)
async def connect_provider(payload: ProviderConnect) -> dict[str, object]:
    try:
        return await cloud_provider_service.connect(
            name=payload.name,
            base_url=payload.base_url,
            api_key=(payload.api_key.get_secret_value() if payload.api_key else None),
            credential_env=payload.credential_env,
            kind=payload.kind,
            default_model=payload.default_model,
            consent=payload.consent,
        )
    except (CloudProviderError, RuntimeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.post(
    "/{provider_id}/discover",
    summary="Refresh models with explicit cloud consent",
)
async def discover_provider(
    provider_id: UUID,
    payload: ProviderDiscoverRequest,
) -> dict[str, object]:
    try:
        return await cloud_provider_service.discover(
            provider_id,
            consent=payload.consent,
        )
    except ProviderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (CloudProviderError, RuntimeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get(
    "/{provider_id}",
    response_model=ProviderPublic,
    summary="Get one model provider",
)
async def get_provider(
    provider_id: UUID,
) -> ProviderPublic:
    try:
        return await provider_service.get_provider(provider_id)

    except ProviderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "",
    response_model=ProviderPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a model provider",
)
async def create_provider(
    payload: ProviderCreate,
) -> ProviderPublic:
    try:
        return await provider_service.create_provider(payload)

    except ProviderNameConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{provider_id}",
    response_model=ProviderPublic,
    summary="Update a model provider",
)
async def update_provider(
    provider_id: UUID,
    payload: ProviderUpdate,
) -> ProviderPublic:
    try:
        return await provider_service.update_provider(
            provider_id,
            payload,
        )

    except ProviderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ProviderNameConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{provider_id}",
    response_model=ProviderDeleteResponse,
    summary="Delete a model provider",
)
async def delete_provider(
    provider_id: UUID,
    response: Response,
) -> ProviderDeleteResponse:
    try:
        await cloud_provider_service.delete(provider_id)

    except ProviderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    response.status_code = status.HTTP_200_OK

    return ProviderDeleteResponse(
        deleted=True,
        provider_id=provider_id,
    )
