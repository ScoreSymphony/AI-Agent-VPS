from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from uuid import UUID

from scoresymphony_contracts import (
    CommandReceipt,
    CommandV1,
    ContractRejection,
    EventV1,
    SubmissionStatus,
    parse_event,
    readonly_json,
)
from scoresymphony_contracts.models import JsonObject, JsonValue


class GatewayClientError(RuntimeError):
    """Raised when the gateway cannot provide a trustworthy V1 result."""


@dataclass(frozen=True, slots=True)
class GatewayHttpResponse:
    status: int
    body: JsonObject | None


class GatewayHttpTransport(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: JsonObject | None = None,
    ) -> GatewayHttpResponse: ...


class UrllibGatewayHttpTransport:
    """Authenticated standard-library transport for Hermes-to-gateway calls."""

    def __init__(self, base_url: str, bearer_token: str, *, timeout_seconds: float = 10.0) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must use http or https")
        if not bearer_token:
            raise ValueError("bearer_token must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._base_url = base_url.rstrip("/") + "/"
        self._token = bearer_token
        self._timeout = timeout_seconds

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: JsonObject | None = None,
    ) -> GatewayHttpResponse:
        if not path.startswith("/") or path.startswith("//"):
            raise GatewayClientError("gateway path must be origin-relative")
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        if json_body is not None:
            data = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            urljoin(self._base_url, path.lstrip("/")),
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                return GatewayHttpResponse(response.status, self._decode(response.read()))
        except HTTPError as error:
            return GatewayHttpResponse(error.code, self._decode(error.read()))
        except (URLError, TimeoutError, OSError) as error:
            raise GatewayClientError("gateway request failed before a response was received") from error

    @staticmethod
    def _decode(raw: bytes) -> JsonObject | None:
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GatewayClientError("gateway returned invalid JSON") from error
        if not isinstance(value, dict):
            raise GatewayClientError("gateway returned non-object JSON")
        return value


@dataclass(frozen=True, slots=True)
class HermesRecoveryPage:
    events: tuple[EventV1, ...]
    next_after_sequence: int
    skipped_event_count: int


class HermesGatewayAdapter:
    """Hermes-facing V1 port over the ScoreSymphony gateway.

    The adapter keeps no lifecycle state and does not persist a recovery cursor.
    The orchestrator advances its cursor only after it has processed a returned
    page successfully.
    """

    def __init__(self, transport: GatewayHttpTransport) -> None:
        self._transport = transport

    def submit(self, command: CommandV1) -> CommandReceipt:
        response = self._transport.request(
            "POST",
            "/v1/commands",
            json_body=self._command(command),
        )
        if response.status != 202 or response.body is None:
            raise self._response_error("command submission", response)
        body = response.body
        command_id = self._uuid(body, "command_id")
        if command_id != command.command_id:
            raise GatewayClientError("gateway receipt command_id does not match submission")
        try:
            status = SubmissionStatus(self._text(body, "status"))
        except ValueError as error:
            raise GatewayClientError("gateway receipt status is invalid") from error
        details = body.get("details")
        if not isinstance(details, dict):
            raise GatewayClientError("gateway receipt details must be an object")
        return CommandReceipt(
            command_id=command_id,
            status=status,
            code=self._text(body, "code"),
            message=self._text(body, "message"),
            details=readonly_json(details),
        )

    def get_events(self, after_sequence: int | None = None) -> tuple[EventV1, ...]:
        return self.get_event_page(after_sequence).events

    def get_event_page(self, after_sequence: int | None = None) -> HermesRecoveryPage:
        cursor = 0 if after_sequence is None else after_sequence
        if cursor < 0:
            raise ValueError("after_sequence must not be negative")
        response = self._transport.request(
            "GET", f"/v1/events?{urlencode({'after_sequence': cursor})}"
        )
        if response.status != 200 or response.body is None:
            raise self._response_error("event recovery", response)
        body = response.body
        next_cursor = self._integer(body, "next_after_sequence")
        skipped = self._integer(body, "skipped_event_count")
        raw_events = body.get("events")
        if next_cursor < cursor:
            raise GatewayClientError("gateway recovery cursor moved backwards")
        if skipped < 0:
            raise GatewayClientError("gateway skipped_event_count must not be negative")
        if not isinstance(raw_events, list):
            raise GatewayClientError("gateway events must be an array")
        events: list[EventV1] = []
        previous_sequence = cursor
        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                raise GatewayClientError("gateway event must be an object")
            parsed = parse_event(raw_event)
            if isinstance(parsed, ContractRejection):
                raise GatewayClientError(
                    f"gateway event violates V1 at {parsed.path}: {parsed.message}"
                )
            if parsed.sequence <= previous_sequence:
                raise GatewayClientError("gateway events are not strictly ordered")
            if parsed.sequence > next_cursor:
                raise GatewayClientError("gateway event sequence exceeds page cursor")
            previous_sequence = parsed.sequence
            events.append(parsed)
        return HermesRecoveryPage(tuple(events), next_cursor, skipped)

    @classmethod
    def _command(cls, command: CommandV1) -> JsonObject:
        return {
            "schema_version": command.schema_version,
            "command_id": str(command.command_id),
            "command": str(command.command),
            "actor": {"type": str(command.actor.type), "id": command.actor.id},
            "task_id": str(command.task_id) if command.task_id else None,
            "execution_id": str(command.execution_id) if command.execution_id else None,
            "correlation_id": str(command.correlation_id),
            "issued_at": command.issued_at.isoformat(),
            "idempotency": {
                "key": command.idempotency.key,
                "scope": command.idempotency.scope,
                "replay_policy": command.idempotency.replay_policy,
            },
            "payload": cls._mutable(command.payload),
        }

    @staticmethod
    def _mutable(value: object) -> JsonValue:
        if isinstance(value, Mapping):
            return {str(key): HermesGatewayAdapter._mutable(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return [HermesGatewayAdapter._mutable(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise TypeError(f"value is not JSON-compatible: {value!r}")

    @staticmethod
    def _text(body: JsonObject, field: str) -> str:
        value = body.get(field)
        if not isinstance(value, str) or not value:
            raise GatewayClientError(f"gateway {field} must be non-empty text")
        return value

    @staticmethod
    def _integer(body: JsonObject, field: str) -> int:
        value = body.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise GatewayClientError(f"gateway {field} must be an integer")
        return value

    @classmethod
    def _uuid(cls, body: JsonObject, field: str) -> UUID:
        try:
            return UUID(cls._text(body, field))
        except ValueError as error:
            raise GatewayClientError(f"gateway {field} must be a UUID") from error

    @staticmethod
    def _response_error(operation: str, response: GatewayHttpResponse) -> GatewayClientError:
        code = None
        if response.body is not None and isinstance(response.body.get("code"), str):
            code = response.body["code"]
        suffix = f" ({code})" if code else ""
        return GatewayClientError(f"gateway {operation} returned HTTP {response.status}{suffix}")
