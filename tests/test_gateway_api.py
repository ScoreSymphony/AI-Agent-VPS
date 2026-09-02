from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import pytest

from scoresymphony_contracts import CommandReceipt, SubmissionStatus, parse_event, readonly_json
from scoresymphony_forge import (
    ForgeDispatchUncertainError,
    ForgeEventPage,
    ForgeEventProjectionError,
    ForgeTransportError,
)
from scoresymphony_gateway import GatewayApplication


ROOT = Path(__file__).resolve().parents[1]


def command_fixture() -> dict[str, object]:
    return json.loads((ROOT / "tests/fixtures/create-task-command.json").read_text())


def event_fixture() -> dict[str, object]:
    return json.loads((ROOT / "tests/fixtures/task-created-event.json").read_text())


@dataclass
class FakeAdapter:
    page: ForgeEventPage = field(default_factory=lambda: ForgeEventPage((), 0, 0))
    submit_error: Exception | None = None
    event_error: Exception | None = None
    commands: list[object] = field(default_factory=list)
    cursors: list[int | None] = field(default_factory=list)

    def submit(self, command) -> CommandReceipt:
        self.commands.append(command)
        if self.submit_error:
            raise self.submit_error
        return CommandReceipt(
            command.command_id,
            SubmissionStatus.ACCEPTED,
            "forge.accepted",
            "Forge accepted the mapped command",
            readonly_json({"http_status": 201}),
        )

    def get_event_page(self, after_sequence: int | None = None) -> ForgeEventPage:
        self.cursors.append(after_sequence)
        if self.event_error:
            raise self.event_error
        return self.page


def environ(method: str, path: str, body: bytes = b"", **extra: object) -> dict[str, object]:
    result: dict[str, object] = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "HTTP_AUTHORIZATION": "Bearer client-token",
        "wsgi.input": io.BytesIO(body),
    }
    result.update(extra)
    return result


def test_health_does_not_contact_forge() -> None:
    adapter = FakeAdapter(event_error=ForgeTransportError("offline"))
    response = GatewayApplication(adapter, "client-token").handle(environ("GET", "/healthz"))
    assert response.status == 200
    assert response.body == {"status": "ok"}
    assert adapter.cursors == []


def test_readiness_checks_durable_forge_recovery() -> None:
    adapter = FakeAdapter()
    assert GatewayApplication(adapter, "client-token").handle(environ("GET", "/readyz")).status == 200
    assert adapter.cursors == [0]

    adapter.event_error = ForgeTransportError("offline")
    response = GatewayApplication(adapter, "client-token").handle(environ("GET", "/readyz"))
    assert response.status == 503
    assert response.body["code"] == "forge.not_ready"


def test_command_ingress_validates_and_returns_non_terminal_receipt() -> None:
    adapter = FakeAdapter()
    body = json.dumps(command_fixture()).encode()

    response = GatewayApplication(adapter, "client-token").handle(environ("POST", "/v1/commands", body))

    assert response.status == 202
    assert response.body["status"] == "accepted"
    assert response.body["code"] == "forge.accepted"
    assert len(adapter.commands) == 1


@pytest.mark.parametrize("authorization", ["", "Bearer wrong", "Basic client-token"])
def test_protected_routes_require_exact_bearer_token(authorization: str) -> None:
    request = environ(
        "GET",
        "/v1/events",
        HTTP_AUTHORIZATION=authorization,
    )
    response = GatewayApplication(FakeAdapter(), "client-token").handle(request)
    assert response.status == 401
    assert response.body["code"] == "auth.unauthorized"


def test_invalid_command_is_not_dispatched() -> None:
    adapter = FakeAdapter()
    body = json.dumps({"schema_version": 99}).encode()

    response = GatewayApplication(adapter, "client-token").handle(environ("POST", "/v1/commands", body))

    assert response.status == 400
    assert response.body["code"] == "missing_required_field"
    assert adapter.commands == []


@pytest.mark.parametrize(
    ("body", "content_type", "expected_code"),
    [
        (b"{", "application/json", "request.invalid_json"),
        (b"{}", "text/plain", "request.content_type"),
    ],
)
def test_rejects_invalid_request_envelope(body: bytes, content_type: str, expected_code: str) -> None:
    response = GatewayApplication(FakeAdapter(), "client-token").handle(
        environ("POST", "/v1/commands", body, CONTENT_TYPE=content_type)
    )
    assert response.status == 400
    assert response.body["code"] == expected_code


def test_rejects_oversized_body_before_reading_it() -> None:
    response = GatewayApplication(FakeAdapter(), "client-token", max_body_bytes=3).handle(
        environ("POST", "/v1/commands", b"1234")
    )
    assert response.status == 413


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (ForgeDispatchUncertainError(503), 503, "forge.dispatch_uncertain"),
        (ForgeTransportError("offline"), 502, "forge.transport_error"),
    ],
)
def test_command_transport_failures_do_not_leak_details(error: Exception, status: int, code: str) -> None:
    body = json.dumps(command_fixture()).encode()
    response = GatewayApplication(FakeAdapter(submit_error=error), "client-token").handle(
        environ("POST", "/v1/commands", body)
    )
    assert response.status == status
    assert response.body["code"] == code
    assert "offline" not in response.body["message"]


def test_event_recovery_returns_v1_events_and_page_cursor() -> None:
    event = parse_event(event_fixture())
    assert not hasattr(event, "path")
    adapter = FakeAdapter(page=ForgeEventPage((event,), 7, 2))

    response = GatewayApplication(adapter, "client-token").handle(
        environ("GET", "/v1/events", QUERY_STRING="after_sequence=4")
    )

    assert response.status == 200
    assert adapter.cursors == [4]
    assert response.body["next_after_sequence"] == 7
    assert response.body["skipped_event_count"] == 2
    assert response.body["events"][0]["event_type"] == "task.created"


@pytest.mark.parametrize("query", ["after_sequence=-1", "after_sequence=x", "limit=10"])
def test_event_recovery_rejects_invalid_query(query: str) -> None:
    response = GatewayApplication(FakeAdapter(), "client-token").handle(
        environ("GET", "/v1/events", QUERY_STRING=query)
    )
    assert response.status == 400


def test_event_projection_failure_is_not_reported_as_empty_history() -> None:
    adapter = FakeAdapter(event_error=ForgeEventProjectionError("bad payload"))
    response = GatewayApplication(adapter, "client-token").handle(environ("GET", "/v1/events"))
    assert response.status == 502
    assert response.body["code"] == "events.invalid_upstream"


def test_wsgi_response_has_json_and_no_store_headers() -> None:
    observed: dict[str, object] = {}

    def start_response(status, headers):
        observed["status"] = status
        observed["headers"] = dict(headers)

    payload = b"".join(
        GatewayApplication(FakeAdapter(), "client-token")(
            environ("GET", "/healthz"), start_response
        )
    )
    assert observed["status"] == "200 OK"
    assert observed["headers"]["Cache-Control"] == "no-store"
    assert json.loads(payload) == {"status": "ok"}
