from __future__ import annotations

from typing import Final
from uuid import UUID

from .models import ContractRejection, JsonObject, JsonValue, RejectionCode


TASK_COMMANDS: Final = frozenset(
    {
        "update_task",
        "start_task",
        "submit_task",
        "request_changes_task",
        "approve_task",
        "cancel_task",
    }
)
EXECUTION_COMMANDS: Final = frozenset({"retry_execution", "cancel_execution"})
TASK_EVENTS: Final = frozenset(
    {
        "task.created",
        "task.updated",
        "task.status_changed",
        "workspace.created",
        "review.started",
        "review.completed",
        "task.merged",
    }
)
EXECUTION_EVENTS: Final = frozenset(
    {
        "execution.started",
        "execution.completed",
        "execution.failed",
        "execution.cancelled",
        "execution.retry_scheduled",
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
    execution_id = message.get("execution_id")
    if not _identifier_is_well_formed(task_id) or not _identifier_is_well_formed(execution_id):
        return None
    if command == "create_task":
        if task_id is not None:
            return _invalid_state("create_task cannot target an existing task", "task_id")
        if execution_id is not None:
            return _invalid_state(
                "create_task cannot target an existing execution", "execution_id"
            )
    if command in TASK_COMMANDS:
        if task_id is None:
            return _invalid_state(f"{command} requires task_id", "task_id")
        if execution_id is not None:
            return _invalid_state(f"{command} cannot target an execution", "execution_id")
    if command in EXECUTION_COMMANDS:
        if task_id is None:
            return _invalid_state(f"{command} requires task_id", "task_id")
        if execution_id is None:
            return _invalid_state(f"{command} requires execution_id", "execution_id")
    return None


def _event_identifier_rejection(message: JsonObject) -> ContractRejection | None:
    event_type = message.get("event_type")
    if not isinstance(event_type, str):
        return None
    task_id = message.get("task_id")
    execution_id = message.get("execution_id")
    causation_id = message.get("causation_id")
    if (
        not _identifier_is_well_formed(task_id)
        or not _identifier_is_well_formed(execution_id)
        or not _identifier_is_well_formed(causation_id)
    ):
        return None
    if event_type in TASK_EVENTS:
        if task_id is None:
            return _invalid_state(f"{event_type} requires task_id", "task_id")
        if execution_id is not None:
            return _invalid_state(f"{event_type} cannot target an execution", "execution_id")
    if event_type in EXECUTION_EVENTS:
        if task_id is None:
            return _invalid_state(f"{event_type} requires task_id", "task_id")
        if execution_id is None:
            return _invalid_state(f"{event_type} requires execution_id", "execution_id")
    if event_type in GLOBAL_EVENTS:
        if task_id is not None:
            return _invalid_state(f"{event_type} cannot target a task", "task_id")
        if execution_id is not None:
            return _invalid_state(f"{event_type} cannot target an execution", "execution_id")
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
        and event_type in TASK_EVENTS | EXECUTION_EVENTS | GLOBAL_EVENTS
        and outcome is not None
    ):
        return _invalid_state(f"{event_type} cannot contain an outcome", "outcome")
    return None
