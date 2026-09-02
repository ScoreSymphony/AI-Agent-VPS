from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

import pytest

from scoresymphony_contracts.models import (
    Actor,
    ActorType,
    CommandKind,
    CommandV1,
    Idempotency,
    SubmissionStatus,
    readonly_json,
)
from scoresymphony_forge import (
    ForgeCommandAdapter,
    ForgeDispatchUncertainError,
    ForgeHttpResponse,
)


COMMAND_ID = UUID("00000000-0000-4000-8000-000000000001")
TASK_ID = UUID("00000000-0000-4000-8000-000000000002")
EXECUTION_ID = UUID("00000000-0000-4000-8000-000000000003")
CORRELATION_ID = UUID("00000000-0000-4000-8000-000000000004")
PROJECT_ID = "00000000-0000-4000-8000-000000000005"


@dataclass
class FakeTransport:
    response: ForgeHttpResponse = field(
        default_factory=lambda: ForgeHttpResponse(200, {"ok": True})
    )
    calls: list[tuple[str, str, dict[str, object] | None]] = field(default_factory=list)

    def request(self, method: str, path: str, *, json_body=None) -> ForgeHttpResponse:
        self.calls.append((method, path, json_body))
        return self.response


def command(
    kind: CommandKind,
    payload: dict[str, object],
    *,
    task_id: UUID | None = None,
    execution_id: UUID | None = None,
) -> CommandV1:
    return CommandV1(
        command_id=COMMAND_ID,
        command=kind,
        actor=Actor(type=ActorType.HERMES, id="hermes-main"),
        task_id=task_id,
        execution_id=execution_id,
        correlation_id=CORRELATION_ID,
        issued_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        idempotency=Idempotency(
            key="command-1", scope="command", replay_policy="return_previous"
        ),
        payload=readonly_json(payload),
    )


@pytest.mark.parametrize(
    ("cmd", "method", "path", "body"),
    [
        (
            command(
                CommandKind.CREATE_TASK,
                {"project_id": PROJECT_ID, "title": "Implement adapter", "description": "x"},
            ),
            "POST",
            f"/api/v1/projects/{PROJECT_ID}/tasks",
            {"title": "Implement adapter", "description": "x"},
        ),
        (
            command(
                CommandKind.UPDATE_TASK,
                {"version": 7, "title": "Updated", "priority": 3},
                task_id=TASK_ID,
            ),
            "PATCH",
            f"/api/v1/tasks/{TASK_ID}",
            {"version": 7, "title": "Updated", "priority": 3},
        ),
        (
            command(CommandKind.START_TASK, {"version": 2}, task_id=TASK_ID),
            "POST",
            f"/api/v1/tasks/{TASK_ID}/start",
            {"version": 2},
        ),
        (
            command(
                CommandKind.SUBMIT_TASK,
                {"version": 3, "reason": "ready"},
                task_id=TASK_ID,
            ),
            "POST",
            f"/api/v1/tasks/{TASK_ID}/submit",
            {"version": 3, "reason": "ready"},
        ),
        (
            command(
                CommandKind.REQUEST_CHANGES_TASK,
                {"version": 4, "reason": "fix tests"},
                task_id=TASK_ID,
            ),
            "POST",
            f"/api/v1/tasks/{TASK_ID}/request-changes",
            {"version": 4, "reason": "fix tests"},
        ),
        (
            command(CommandKind.APPROVE_TASK, {"version": 5}, task_id=TASK_ID),
            "POST",
            f"/api/v1/tasks/{TASK_ID}/approve",
            {"version": 5},
        ),
        (
            command(CommandKind.CANCEL_TASK, {"version": 6}, task_id=TASK_ID),
            "POST",
            f"/api/v1/tasks/{TASK_ID}/cancel",
            {"version": 6},
        ),
        (
            command(
                CommandKind.RETRY_EXECUTION,
                {},
                task_id=TASK_ID,
                execution_id=EXECUTION_ID,
            ),
            "POST",
            f"/api/v1/executions/{EXECUTION_ID}/re-execute",
            None,
        ),
        (
            command(
                CommandKind.CANCEL_EXECUTION,
                {},
                task_id=TASK_ID,
                execution_id=EXECUTION_ID,
            ),
            "POST",
            f"/api/v1/executions/{EXECUTION_ID}/cancel",
            None,
        ),
    ],
)
def test_maps_every_v1_command_to_verified_public_forge_operation(
    cmd: CommandV1,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    transport = FakeTransport()
    receipt = ForgeCommandAdapter(transport).submit(cmd)

    assert transport.calls == [(method, path, body)]
    assert receipt.command_id == COMMAND_ID
    assert receipt.status is SubmissionStatus.ACCEPTED
    assert receipt.code == "forge.accepted"
    assert receipt.details["http_status"] == 200


def test_forwards_expected_task_version_without_fetching_or_replacing_it() -> None:
    transport = FakeTransport()
    cmd = command(
        CommandKind.UPDATE_TASK,
        {"version": 91, "description": None},
        task_id=TASK_ID,
    )

    ForgeCommandAdapter(transport).submit(cmd)

    assert transport.calls[0][2] == {"version": 91, "description": None}


def test_forge_conflict_is_a_deterministic_rejected_receipt() -> None:
    transport = FakeTransport(
        ForgeHttpResponse(
            409,
            {"code": "task.version_conflict", "message": "expected version is stale"},
        )
    )
    cmd = command(CommandKind.START_TASK, {"version": 2}, task_id=TASK_ID)

    receipt = ForgeCommandAdapter(transport).submit(cmd)

    assert receipt.status is SubmissionStatus.REJECTED
    assert receipt.code == "task.version_conflict"
    assert receipt.message == "expected version is stale"
    assert receipt.details["http_status"] == 409


def test_server_failure_is_not_misreported_as_success_or_safe_rejection() -> None:
    transport = FakeTransport(ForgeHttpResponse(503, {"message": "unavailable"}))
    cmd = command(CommandKind.CANCEL_TASK, {"version": 2}, task_id=TASK_ID)

    with pytest.raises(ForgeDispatchUncertainError) as error:
        ForgeCommandAdapter(transport).submit(cmd)

    assert error.value.status == 503


def test_receipt_does_not_claim_terminal_command_success() -> None:
    transport = FakeTransport(ForgeHttpResponse(202, {"id": str(TASK_ID)}))
    cmd = command(CommandKind.START_TASK, {"version": 2}, task_id=TASK_ID)

    receipt = ForgeCommandAdapter(transport).submit(cmd)

    assert receipt.status is SubmissionStatus.ACCEPTED
    assert receipt.code != "command.succeeded"
    assert "terminal" not in receipt.message.lower()
