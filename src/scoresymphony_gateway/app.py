from __future__ import annotations

import hmac
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import parse_qs

from scoresymphony_contracts import (
    CommandReceipt,
    ContractRejection,
    EventV1,
    Failed,
    Rejected,
    Success,
    parse_command,
)
from scoresymphony_contracts.models import JsonObject, JsonValue
from scoresymphony_forge import (
    ForgeDispatchUncertainError,
    ForgeEventPage,
    ForgeEventProjectionError,
    ForgeIntegrationAdapter,
    ForgeTransportError,
)


StartResponse = Callable[[str, list[tuple[str, str]]], object]


class GatewayAdapter(Protocol):
    def submit(self, command) -> CommandReceipt: ...

    def get_event_page(self, after_sequence: int | None = None) -> ForgeEventPage: ...


@dataclass(frozen=True, slots=True)
class ApiResponse:
    status: int
    body: JsonObject


class GatewayApplication:
    """Minimal WSGI API; Forge remains the only lifecycle authority."""

    def __init__(
        self,
        adapter: GatewayAdapter,
        client_bearer_token: str,
        *,
        max_body_bytes: int = 1_048_576,
    ) -> None:
        if not client_bearer_token:
            raise ValueError("client_bearer_token must not be empty")
        if max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive")
        self._adapter = adapter
        self._client_bearer_token = client_bearer_token
        self._max_body_bytes = max_body_bytes

    def __call__(self, environ: Mapping[str, object], start_response: StartResponse) -> Iterable[bytes]:
        response = self.handle(environ)
        payload = json.dumps(response.body, separators=(",", ":")).encode("utf-8")
        status = {
            200: "200 OK",
            202: "202 Accepted",
            401: "401 Unauthorized",
            400: "400 Bad Request",
            404: "404 Not Found",
            405: "405 Method Not Allowed",
            413: "413 Content Too Large",
            502: "502 Bad Gateway",
            503: "503 Service Unavailable",
        }[response.status]
        start_response(
            status,
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(payload))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [payload]

    def handle(self, environ: Mapping[str, object]) -> ApiResponse:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        if path == "/healthz":
            return self._method(method, "GET", lambda: ApiResponse(200, {"status": "ok"}))
        if path == "/readyz":
            return self._method(method, "GET", self._ready)
        if path == "/v1/commands":
            if not self._authorized(environ):
                return ApiResponse(401, self._error("auth.unauthorized", "Authentication required"))
            return self._method(method, "POST", lambda: self._submit(environ))
        if path == "/v1/events":
            if not self._authorized(environ):
                return ApiResponse(401, self._error("auth.unauthorized", "Authentication required"))
            return self._method(method, "GET", lambda: self._events(environ))
        return ApiResponse(404, self._error("route.not_found", "Route not found"))

    def _authorized(self, environ: Mapping[str, object]) -> bool:
        supplied = str(environ.get("HTTP_AUTHORIZATION", ""))
        expected = f"Bearer {self._client_bearer_token}"
        return hmac.compare_digest(supplied, expected)

    @staticmethod
    def _method(method: str, expected: str, handler: Callable[[], ApiResponse]) -> ApiResponse:
        if method != expected:
            return ApiResponse(405, GatewayApplication._error("method.not_allowed", "Method not allowed"))
        return handler()

    def _ready(self) -> ApiResponse:
        try:
            self._adapter.get_event_page(0)
        except (ForgeTransportError, ForgeEventProjectionError):
            return ApiResponse(503, self._error("forge.not_ready", "Forge recovery API is unavailable"))
        return ApiResponse(200, {"status": "ready"})

    def _submit(self, environ: Mapping[str, object]) -> ApiResponse:
        content_type = str(environ.get("CONTENT_TYPE", "")).split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return ApiResponse(400, self._error("request.content_type", "Content-Type must be application/json"))
        raw_length = str(environ.get("CONTENT_LENGTH", ""))
        try:
            length = int(raw_length)
        except ValueError:
            return ApiResponse(400, self._error("request.content_length", "Content-Length is invalid"))
        if length < 0:
            return ApiResponse(400, self._error("request.content_length", "Content-Length is invalid"))
        if length > self._max_body_bytes:
            return ApiResponse(413, self._error("request.too_large", "Request body exceeds the configured limit"))
        stream = environ.get("wsgi.input")
        if stream is None or not hasattr(stream, "read"):
            return ApiResponse(400, self._error("request.body_missing", "Request body is missing"))
        raw = stream.read(length)
        try:
            message = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ApiResponse(400, self._error("request.invalid_json", "Request body is invalid JSON"))
        command = parse_command(message)
        if isinstance(command, ContractRejection):
            return ApiResponse(
                400,
                {
                    "code": str(command.code),
                    "message": command.message,
                    "path": command.path,
                },
            )
        try:
            receipt = self._adapter.submit(command)
        except ForgeDispatchUncertainError:
            return ApiResponse(503, self._error("forge.dispatch_uncertain", "Forge command outcome is uncertain"))
        except ForgeTransportError:
            return ApiResponse(502, self._error("forge.transport_error", "Forge command transport failed"))
        return ApiResponse(202, self._receipt(receipt))

    def _events(self, environ: Mapping[str, object]) -> ApiResponse:
        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(query) - {"after_sequence"} or len(query.get("after_sequence", [])) > 1:
            return ApiResponse(400, self._error("events.invalid_query", "Only one after_sequence is allowed"))
        raw_cursor = query.get("after_sequence", ["0"])[0]
        try:
            cursor = int(raw_cursor)
        except ValueError:
            return ApiResponse(400, self._error("events.invalid_cursor", "after_sequence must be an integer"))
        if cursor < 0:
            return ApiResponse(400, self._error("events.invalid_cursor", "after_sequence must not be negative"))
        try:
            page = self._adapter.get_event_page(cursor)
        except ForgeEventProjectionError:
            return ApiResponse(502, self._error("events.invalid_upstream", "Forge returned invalid event history"))
        except ForgeTransportError:
            return ApiResponse(503, self._error("events.unavailable", "Forge event history is unavailable"))
        return ApiResponse(
            200,
            {
                "next_after_sequence": page.next_after_sequence,
                "skipped_event_count": page.skipped_event_count,
                "events": [self._event(event) for event in page.events],
            },
        )

    @staticmethod
    def _receipt(receipt: CommandReceipt) -> JsonObject:
        return {
            "command_id": str(receipt.command_id),
            "status": str(receipt.status),
            "code": receipt.code,
            "message": receipt.message,
            "details": GatewayApplication._mutable(receipt.details),
        }

    @staticmethod
    def _event(event: EventV1) -> JsonObject:
        outcome: JsonObject | None = None
        if event.outcome is not None:
            outcome = {
                "status": "success" if isinstance(event.outcome, Success) else "rejected" if isinstance(event.outcome, Rejected) else "failed",
                "code": event.outcome.code,
                "message": event.outcome.message,
                "details": GatewayApplication._mutable(event.outcome.details),
            }
            if isinstance(event.outcome, (Rejected, Failed)):
                outcome["retryable"] = event.outcome.retryable
        return {
            "schema_version": event.schema_version,
            "event_id": str(event.event_id),
            "event_type": str(event.event_type),
            "sequence": event.sequence,
            "occurred_at": event.occurred_at.isoformat(),
            "actor": {"type": str(event.actor.type), "id": event.actor.id},
            "task_id": str(event.task_id) if event.task_id else None,
            "execution_id": str(event.execution_id) if event.execution_id else None,
            "correlation_id": str(event.correlation_id),
            "causation_id": str(event.causation_id) if event.causation_id else None,
            "data": GatewayApplication._mutable(event.data),
            "outcome": outcome,
        }

    @staticmethod
    def _mutable(value: object) -> JsonValue:
        if isinstance(value, Mapping):
            return {str(key): GatewayApplication._mutable(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return [GatewayApplication._mutable(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise TypeError(f"value is not JSON-compatible: {value!r}")

    @staticmethod
    def _error(code: str, message: str) -> JsonObject:
        return {"code": code, "message": message}
