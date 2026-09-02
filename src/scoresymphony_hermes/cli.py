from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from scoresymphony_contracts import (
    CommandReceipt,
    ContractRejection,
    EventV1,
    Failed,
    Rejected,
    Success,
    parse_command,
)

from .client import GatewayClientError, HermesGatewayAdapter, UrllibGatewayHttpTransport


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="scoresymphony-hermes",
        description="Hermes CLI boundary for the ScoreSymphony V1 gateway",
    )
    result.add_argument(
        "--gateway-url",
        default="http://127.0.0.1:8080",
        help="ScoreSymphony gateway base URL",
    )
    subcommands = result.add_subparsers(dest="operation", required=True)
    submit = subcommands.add_parser("submit", help="submit one V1 command JSON document")
    submit.add_argument("command_file", help="JSON path, or - to read standard input")
    events = subcommands.add_parser("events", help="read one durable V1 recovery page")
    events.add_argument("--after-sequence", type=int, default=0)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    token = os.environ.get("SCORESYMPHONY_GATEWAY_BEARER_TOKEN")
    if not token:
        return _fail("configuration.gateway_token_missing", "Gateway bearer token is required")
    timeout = float(os.environ.get("SCORESYMPHONY_GATEWAY_TIMEOUT_SECONDS", "10"))
    adapter = HermesGatewayAdapter(
        UrllibGatewayHttpTransport(args.gateway_url, token, timeout_seconds=timeout)
    )
    try:
        if args.operation == "submit":
            raw = _read_command(args.command_file)
            command = parse_command(raw)
            if isinstance(command, ContractRejection):
                return _fail(str(command.code), command.message, path=command.path)
            receipt = adapter.submit(command)
            _print(_receipt(receipt))
            return 0
        page = adapter.get_event_page(args.after_sequence)
        _print(
            {
                "next_after_sequence": page.next_after_sequence,
                "skipped_event_count": page.skipped_event_count,
                "events": [_event(event) for event in page.events],
            }
        )
        return 0
    except (GatewayClientError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return _fail("gateway.client_error", str(error))


def _read_command(path: str) -> object:
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def _print(value: object) -> None:
    print(json.dumps(value, separators=(",", ":"), sort_keys=True))


def _fail(code: str, message: str, *, path: str | None = None) -> int:
    body: dict[str, object] = {"code": code, "message": message}
    if path is not None:
        body["path"] = path
    print(json.dumps(body, separators=(",", ":"), sort_keys=True), file=sys.stderr)
    return 2


def _receipt(receipt: CommandReceipt) -> dict[str, object]:
    return {
        "command_id": str(receipt.command_id),
        "status": str(receipt.status),
        "code": receipt.code,
        "message": receipt.message,
        "details": _mutable(receipt.details),
    }


def _event(event: EventV1) -> dict[str, object]:
    outcome: dict[str, object] | None = None
    if event.outcome is not None:
        outcome = {
            "status": "success" if isinstance(event.outcome, Success) else "rejected" if isinstance(event.outcome, Rejected) else "failed",
            "code": event.outcome.code,
            "message": event.outcome.message,
            "details": _mutable(event.outcome.details),
        }
        if isinstance(event.outcome, (Rejected, Failed)):
            outcome["retryable"] = event.outcome.retryable
    return {
        "schema_version": event.schema_version,
        "event_id": str(event.event_id),
        "event_type": str(event.event_type),
        "sequence": event.sequence,
        "occurred_at": event.occurred_at.isoformat(),
        "actor": {"type": str(event.actor.type), "id": event.actor.id},
        "task_id": str(event.task_id) if event.task_id else None,
        "execution_id": str(event.execution_id) if event.execution_id else None,
        "correlation_id": str(event.correlation_id),
        "causation_id": str(event.causation_id) if event.causation_id else None,
        "data": _mutable(event.data),
        "outcome": outcome,
    }


def _mutable(value: object) -> object:
    if isinstance(value, dict) or hasattr(value, "items"):
        return {str(key): _mutable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_mutable(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
