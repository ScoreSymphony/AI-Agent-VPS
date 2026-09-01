from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from scoresymphony_contracts import (
    CommandKind,
    CommandV1,
    EventV1,
    Failed,
    IntegrationContractPort,
    Rejected,
    Success,
    parse_command,
    parse_event,
)

from test_contract_rejections import COMMAND_ID, RUN_ID, valid_create_task, valid_event


def test_parse_command_when_valid_returns_frozen_typed_model() -> None:
    # Given
    raw = valid_create_task()

    # When
    result = parse_command(raw)

    # Then
    assert isinstance(result, CommandV1)
    assert result.command is CommandKind.CREATE_TASK
    assert result.command_id == UUID(COMMAND_ID)
    assert result.issued_at == datetime(2026, 9, 1, 16, tzinfo=UTC)
    with pytest.raises(AttributeError):
        result.command = CommandKind.CANCEL_RUN


def test_parse_event_when_success_outcome_returns_success_variant() -> None:
    # Given
    raw = valid_event()
    raw["event_type"] = "command.succeeded"
    raw["run_id"] = RUN_ID
    raw["outcome"] = {
        "status": "success",
        "code": "command_completed",
        "message": "Command completed",
        "details": {"state": "completed"},
    }

    # When
    result = parse_event(raw)

    # Then
    assert isinstance(result, EventV1)
    assert isinstance(result.outcome, Success)
    assert result.outcome.code == "command_completed"


@pytest.mark.parametrize(
    ("status", "expected_type", "retryable"),
    [
        ("rejected", Rejected, False),
        ("failed", Failed, True),
    ],
)
def test_parse_event_when_non_success_outcome_preserves_structured_result(
    status: str,
    expected_type: type[Rejected] | type[Failed],
    retryable: bool,
) -> None:
    # Given
    raw = valid_event()
    raw["event_type"] = f"command.{status}"
    raw["outcome"] = {
        "status": status,
        "code": "state_conflict" if status == "rejected" else "execution_failed",
        "message": "Deterministic result",
        "retryable": retryable,
        "details": {"current_state": "running"},
    }

    # When
    result = parse_event(raw)

    # Then
    assert isinstance(result, EventV1)
    assert isinstance(result.outcome, expected_type)
    assert result.outcome.retryable is retryable


def test_contract_port_when_implemented_by_fake_accepts_typed_messages() -> None:
    # Given
    class FakePort:
        def submit(self, command: CommandV1) -> Success | Rejected | Failed:
            return Success(
                code="accepted",
                message=str(command.command_id),
                details={},
            )

        def get_events(self, after_sequence: int | None = None) -> tuple[EventV1, ...]:
            del after_sequence
            return ()

    # When
    port = FakePort()

    # Then
    assert isinstance(port, IntegrationContractPort)
