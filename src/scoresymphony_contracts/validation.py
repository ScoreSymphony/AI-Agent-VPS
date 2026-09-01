from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TypeAlias, assert_never
from uuid import UUID

from jsonschema import Draft202012Validator

from .models import (
    Actor,
    ActorType,
    CommandKind,
    CommandV1,
    ContractRejection,
    EventType,
    EventV1,
    Failed,
    Idempotency,
    JsonObject,
    JsonValue,
    Rejected,
    RejectionCode,
    SCHEMA_VERSION_V1,
    Success,
    readonly_json,
)
from .schema_validation import COMMAND_VALIDATOR, EVENT_VALIDATOR, error_path, schema_rejection
from .state_validation import command_state_rejection, event_state_rejection


StateValidator: TypeAlias = Callable[[JsonObject], ContractRejection | None]


def _missing_required_field(
    message: JsonObject,
    validator: Draft202012Validator,
) -> ContractRejection | None:
    required = validator.schema.get("required")
    if not isinstance(required, list):
        return None
    missing = sorted(field for field in required if isinstance(field, str) and field not in message)
    if not missing:
        return None
    field = missing[0]
    return ContractRejection(
        RejectionCode.MISSING_REQUIRED_FIELD,
        f"required field is missing: {field}",
        field,
    )


def _validate(
    raw: JsonValue,
    validator: Draft202012Validator,
    state_validator: StateValidator,
) -> JsonObject | ContractRejection:
    match raw:
        case dict() as message:
            missing_rejection = _missing_required_field(message, validator)
            if missing_rejection is not None:
                return missing_rejection
            version = message.get("schema_version")
            if version != SCHEMA_VERSION_V1:
                return ContractRejection(
                    RejectionCode.UNSUPPORTED_SCHEMA_VERSION,
                    f"unsupported schema version: {version!r}",
                    "schema_version",
                )
            state_rejection = state_validator(message)
            if state_rejection is not None:
                return state_rejection
            errors = sorted(
                validator.iter_errors(message),
                key=lambda error: (error_path(error), error.message),
            )
            if errors:
                return schema_rejection(errors[0])
            return message
        case _:
            return ContractRejection(
                RejectionCode.SCHEMA_VIOLATION,
                "message must be a JSON object",
                "$",
            )


def _text(data: JsonObject, field: str) -> str:
    match data[field]:
        case str() as value:
            return value
        case unreachable:
            raise TypeError(f"validated field {field} is not text: {unreachable!r}")


def _integer(data: JsonObject, field: str) -> int:
    match data[field]:
        case bool() as unreachable:
            raise TypeError(f"validated field {field} is boolean: {unreachable!r}")
        case int() as value:
            return value
        case unreachable:
            raise TypeError(f"validated field {field} is not an integer: {unreachable!r}")


def _object(data: JsonObject, field: str) -> JsonObject:
    match data[field]:
        case dict() as value:
            return value
        case unreachable:
            raise TypeError(f"validated field {field} is not an object: {unreachable!r}")


def _optional_uuid(data: JsonObject, field: str) -> UUID | None:
    match data[field]:
        case None:
            return None
        case str() as value:
            return UUID(value)
        case unreachable:
            raise TypeError(f"validated field {field} is not nullable UUID text: {unreachable!r}")


def _timestamp(data: JsonObject, field: str) -> datetime:
    value = datetime.fromisoformat(_text(data, field).replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise TypeError(f"validated field {field} has no timezone")
    return value


def _actor(data: JsonObject) -> Actor:
    actor = _object(data, "actor")
    return Actor(type=ActorType(_text(actor, "type")), id=_text(actor, "id"))


def parse_command(raw: JsonValue) -> CommandV1 | ContractRejection:
    validated = _validate(raw, COMMAND_VALIDATOR, command_state_rejection)
    if isinstance(validated, ContractRejection):
        return validated
    idempotency = _object(validated, "idempotency")
    return CommandV1(
        command_id=UUID(_text(validated, "command_id")),
        command=CommandKind(_text(validated, "command")),
        actor=_actor(validated),
        task_id=_optional_uuid(validated, "task_id"),
        run_id=_optional_uuid(validated, "run_id"),
        correlation_id=UUID(_text(validated, "correlation_id")),
        issued_at=_timestamp(validated, "issued_at"),
        idempotency=Idempotency(
            key=_text(idempotency, "key"),
            scope=_text(idempotency, "scope"),
            replay_policy=_text(idempotency, "replay_policy"),
        ),
        payload=readonly_json(_object(validated, "payload")),
    )


def _outcome(data: JsonObject) -> Success | Rejected | Failed | None:
    match data["outcome"]:
        case None:
            return None
        case dict() as value:
            details = readonly_json(_object(value, "details"))
            match _text(value, "status"):
                case "success":
                    return Success(_text(value, "code"), _text(value, "message"), details)
                case "rejected":
                    return Rejected(_text(value, "code"), _text(value, "message"), details)
                case "failed":
                    retryable = value["retryable"]
                    match retryable:
                        case bool() as flag:
                            return Failed(
                                _text(value, "code"), _text(value, "message"), flag, details
                            )
                        case unreachable:
                            raise TypeError(f"validated retryable is not boolean: {unreachable!r}")
                case unreachable:
                    assert_never(unreachable)
        case unreachable:
            raise TypeError(f"validated outcome is invalid: {unreachable!r}")


def parse_event(raw: JsonValue) -> EventV1 | ContractRejection:
    validated = _validate(raw, EVENT_VALIDATOR, event_state_rejection)
    if isinstance(validated, ContractRejection):
        return validated
    return EventV1(
        event_id=UUID(_text(validated, "event_id")),
        event_type=EventType(_text(validated, "event_type")),
        sequence=_integer(validated, "sequence"),
        occurred_at=_timestamp(validated, "occurred_at"),
        actor=_actor(validated),
        task_id=_optional_uuid(validated, "task_id"),
        run_id=_optional_uuid(validated, "run_id"),
        correlation_id=UUID(_text(validated, "correlation_id")),
        causation_id=_optional_uuid(validated, "causation_id"),
        data=readonly_json(_object(validated, "data")),
        outcome=_outcome(validated),
    )
