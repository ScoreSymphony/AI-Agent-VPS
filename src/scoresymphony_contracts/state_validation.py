from __future__ import annotations

from typing import Final
from uuid import UUID

from .models import ContractRejection, JsonObject, JsonValue, RejectionCode


TASK_REQUIRED_COMMANDS: Final = frozenset(
    {
        "update_task",
        "start_worker",
        "create_worktree",
        "inspect_worktree",
        "run_tests",
        "request_review",
        "retry_run",
        "cancel_run",
        "merge_task",
    }
)
RUN_REQUIRED_COMMANDS: Final = frozenset(
    {"run_tests", "request_review", "retry_run", "cancel_run", "merge_task"}
)
TASK_EVENTS: Final = frozenset(
    {"task.created", "task.updated", "worktree.created", "worktree.inspected"}
)
RUN_EVENTS: Final = frozenset(
    {
        "run.started",
        "run.tests_completed",
        "run.cancelled",
        "run.retry_scheduled",
        "review.requested",
        "review.completed",
        "task.merged",
    }
)
GLOBAL_EVENTS: Final = frozenset({"events.snapshot", "resources.reported"})
TERMINAL_OUTCOMES: Final = {
    "command.succeeded": "success",
    "command.rejected": "rejected",
    "command.failed": "failed",
}


def _invalid_state(message: str, path: str) -> ContractRejection:
    return ContractRejection(RejectionCode.INVALID_STATE, message, path)


def _identifier_is_well_formed(value: JsonValue) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def command_state_rejection(message: JsonObject) -> ContractRejection | None:
    command = message.get("command")
    if not isinstance(command, str):
        return None
    task_id = message.get("task_id")
    run_id = message.get("run_id")
    if not _identifier_is_well_formed(task_id) or not _identifier_is_well_formed(run_id):
        return None
    if command == "create_task" and task_id is not None:
        return _invalid_state("create_task cannot target an existing task", "task_id")
    if command == "create_task" and run_id is not None:
        return _invalid_state("create_task cannot target an existing run", "run_id")
    if command in TASK_REQUIRED_COMMANDS and task_id is None:
        return _invalid_state(f"{command} requires task_id", "task_id")
    if command in RUN_REQUIRED_COMMANDS and run_id is None:
        return _invalid_state(f"{command} requires run_id", "run_id")
    if command in TASK_REQUIRED_COMMANDS - RUN_REQUIRED_COMMANDS and run_id is not None:
        return _invalid_state(f"{command} cannot target a run", "run_id")
    return None


def _event_identifier_rejection(message: JsonObject) -> ContractRejection | None:
    event_type = message.get("event_type")
    if not isinstance(event_type, str):
        return None
    task_id = message.get("task_id")
    run_id = message.get("run_id")
    causation_id = message.get("causation_id")
    if (
        not _identifier_is_well_formed(task_id)
        or not _identifier_is_well_formed(run_id)
        or not _identifier_is_well_formed(causation_id)
    ):
        return None
    if event_type in TASK_EVENTS:
        if task_id is None:
            return _invalid_state(f"{event_type} requires task_id", "task_id")
        if run_id is not None:
            return _invalid_state(f"{event_type} cannot target a run", "run_id")
    if event_type in RUN_EVENTS:
        if task_id is None:
            return _invalid_state(f"{event_type} requires task_id", "task_id")
        if run_id is None:
            return _invalid_state(f"{event_type} requires run_id", "run_id")
    if event_type in GLOBAL_EVENTS:
        if task_id is not None:
            return _invalid_state(f"{event_type} cannot target a task", "task_id")
        if run_id is not None:
            return _invalid_state(f"{event_type} cannot target a run", "run_id")
    if event_type in TERMINAL_OUTCOMES and causation_id is None:
        return _invalid_state(f"{event_type} requires causation_id", "causation_id")
    return None


def event_state_rejection(message: JsonObject) -> ContractRejection | None:
    identifier_rejection = _event_identifier_rejection(message)
    if identifier_rejection is not None:
        return identifier_rejection

    event_type = message.get("event_type")
    outcome = message.get("outcome")
    expected_status = TERMINAL_OUTCOMES.get(event_type) if isinstance(event_type, str) else None
    if expected_status is not None:
        if outcome is None:
            return _invalid_state(f"{event_type} requires an outcome", "outcome")
        if isinstance(outcome, dict):
            status = outcome.get("status")
            if isinstance(status, str) and status != expected_status:
                return _invalid_state(
                    f"{event_type} requires outcome status {expected_status}",
                    "outcome.status",
                )
        return None
    if (
        isinstance(event_type, str)
        and event_type in TASK_EVENTS | RUN_EVENTS | GLOBAL_EVENTS
        and outcome is not None
    ):
        return _invalid_state(f"{event_type} cannot contain an outcome", "outcome")
    return None
