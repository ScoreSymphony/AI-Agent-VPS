from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from scoresymphony_contracts import (
    CommandKind,
    CommandReceipt,
    CommandV1,
    EventV1,
    Failed,
    IntegrationContractPort,
    Rejected,
    SubmissionStatus,
    Success,
    parse_command,
    parse_event,
    readonly_json,
)
from test_contract_rejections import (
    COMMAND_ID,
    EXECUTION_ID,
    PROJECT_ID,
    TASK_ID,
    valid_create_task,
    valid_event,
)


def test_parse_command_when_valid_returns_frozen_typed_model() -> None:
    result = parse_command(valid_create_task())
    assert isinstance(result, CommandV1)
    assert result.command is CommandKind.CREATE_TASK
    assert result.command_id == UUID(COMMAND_ID)
    assert result.issued_at == datetime(2026, 9, 1, 16, tzinfo=UTC)
    with pytest.raises(AttributeError):
        result.command = CommandKind.CANCEL_TASK


def test_parse_command_when_payload_is_nested_returns_recursively_read_only_data() -> None:
    raw = valid_create_task()
    raw["payload"] = {
        "project_id": PROJECT_ID,
        "title": "Nested fixture",
        "description": None,
    }
    result = parse_command(raw)
    assert isinstance(result, CommandV1)
    with pytest.raises(TypeError):
        result.payload["project_id"] = "changed"


def test_parse_task_action_when_valid_preserves_expected_version() -> None:
    raw = valid_create_task()
    raw["command"] = "start_task"
    raw["task_id"] = TASK_ID
    raw["payload"] = {"version": 4}
    result = parse_command(raw)
    assert isinstance(result, CommandV1)
    assert result.command is CommandKind.START_TASK
    assert result.payload["version"] == 4


def test_parse_execution_command_when_valid_uses_execution_identifier() -> None:
    raw = valid_create_task()
    raw["command"] = "retry_execution"
    raw["task_id"] = TASK_ID
    raw["execution_id"] = EXECUTION_ID
    raw["payload"] = {}
    result = parse_command(raw)
    assert isinstance(result, CommandV1)
    assert result.command is CommandKind.RETRY_EXECUTION
    assert result.execution_id == UUID(EXECUTION_ID)


def test_parse_event_when_success_outcome_returns_success_variant() -> None:
    raw = valid_event()
    raw["event_type"] = "command.succeeded"
    raw["execution_id"] = EXECUTION_ID
    raw["outcome"] = {
        "status": "success",
        "code": "command_completed",
        "message": "Command completed",
        "details": {"state": "completed"},
    }
    result = parse_event(raw)
    assert isinstance(result, EventV1)
    assert isinstance(result.outcome, Success)


@pytest.mark.parametrize(
    ("status", "expected_type", "retryable"),
    [("rejected", Rejected, False), ("failed", Failed, True)],
)
def test_parse_event_when_non_success_outcome_preserves_structured_result(
    status: str,
    expected_type: type[Rejected] | type[Failed],
    retryable: bool,
) -> None:
    raw = valid_event()
    raw["event_type"] = f"command.{status}"
    raw["outcome"] = {
        "status": status,
        "code": "state_conflict" if status == "rejected" else "execution_failed",
        "message": "Deterministic result",
        "retryable": retryable,
        "details": {},
    }
    result = parse_event(raw)
    assert isinstance(result, EventV1)
    assert isinstance(result.outcome, expected_type)
    assert result.outcome.retryable is retryable


def test_contract_port_when_implemented_by_fake_separates_receipt_from_terminal_events() -> None:
    class FakePort:
        def submit(self, command: CommandV1) -> CommandReceipt:
            return CommandReceipt(
                command_id=command.command_id,
                status=SubmissionStatus.ACCEPTED,
                code="accepted",
                message="Queued for Forge execution",
                details=readonly_json({}),
            )

        def get_events(self, after_sequence: int | None = None) -> tuple[EventV1, ...]:
            del after_sequence
            return ()

    command = parse_command(valid_create_task())
    assert isinstance(command, CommandV1)
    port = FakePort()
    receipt = port.submit(command)
    assert isinstance(port, IntegrationContractPort)
    assert receipt.status is SubmissionStatus.ACCEPTED
    assert not isinstance(receipt, (Success, Rejected, Failed))
