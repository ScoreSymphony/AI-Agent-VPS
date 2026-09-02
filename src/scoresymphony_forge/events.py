from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlencode
from uuid import UUID

from scoresymphony_contracts.models import JsonObject, JsonValue, EventV1
from scoresymphony_contracts.validation import parse_event
from scoresymphony_contracts.models import ContractRejection

from .transport import ForgeHttpTransport, ForgeTransportError


class ForgeEventProjectionError(ForgeTransportError):
    """Raised when Forge history violates its public contract or V1 projection rules."""


@dataclass(frozen=True, slots=True)
class ForgeEventPage:
    events: tuple[EventV1, ...]
    next_after_sequence: int
    skipped_event_count: int


_EVENT_TYPES = {
    "task.created": "task.created",
    "task.updated": "task.updated",
    "task.status_changed": "task.status_changed",
    "task.transitioned": "task.status_changed",
    "workspace.created": "workspace.created",
    "execution.started": "execution.started",
    "execution.completed": "execution.completed",
    "execution.failed": "execution.failed",
    "execution.cancelled": "execution.cancelled",
    "execution.retry_scheduled": "execution.retry_scheduled",
    "review.started": "review.started",
    "review.completed": "review.completed",
    "task.merged": "task.merged",
}


class ForgeEventAdapter:
    """Reads durable Forge history and projects supported lifecycle events to V1."""

    def __init__(self, transport: ForgeHttpTransport, *, page_limit: int = 100) -> None:
        if not 1 <= page_limit <= 500:
            raise ValueError("page_limit must be between 1 and 500")
        self._transport = transport
        self._page_limit = page_limit

    def get_events(self, after_sequence: int | None = None) -> tuple[EventV1, ...]:
        return self.get_event_page(after_sequence).events

    def get_event_page(self, after_sequence: int | None = None) -> ForgeEventPage:
        cursor = 0 if after_sequence is None else after_sequence
        if cursor < 0:
            raise ValueError("after_sequence must not be negative")
        query = urlencode({"after_sequence": cursor, "limit": self._page_limit})
        response = self._transport.request("GET", f"/api/v1/events?{query}")
        if response.status != 200:
            raise ForgeTransportError(f"Forge history read returned HTTP {response.status}")
        body = response.body
        if body is None:
            raise ForgeEventProjectionError("Forge history response body is missing")
        raw_events = body.get("events")
        response_cursor = body.get("after_sequence")
        response_limit = body.get("limit")
        next_cursor = body.get("next_after_sequence")
        if response_cursor != cursor:
            raise ForgeEventProjectionError("Forge history response cursor does not match request")
        if response_limit != self._page_limit:
            raise ForgeEventProjectionError("Forge history response limit does not match request")
        if isinstance(next_cursor, bool) or not isinstance(next_cursor, int):
            raise ForgeEventProjectionError("next_after_sequence must be an integer")
        if next_cursor < cursor:
            raise ForgeEventProjectionError("Forge history cursor moved backwards")
        if not isinstance(raw_events, list):
            raise ForgeEventProjectionError("Forge history events must be an array")
        if len(raw_events) > self._page_limit:
            raise ForgeEventProjectionError("Forge history page exceeds requested limit")

        projected: list[EventV1] = []
        skipped = 0
        previous_sequence = cursor
        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                raise ForgeEventProjectionError("Forge history event must be an object")
            sequence = self._integer(raw_event, "sequence")
            if sequence <= previous_sequence:
                raise ForgeEventProjectionError("Forge history events are not strictly ordered")
            previous_sequence = sequence
            event = self._project(raw_event)
            if event is None:
                skipped += 1
            else:
                projected.append(event)
        if raw_events and next_cursor != previous_sequence:
            raise ForgeEventProjectionError("Forge history cursor does not match the last event")
        return ForgeEventPage(tuple(projected), next_cursor, skipped)

    def _project(self, raw: Mapping[str, JsonValue]) -> EventV1 | None:
        forge_type = self._text(raw, "event_type")
        event_type = _EVENT_TYPES.get(forge_type)
        if event_type is None:
            return None
        payload = self._payload(raw)
        entity_id = self._uuid_text(raw, "entity_id")
        task_id: str | None
        execution_id: str | None = None
        if event_type.startswith("execution."):
            execution_id = entity_id
            task_id = self._payload_uuid(payload, "task_id")
        elif event_type.startswith("task."):
            task_id = entity_id
        else:
            task_id = self._payload_uuid(payload, "task_id", required=False)
            if task_id is None and raw.get("scope_type") == "task":
                task_id = self._uuid_text(raw, "scope_id")
        actor_type = self._actor_type(self._text(raw, "actor_type"))
        actor_id = raw.get("actor_id")
        if not isinstance(actor_id, str) or not actor_id:
            actor_id = "forge-runtime"
        message: JsonObject = {
            "schema_version": 1,
            "event_id": self._uuid_text(raw, "id"),
            "event_type": event_type,
            "sequence": self._integer(raw, "sequence"),
            "occurred_at": self._text(raw, "created_at"),
            "actor": {"type": actor_type, "id": actor_id},
            "task_id": task_id,
            "execution_id": execution_id,
            "correlation_id": self._uuid_text(raw, "correlation_id"),
            "causation_id": self._optional_uuid_text(raw, "causation_id"),
            "data": payload,
            "outcome": None,
        }
        parsed = parse_event(message)
        if isinstance(parsed, ContractRejection):
            raise ForgeEventProjectionError(
                f"projected event violates V1 at {parsed.path}: {parsed.message}"
            )
        return parsed

    @staticmethod
    def _actor_type(value: str) -> str:
        if value == "user":
            return "user"
        if value == "hermes":
            return "hermes"
        if value == "worker":
            return "worker"
        if value == "system":
            return "system"
        return "forge"

    @staticmethod
    def _payload(raw: Mapping[str, JsonValue]) -> JsonObject:
        value = raw.get("payload_json")
        if not isinstance(value, str):
            raise ForgeEventProjectionError("payload_json must be a string")
        try:
            payload = json.loads(value)
        except json.JSONDecodeError as error:
            raise ForgeEventProjectionError("payload_json is invalid JSON") from error
        if not isinstance(payload, dict):
            raise ForgeEventProjectionError("payload_json must contain a JSON object")
        return payload

    @staticmethod
    def _text(raw: Mapping[str, JsonValue], field: str) -> str:
        value = raw.get(field)
        if not isinstance(value, str) or not value:
            raise ForgeEventProjectionError(f"{field} must be non-empty text")
        return value

    @staticmethod
    def _integer(raw: Mapping[str, JsonValue], field: str) -> int:
        value = raw.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ForgeEventProjectionError(f"{field} must be an integer")
        return value

    @classmethod
    def _uuid_text(cls, raw: Mapping[str, JsonValue], field: str) -> str:
        value = cls._text(raw, field)
        try:
            return str(UUID(value))
        except ValueError as error:
            raise ForgeEventProjectionError(f"{field} must be a UUID") from error

    @classmethod
    def _optional_uuid_text(cls, raw: Mapping[str, JsonValue], field: str) -> str | None:
        if raw.get(field) is None:
            return None
        return cls._uuid_text(raw, field)

    @staticmethod
    def _payload_uuid(payload: JsonObject, field: str, *, required: bool = True) -> str | None:
        value = payload.get(field)
        if value is None and not required:
            return None
        if not isinstance(value, str):
            raise ForgeEventProjectionError(f"payload.{field} must be a UUID")
        try:
            return str(UUID(value))
        except ValueError as error:
            raise ForgeEventProjectionError(f"payload.{field} must be a UUID") from error
