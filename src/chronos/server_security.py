"""Certification-only GraphQL security boundary stub.

This public harness validates Ariadne schema/scalar/ASGI compatibility without
copying the full CHRONOS server implementation. It mirrors only the API-key
surface exercised by the private integration regression; production security
middleware is tested separately in the private candidate.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ServerSecuritySettings:
    """Minimal settings surface required by ``ChronosGraphQL`` in this harness."""

    api_key: str | None = None
    allow_unauthenticated_local: bool = True

    @classmethod
    def from_env(cls) -> "ServerSecuritySettings":
        return cls()

    def validate_bind_host(self, host: str) -> None:
        del host


class ChronosSecurityMiddleware:
    """Minimal API-key ASGI boundary used only by the GraphQL certification harness."""

    def __init__(self, app: Any, settings: ServerSecuritySettings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") == "http" and self.settings.api_key is not None:
            headers = {
                key.decode("latin-1").lower(): value.decode("latin-1")
                for key, value in scope.get("headers", [])
            }
            supplied = headers.get("x-api-key", "").strip()
            if not supplied:
                await self._send_json(
                    send,
                    401,
                    b'{"error":"Authentication required","code":"AUTH_REQUIRED"}',
                )
                return
            if not hmac.compare_digest(supplied, self.settings.api_key):
                await self._send_json(
                    send,
                    403,
                    b'{"error":"Invalid API key","code":"INVALID_KEY"}',
                )
                return
        await self.app(scope, receive, send)

    @staticmethod
    async def _send_json(send: Any, status: int, body: bytes) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
