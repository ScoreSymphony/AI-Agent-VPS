from __future__ import annotations

from copy import deepcopy
from typing import assert_never

import pytest

from scoresymphony_contracts import (
    ContractRejection,
    EventV1,
    Failed,
    JsonObject,
    Rejected,
    RejectionCode,
    Success,
    parse_command,
    parse_event,
)


COMMAND_ID = "6fd31d31-e8d9-4ac8-9f65-b7ae97976ac2"
CORRELATION_ID = "159d4955-1584-4888-b7bd-314c02a515a3"
PROJECT_ID = "2b874ced-93c6-4af9-b3ab-c5a4d3d39cec"
TASK_ID = "9a9a0d0d-3c62-4a4a-9ef7-80fb7b3d429c"
EXECUTION_ID = "a7640bf2-e3ed-4d76-a72a-d64e58722ef8"
EVENT_ID = "fd6dde8c-7414-48f9-b1c0-7c40f42a4e44"


def valid_create_task() -> JsonObject:
    return {
        "schema_version": 1,
        "command_id": COMMAND_ID,
        "command": "create_task",
        "actor": {"type": "hermes", "id": "platform-orchestrator"},
        "task_id": None,
        "execution_id": None,
        "correlation_id": CORRELATION_ID,
        "issued_at": "2026-09-01T16:00:00Z",
        "idempotency": {
            "key": "fixture-create-task-1",
            "scope": "command",
            "replay_policy": "return_previous",
        },
        "payload": {"project_id": PROJECT_ID, "title": "Update fixture file"},
    }


def valid_event() -> JsonObject:
    return {
        "schema_version": 1,
        "event_id": EVENT_ID,
        "event_type": "task.created",
        "sequence": 1,
        "occurred_at": "2026-09-01T16:00:01Z",
        "actor": {"type": "forge", "id": "execution-engine"},
        "task_id": TASK_ID,
        "execution_id": None,
        "correlation_id": CORRELATION_ID,
        "causation_id": COMMAND_ID,
        "data": {"state": "created"},
        "outcome": None,
    }


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("schema_version", 2, RejectionCode.UNSUPPORTED_SCHEMA_VERSION),
        ("command_id", "not-a-uuid", RejectionCode.INVALID_IDENTIFIER),
        ("correlation_id", "not-a-uuid", RejectionCode.INVALID_IDENTIFIER),
        ("issued_at", "2026-09-01T16:00:00", RejectionCode.INVALID_TIMESTAMP),
    ],
)
def test_parse_command_when_envelope_is_invalid_returns_structured_rejection(
    field: str,
    value: str | int,
    expected_code: RejectionCode,
) -> None:
    raw = valid_create_task()
    raw[field] = value
    result = parse_command(raw)
    assert isinstance(result, ContractRejection)
    assert result.code is expected_code
    assert result.path == field


def test_parse_command_when_required_field_is_missing_rejects_deterministically() -> None:
    raw = valid_create_task()
    del raw["actor"]
    first = parse_command(raw)
    second = parse_command(deepcopy(raw))
    assert first == second
    assert isinstance(first, ContractRejection)
    assert first.code is RejectionCode.MISSING_REQUIRED_FIELD
    assert first.path == "actor"


@pytest.mark.parametrize("malformed", [[], {}])
def test_parse_command_when_discriminator_is_not_text_returns_structured_rejection(
    malformed: JsonObject | list[object],
) -> None:
    raw = valid_create_task()
    raw["command"] = malformed
    result = parse_command(raw)
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.SCHEMA_VIOLATION
    assert result.path == "command"


@pytest.mark.parametrize(
    ("field", "malformed"),
    [
        ("task_id", []),
        ("task_id", "not-a-uuid"),
        ("execution_id", []),
        ("execution_id", "not-a-uuid"),
    ],
)
def test_parse_create_task_when_optional_identifier_is_malformed_rejects_identifier(
    field: str,
    malformed: str | list[object],
) -> None:
    raw = valid_create_task()
    raw[field] = malformed
    result = parse_command(raw)
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.INVALID_IDENTIFIER
    assert result.path == field


@pytest.mark.parametrize(
    ("command", "task_id", "execution_id"),
    [
        ("update_task", None, None),
        ("start_task", None, None),
        ("submit_task", None, None),
        ("approve_task", None, None),
        ("cancel_task", None, None),
        ("retry_execution", TASK_ID, None),
        ("cancel_execution", TASK_ID, None),
        ("create_task", TASK_ID, None),
        ("create_task", None, EXECUTION_ID),
    ],
)
def test_parse_command_when_identifier_state_is_invalid_rejects_semantics(
    command: str,
    task_id: str | None,
    execution_id: str | None,
) -> None:
    raw = valid_create_task()
    raw["command"] = command
    raw["task_id"] = task_id
    raw["execution_id"] = execution_id
    if command == "update_task":
        raw["payload"] = {"version": 1, "title": "Changed"}
    elif command == "request_changes_task":
        raw["payload"] = {"version": 1, "reason": "Needs changes"}
    elif command in {"start_task", "submit_task", "approve_task", "cancel_task"}:
        raw["payload"] = {"version": 1}
    else:
        raw["payload"] = {}
    result = parse_command(raw)
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.INVALID_STATE


@pytest.mark.parametrize(
    ("command", "payload"),
    [
        ("create_task", {"title": "Missing project"}),
        ("update_task", {"title": "Missing version"}),
        ("update_task", {"version": 1}),
        ("start_task", {}),
        ("submit_task", {"version": 0}),
        ("request_changes_task", {"version": 1}),
        ("approve_task", {"version": 1, "unexpected": True}),
        ("retry_execution", {"unexpected": True}),
    ],
)
def test_parse_command_when_command_payload_contract_is_invalid_rejects_schema(
    command: str,
    payload: JsonObject,
) -> None:
    raw = valid_create_task()
    raw["command"] = command
    raw["payload"] = payload
    if command != "create_task":
        raw["task_id"] = TASK_ID
    if command in {"retry_execution", "cancel_execution"}:
        raw["execution_id"] = EXECUTION_ID
    result = parse_command(raw)
    assert isinstance(result, ContractRejection)
    assert result.code in {
        RejectionCode.MISSING_REQUIRED_FIELD,
        RejectionCode.SCHEMA_VIOLATION,
        RejectionCode.INVALID_IDENTIFIER,
    }


@pytest.mark.parametrize(
    "legacy",
    [
        "start_worker",
        "create_worktree",
        "inspect_worktree",
        "run_tests",
        "request_review",
        "retry_run",
        "cancel_run",
        "merge_task",
        "get_events",
        "get_resources",
    ],
)
def test_parse_command_when_legacy_or_query_command_is_used_rejects(legacy: str) -> None:
    raw = valid_create_task()
    raw["command"] = legacy
    raw["payload"] = {}
    result = parse_command(raw)
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.SCHEMA_VIOLATION
    assert result.path == "command"


@pytest.mark.parametrize(
    "event_type", ["command.succeeded", "command.rejected", "command.failed"]
)
def test_parse_event_when_terminal_event_has_no_outcome_rejects_state(event_type: str) -> None:
    raw = valid_event()
    raw["event_type"] = event_type
    result = parse_event(raw)
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.INVALID_STATE
    assert result.path == "outcome"


def test_parse_event_when_terminal_event_has_no_causation_rejects_state() -> None:
    raw = valid_event()
    raw["event_type"] = "command.failed"
    raw["causation_id"] = None
    raw["outcome"] = {
        "status": "failed",
        "code": "execution_failed",
        "message": "Failed",
        "retryable": True,
        "details": {},
    }
    result = parse_event(raw)
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.INVALID_STATE
    assert result.path == "causation_id"


@pytest.mark.parametrize(
    ("event_type", "task_id", "execution_id", "path"),
    [
        ("task.created", None, None, "task_id"),
        ("task.updated", TASK_ID, EXECUTION_ID, "execution_id"),
        ("workspace.created", None, None, "task_id"),
        ("review.started", TASK_ID, EXECUTION_ID, "execution_id"),
        ("task.merged", None, None, "task_id"),
        ("execution.started", None, EXECUTION_ID, "task_id"),
        ("execution.completed", TASK_ID, None, "execution_id"),
        ("execution.failed", TASK_ID, None, "execution_id"),
        ("events.snapshot", TASK_ID, None, "task_id"),
        ("resources.reported", None, EXECUTION_ID, "execution_id"),
    ],
)
def test_parse_event_when_identifier_state_mismatches_event_family_rejects_state(
    event_type: str,
    task_id: str | None,
    execution_id: str | None,
    path: str,
) -> None:
    raw = valid_event()
    raw["event_type"] = event_type
    raw["task_id"] = task_id
    raw["execution_id"] = execution_id
    result = parse_event(raw)
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.INVALID_STATE
    assert result.path == path


def test_outcome_variants_are_exhaustive() -> None:
    raw = valid_event()
    raw["event_type"] = "command.failed"
    raw["outcome"] = {
        "status": "failed",
        "code": "execution_failed",
        "message": "Worker failed",
        "retryable": True,
        "details": {},
    }
    result = parse_event(raw)
    assert isinstance(result, EventV1)
    match result.outcome:
        case Success() | Rejected() | Failed():
            pass
        case None:
            pytest.fail("terminal event must have an outcome")
        case unreachable:
            assert_never(unreachable)
