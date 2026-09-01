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

from test_contract_rejections import COMMAND_ID, RUN_ID, valid_create_task, valid_event


def test_parse_command_when_valid_returns_frozen_typed_model() -> None:
    raw = valid_create_task()
    result = parse_command(raw)
    assert isinstance(result, CommandV1)
    assert result.command is CommandKind.CREATE_TASK
    assert result.command_id == UUID(COMMAND_ID)
    assert result.issued_at == datetime(2026, 9, 1, 16, tzinfo=UTC)
    with pytest.raises(AttributeError):
        result.command = CommandKind.CANCEL_RUN


def test_parse_command_when_payload_is_nested_returns_recursively_read_only_data() -> None:
    raw = valid_create_task()
    raw["command"] = "update_task"
    raw["task_id"] = "9a9a0d0d-3c62-4a4a-9ef7-80fb7b3d429c"
    raw["payload"] = {
        "settings": {
            "paths": ["tests/fixture.txt"],
            "metadata": {"owner": "forge"},
        }
    }
    result = parse_command(raw)
    assert isinstance(result, CommandV1)
    settings = result.payload["settings"]
    assert not isinstance(settings, dict)
    assert isinstance(settings["paths"], tuple)
    with pytest.raises(TypeError):
        settings["metadata"]["owner"] = "hermes"


def test_parse_event_when_success_outcome_returns_success_variant() -> None:
    raw = valid_event()
    raw["event_type"] = "command.succeeded"
    raw["run_id"] = RUN_ID
    raw["outcome"] = {
        "status": "success",
        "code": "command_completed",
        "message": "Command completed",
        "details": {"state": "completed"},
    }
    result = parse_event(raw)
    assert isinstance(result, EventV1)
    assert isinstance(result.outcome, Success)
    assert result.outcome.code == "command_completed"


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
        "details": {"current_state": "running"},
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


@pytest.mark.parametrize("read_operation", ["get_events", "get_resources"])
def test_parse_command_when_read_operation_is_sent_on_command_plane_rejects(
    read_operation: str,
) -> None:
    from scoresymphony_contracts import ContractRejection, RejectionCode

    raw = valid_create_task()
    raw["command"] = read_operation
    raw["payload"] = {}
    result = parse_command(raw)
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.SCHEMA_VIOLATION
    assert result.path == "command"


def test_parse_event_when_terminal_command_event_has_no_causation_rejects() -> None:
    from scoresymphony_contracts import ContractRejection, RejectionCode

    raw = valid_event()
    raw["event_type"] = "command.failed"
    raw["causation_id"] = None
    raw["outcome"] = {
        "status": "failed",
        "code": "execution_failed",
        "message": "Worker failed",
        "retryable": True,
        "details": {},
    }
    result = parse_event(raw)
    assert isinstance(result, ContractRejection)
    assert result.code is RejectionCode.INVALID_STATE
    assert result.path == "causation_id"
