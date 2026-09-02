from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event

import pytest

from scoresymphony_security import (
    ApprovalRecord,
    ApprovalRequest,
    ApprovalRequirement,
    ApprovalStatus,
    AuthorizationRequest,
    Principal,
    PrincipalKind,
    ResourceRef,
    approval_satisfies,
)
from scoresymphony_workers import ShellCommand, ShellExecutionStatus, ShellWorker


def test_pre_cancelled_shell_command_never_spawns_process(tmp_path: Path) -> None:
    marker = tmp_path / "marker.txt"
    script = tmp_path / "write_marker.py"
    script.write_text(
        "from pathlib import Path\nPath('marker.txt').write_text('spawned', encoding='utf-8')\n",
        encoding="utf-8",
    )

    worker = ShellWorker(
        tmp_path,
        allowed_executables=(sys.executable,),
        allowed_write_paths=("marker.txt",),
    )
    cancel_event = Event()
    cancel_event.set()

    result = worker.execute(
        ShellCommand(
            argv=(sys.executable, str(script)),
            declared_write_paths=("marker.txt",),
        ),
        cancel_event=cancel_event,
    )

    assert result.status is ShellExecutionStatus.CANCELLED
    assert result.exit_code is None
    assert result.error_code == "cancelled"
    assert result.changed_paths == ()
    assert not marker.exists()


def test_approval_evaluation_rejects_naive_now() -> None:
    requested_at = datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)
    authorization = AuthorizationRequest(
        principal=Principal(
            principal_id="operator-1",
            kind=PrincipalKind.USER,
            roles=frozenset({"operator"}),
        ),
        action="task.start",
        resource=ResourceRef(resource_type="task", resource_id="task-1", scope="project-1"),
        operation_digest="sha256:test-operation",
    )
    approval_request = ApprovalRequest(
        approval_id="approval-1",
        authorization=authorization,
        policy_id="policy-1",
        requested_at=requested_at,
        expires_at=requested_at + timedelta(minutes=10),
    )
    record = ApprovalRecord(
        request=approval_request,
        status=ApprovalStatus.APPROVED,
        approver_id="reviewer-1",
        decided_at=requested_at + timedelta(minutes=1),
    )

    with pytest.raises(ValueError, match="now must be timezone-aware"):
        approval_satisfies(
            record,
            authorization,
            ApprovalRequirement(policy_ids=frozenset({"policy-1"})),
            now=datetime(2026, 9, 2, 4, 2),
        )
