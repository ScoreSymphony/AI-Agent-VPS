from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Final, TypeAlias
from uuid import UUID


SCHEMA_VERSION_V1: Final = 1

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
ReadonlyJsonValue: TypeAlias = (
    JsonScalar | tuple["ReadonlyJsonValue", ...] | Mapping[str, "ReadonlyJsonValue"]
)
ReadonlyJsonObject: TypeAlias = Mapping[str, ReadonlyJsonValue]


class CommandKind(StrEnum):
    CREATE_TASK = "create_task"
    UPDATE_TASK = "update_task"
    START_WORKER = "start_worker"
    CREATE_WORKTREE = "create_worktree"
    INSPECT_WORKTREE = "inspect_worktree"
    RUN_TESTS = "run_tests"
    REQUEST_REVIEW = "request_review"
    RETRY_RUN = "retry_run"
    CANCEL_RUN = "cancel_run"
    MERGE_TASK = "merge_task"


class EventType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    WORKTREE_CREATED = "worktree.created"
    WORKTREE_INSPECTED = "worktree.inspected"
    RUN_STARTED = "run.started"
    RUN_TESTS_COMPLETED = "run.tests_completed"
    RUN_CANCELLED = "run.cancelled"
    RUN_RETRY_SCHEDULED = "run.retry_scheduled"
    REVIEW_REQUESTED = "review.requested"
    REVIEW_COMPLETED = "review.completed"
    TASK_MERGED = "task.merged"
    COMMAND_SUCCEEDED = "command.succeeded"
    COMMAND_REJECTED = "command.rejected"
    COMMAND_FAILED = "command.failed"
    EVENTS_SNAPSHOT = "events.snapshot"
    RESOURCES_REPORTED = "resources.reported"


class ActorType(StrEnum):
    USER = "user"
    HERMES = "hermes"
    FORGE = "forge"
    WORKER = "worker"
    SYSTEM = "system"


class SubmissionStatus(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


class RejectionCode(StrEnum):
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_IDENTIFIER = "invalid_identifier"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_STATE = "invalid_state"
    SCHEMA_VIOLATION = "schema_violation"


@dataclass(frozen=True, slots=True)
class Actor:
    type: ActorType
    id: str


@dataclass(frozen=True, slots=True)
class Idempotency:
    key: str
    scope: str
    replay_policy: str


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    """Immediate ingress result; terminal execution results arrive as events."""

    command_id: UUID
    status: SubmissionStatus
    code: str
    message: str
    details: ReadonlyJsonObject


@dataclass(frozen=True, slots=True)
class Success:
    code: str
    message: str
    details: ReadonlyJsonObject

    @property
    def retryable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Rejected:
    code: str
    message: str
    details: ReadonlyJsonObject

    @property
    def retryable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Failed:
    code: str
    message: str
    retryable: bool
    details: ReadonlyJsonObject


CommandOutcome: TypeAlias = Success | Rejected | Failed


@dataclass(frozen=True, slots=True)
class ContractRejection:
    code: RejectionCode
    message: str
    path: str


@dataclass(frozen=True, slots=True)
class CommandV1:
    command_id: UUID
    command: CommandKind
    actor: Actor
    task_id: UUID | None
    run_id: UUID | None
    correlation_id: UUID
    issued_at: datetime
    idempotency: Idempotency
    payload: ReadonlyJsonObject
    schema_version: int = SCHEMA_VERSION_V1


@dataclass(frozen=True, slots=True)
class EventV1:
    event_id: UUID
    event_type: EventType
    sequence: int
    occurred_at: datetime
    actor: Actor
    task_id: UUID | None
    run_id: UUID | None
    correlation_id: UUID
    causation_id: UUID | None
    data: ReadonlyJsonObject
    outcome: CommandOutcome | None
    schema_version: int = SCHEMA_VERSION_V1


def readonly_json_value(value: JsonValue) -> ReadonlyJsonValue:
    match value:
        case dict() as mapping:
            return MappingProxyType(
                {key: readonly_json_value(item) for key, item in mapping.items()}
            )
        case list() as items:
            return tuple(readonly_json_value(item) for item in items)
        case str() | int() | float() | bool() | None:
            return value
        case unreachable:
            raise TypeError(f"unsupported JSON value: {unreachable!r}")


def readonly_json(data: JsonObject) -> ReadonlyJsonObject:
    frozen = readonly_json_value(data)
    if not isinstance(frozen, Mapping):
        raise TypeError("JSON object must freeze to a mapping")
    return frozen
