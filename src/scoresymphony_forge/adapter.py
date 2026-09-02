from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from scoresymphony_contracts.models import (
    CommandKind,
    CommandReceipt,
    CommandV1,
    JsonObject,
    JsonValue,
    SubmissionStatus,
    readonly_json,
)

from .transport import ForgeDispatchUncertainError, ForgeHttpResponse, ForgeHttpTransport


class ForgeAdapterMappingError(ValueError):
    """Raised when a typed command violates adapter mapping invariants."""


@dataclass(frozen=True, slots=True)
class ForgeRequest:
    method: str
    path: str
    json_body: JsonObject | None = None


class ForgeCommandAdapter:
    """Maps ScoreSymphony V1 commands to verified public Forge HTTP operations.

    The adapter owns no Forge lifecycle state. A successful HTTP submission is
    only an accepted ingress receipt; terminal truth still arrives through
    durable/live command and lifecycle events.
    """

    def __init__(self, transport: ForgeHttpTransport) -> None:
        self._transport = transport

    def submit(self, command: CommandV1) -> CommandReceipt:
        request = self.map_command(command)
        response = self._transport.request(
            request.method,
            request.path,
            json_body=request.json_body,
        )
        return self._receipt(command, response)

    def map_command(self, command: CommandV1) -> ForgeRequest:
        payload = command.payload

        match command.command:
            case CommandKind.CREATE_TASK:
                project_id = self._required_string(payload, "project_id")
                body: JsonObject = {
                    "title": self._required_string(payload, "title"),
                    "description": self._optional_json(payload, "description"),
                }
                return ForgeRequest(
                    "POST", f"/api/v1/projects/{project_id}/tasks", body
                )

            case CommandKind.UPDATE_TASK:
                task_id = self._required_id(command.task_id, "task_id")
                body = {"version": self._required_int(payload, "version")}
                for key in ("title", "description", "priority"):
                    if key in payload:
                        body[key] = self._json_value(payload[key])
                return ForgeRequest("PATCH", f"/api/v1/tasks/{task_id}", body)

            case (
                CommandKind.START_TASK
                | CommandKind.SUBMIT_TASK
                | CommandKind.REQUEST_CHANGES_TASK
                | CommandKind.APPROVE_TASK
                | CommandKind.CANCEL_TASK
            ):
                task_id = self._required_id(command.task_id, "task_id")
                action = {
                    CommandKind.START_TASK: "start",
                    CommandKind.SUBMIT_TASK: "submit",
                    CommandKind.REQUEST_CHANGES_TASK: "request-changes",
                    CommandKind.APPROVE_TASK: "approve",
                    CommandKind.CANCEL_TASK: "cancel",
                }[command.command]
                body = {"version": self._required_int(payload, "version")}
                if "reason" in payload:
                    body["reason"] = self._json_value(payload["reason"])
                return ForgeRequest("POST", f"/api/v1/tasks/{task_id}/{action}", body)

            case CommandKind.RETRY_EXECUTION:
                execution_id = self._required_id(command.execution_id, "execution_id")
                self._required_id(command.task_id, "task_id")
                return ForgeRequest(
                    "POST", f"/api/v1/executions/{execution_id}/re-execute"
                )

            case CommandKind.CANCEL_EXECUTION:
                execution_id = self._required_id(command.execution_id, "execution_id")
                self._required_id(command.task_id, "task_id")
                return ForgeRequest(
                    "POST", f"/api/v1/executions/{execution_id}/cancel"
                )

        raise ForgeAdapterMappingError(f"unsupported command: {command.command!r}")

    def _receipt(self, command: CommandV1, response: ForgeHttpResponse) -> CommandReceipt:
        if 200 <= response.status < 300:
            details: JsonObject = {"http_status": response.status}
            if response.body is not None:
                details["forge_response"] = response.body
            return CommandReceipt(
                command_id=command.command_id,
                status=SubmissionStatus.ACCEPTED,
                code="forge.accepted",
                message="Forge accepted the mapped command",
                details=readonly_json(details),
            )

        if 400 <= response.status < 500:
            code = self._response_text(response.body, "code") or "forge.rejected"
            message = (
                self._response_text(response.body, "message")
                or f"Forge rejected the command with HTTP {response.status}"
            )
            details = {"http_status": response.status}
            if response.body is not None:
                details["forge_response"] = response.body
            return CommandReceipt(
                command_id=command.command_id,
                status=SubmissionStatus.REJECTED,
                code=code,
                message=message,
                details=readonly_json(details),
            )

        raise ForgeDispatchUncertainError(response.status, response.body)

    @staticmethod
    def _response_text(body: JsonObject | None, key: str) -> str | None:
        if body is None:
            return None
        value = body.get(key)
        return value if isinstance(value, str) else None

    @staticmethod
    def _required_id(value: object, name: str) -> str:
        if value is None:
            raise ForgeAdapterMappingError(f"{name} is required")
        return str(value)

    @staticmethod
    def _required_string(payload: Mapping[str, object], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ForgeAdapterMappingError(f"payload.{key} must be a non-empty string")
        return value

    @staticmethod
    def _required_int(payload: Mapping[str, object], key: str) -> int:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ForgeAdapterMappingError(f"payload.{key} must be an integer")
        return value

    @classmethod
    def _optional_json(cls, payload: Mapping[str, object], key: str) -> JsonValue:
        if key not in payload:
            return None
        return cls._json_value(payload[key])

    @classmethod
    def _json_value(cls, value: object) -> JsonValue:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, tuple):
            return [cls._json_value(item) for item in value]
        if isinstance(value, Mapping):
            return {str(key): cls._json_value(item) for key, item in value.items()}
        raise ForgeAdapterMappingError(f"payload contains unsupported value: {value!r}")
