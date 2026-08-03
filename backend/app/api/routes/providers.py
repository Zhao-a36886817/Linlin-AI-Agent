from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.providers.models import (
    ProviderCreate,
    ProviderDeleteResponse,
    ProviderListResponse,
    ProviderPublic,
    ProviderUpdate,
)
from app.providers.service import (
    ProviderNameConflictError,
    ProviderNotFoundError,
    provider_service,
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
        await provider_service.delete_provider(provider_id)

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
