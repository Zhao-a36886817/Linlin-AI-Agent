from __future__ import annotations

from collections.abc import Mapping

from fastapi.responses import ORJSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PUBLIC_API_VERSION = "1"
PUBLIC_API_SUPPORTED_VERSIONS = (PUBLIC_API_VERSION,)
API_VERSION_HEADER = "X-Linlin-API-Version"
API_STABILITY_HEADER = "X-Linlin-API-Stability"
API_STABILITY = "stable"
DEPRECATION_MIN_MINOR_RELEASES = 2
DEPRECATION_MIN_DAYS = 90

# Longest matching prefix owns the route. Tests fail when a public route is added
# without an explicit owner, keeping the published inventory reviewable.
PUBLIC_API_OWNERS: Mapping[str, str] = {
    "/api/advanced-runtime": "Advanced Runtime",
    "/api/runtime-control": "Runtime Control",
    "/api/code-generation": "Code Generation",
    "/api/providers": "Provider Runtime",
    "/api/training": "Training Runtime",
    "/api/models": "Provider Runtime",
    "/api/agents": "Agent Runtime",
    "/api/system": "Platform API",
    "/api/health": "Platform API",
    "/api/chat": "Chat Runtime",
}


def public_api_owner(path: str) -> str | None:
    for prefix in sorted(PUBLIC_API_OWNERS, key=len, reverse=True):
        if path == prefix or path.startswith(f"{prefix}/"):
            return PUBLIC_API_OWNERS[prefix]
    return None


class ApiContractMiddleware:
    """Negotiate the stable public API contract without changing route URLs."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not _is_public_api_path(path):
            await self.app(scope, receive, send)
            return

        requested_version = Headers(scope=scope).get(API_VERSION_HEADER)

        async def send_with_contract_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers[API_VERSION_HEADER] = PUBLIC_API_VERSION
                headers[API_STABILITY_HEADER] = API_STABILITY
                headers.add_vary_header(API_VERSION_HEADER)
            await send(message)

        if requested_version and requested_version not in PUBLIC_API_SUPPORTED_VERSIONS:
            response = ORJSONResponse(
                status_code=406,
                content={
                    "detail": "Requested public API version is not supported.",
                    "requested_version": requested_version,
                    "supported_versions": list(PUBLIC_API_SUPPORTED_VERSIONS),
                },
            )
            await response(scope, receive, send_with_contract_headers)
            return

        await self.app(scope, receive, send_with_contract_headers)


def _is_public_api_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")
