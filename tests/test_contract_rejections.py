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
TASK_ID = "9a9a0d0d-3c62-4a4a-9ef7-80fb7b3d429c"
RUN_ID = "a7640bf2-e3ed-4d76-a72a-d64e58722ef8"
EVENT_ID = "fd6dde8c-7414-48f9-b1c0-7c40f42a4e44"


def valid_create_task() -> JsonObject:
    return {
        "schema_version": 1,
        "command_id": COMMAND_ID,
        "command": "create_task",
        "actor": {"type": "hermes", "id": "platform-orchestrator"},
        "task_id": None,
        "run_id": None,
        "correlation_id": CORRELATION_ID,
        "issued_at": "2026-09-01T16:00:00Z",
        "idempotency": {
            "key": "fixture-create-task-1",
            "scope": "command",
            "replay_policy": "return_previous",
        },
        "payload": {
            "title": "Update fixture file",
            "worker_class": "shell",
            "requires_review": True,
        },
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
        "run_id": None,
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
    # Given
    raw = valid_create_task()
    raw[field] = value

    # When
    result = parse_command(raw)

    # Then
    assert isinstance(result, ContractRejection)
    assert result.code is expected_code
    assert result.path == field
    assert result.message


def test_parse_command_when_required_field_is_missing_rejects_deterministically() -> None:
    # Given
    raw = valid_create_task()
    del raw["actor"]

    # When
    first = parse_command(raw)
    second = parse_command(deepcopy(raw))

    # Then
    assert isinstance(first, ContractRejection)
    assert first == second
    assert first.code is RejectionCode.MISSING_REQUIRED_FIELD
    assert first.path == "actor"


def test_parse_command_when_schema_version_is_missing_reports_missing_field() -> None:
    # Given
    raw = valid_create_task()
    del raw["schema_version"]

    # When
    result = parse_command(raw)

    # Then
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.MISSING_REQUIRED_FIELD
    assert result.path == "schema_version"


@pytest.mark.parametrize(
    ("command", "task_id", "run_id"),
    [
        ("run_tests", TASK_ID, None),
        ("request_review", None, RUN_ID),
        ("cancel_run", TASK_ID, None),
        ("merge_task", TASK_ID, None),
        ("create_task", TASK_ID, None),
    ],
)
def test_parse_command_when_identifier_state_is_invalid_rejects_semantics(
    command: str,
    task_id: str | None,
    run_id: str | None,
) -> None:
    # Given
    raw = valid_create_task()
    raw["command"] = command
    raw["task_id"] = task_id
    raw["run_id"] = run_id
    raw["payload"] = {}

    # When
    result = parse_command(raw)

    # Then
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.INVALID_STATE


@pytest.mark.parametrize(
    "event_type",
    ["command.succeeded", "command.rejected", "command.failed"],
)
def test_parse_event_when_terminal_event_has_no_outcome_rejects_state(
    event_type: str,
) -> None:
    # Given
    raw = valid_event()
    raw["event_type"] = event_type

    # When
    result = parse_event(raw)

    # Then
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.INVALID_STATE
    assert result.path == "outcome"


@pytest.mark.parametrize(
    ("event_type", "outcome_status"),
    [
        ("command.succeeded", "rejected"),
        ("command.succeeded", "failed"),
        ("command.rejected", "success"),
        ("command.rejected", "failed"),
        ("command.failed", "success"),
        ("command.failed", "rejected"),
    ],
)
def test_parse_event_when_terminal_outcome_mismatches_rejects_state(
    event_type: str,
    outcome_status: str,
) -> None:
    # Given
    raw = valid_event()
    raw["event_type"] = event_type
    raw["outcome"] = {
        "status": outcome_status,
        "code": "state_conflict",
        "message": "Mismatched terminal result",
        "retryable": outcome_status == "failed",
        "details": {},
    }

    # When
    result = parse_event(raw)

    # Then
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.INVALID_STATE
    assert result.path == "outcome.status"


def test_parse_event_when_non_terminal_event_has_outcome_rejects_state() -> None:
    # Given
    raw = valid_event()
    raw["outcome"] = {
        "status": "success",
        "code": "command_completed",
        "message": "Not valid for task event",
        "details": {},
    }

    # When
    result = parse_event(raw)

    # Then
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.INVALID_STATE
    assert result.path == "outcome"


@pytest.mark.parametrize(
    ("event_type", "task_id", "run_id", "path"),
    [
        ("task.created", None, None, "task_id"),
        ("task.updated", TASK_ID, RUN_ID, "run_id"),
        ("worktree.created", None, None, "task_id"),
        ("worktree.inspected", TASK_ID, RUN_ID, "run_id"),
        ("run.started", None, RUN_ID, "task_id"),
        ("run.tests_completed", TASK_ID, None, "run_id"),
        ("review.requested", TASK_ID, None, "run_id"),
        ("review.completed", None, RUN_ID, "task_id"),
        ("task.merged", TASK_ID, None, "run_id"),
        ("events.snapshot", TASK_ID, None, "task_id"),
        ("resources.reported", None, RUN_ID, "run_id"),
    ],
)
def test_parse_event_when_identifier_state_mismatches_event_family_rejects_state(
    event_type: str,
    task_id: str | None,
    run_id: str | None,
    path: str,
) -> None:
    # Given
    raw = valid_event()
    raw["event_type"] = event_type
    raw["task_id"] = task_id
    raw["run_id"] = run_id

    # When
    result = parse_event(raw)

    # Then
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.INVALID_STATE
    assert result.path == path


def test_outcome_variants_are_exhaustive() -> None:
    # Given
    raw = valid_event()
    raw["event_type"] = "command.failed"
    raw["outcome"] = {
        "status": "failed",
        "code": "execution_failed",
        "message": "Worker failed",
        "retryable": True,
        "details": {},
    }

    # When
    result = parse_event(raw)

    # Then
    assert isinstance(result, EventV1)
    match result.outcome:
        case Success() | Rejected() | Failed():
            pass
        case None:
            pytest.fail("terminal event must have an outcome")
        case unreachable:
            assert_never(unreachable)
