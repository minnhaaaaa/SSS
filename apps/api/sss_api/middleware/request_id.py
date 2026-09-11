"""Attach a validated request identifier to every response."""

from __future__ import annotations

from uuid import UUID, uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp, *, header_name: str = "X-Request-ID") -> None:
        self.app = app
        self.header_name = header_name
        self.header_name_bytes = header_name.lower().encode("ascii")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope, self.header_name_bytes)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((self.header_name_bytes, request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_request_id)


def _request_id(scope: Scope, header_name: bytes) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() == header_name:
            candidate = value.decode("ascii", errors="ignore")
            try:
                return str(UUID(candidate))
            except ValueError:
                break
    return str(uuid4())
