from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from uuid import UUID

import pytest

from scoresymphony_contracts import (
    CommandV1,
    IntegrationContractPort,
    SubmissionStatus,
    parse_command,
)
from scoresymphony_hermes import (
    GatewayClientError,
    GatewayHttpResponse,
    HermesGatewayAdapter,
    UrllibGatewayHttpTransport,
)


ROOT = Path(__file__).resolve().parents[1]


def fixture(name: str) -> dict[str, object]:
    return json.loads((ROOT / "tests" / "fixtures" / name).read_text())


def command() -> CommandV1:
    parsed = parse_command(fixture("create-task-command.json"))
    assert isinstance(parsed, CommandV1)
    return parsed


@dataclass
class FakeTransport:
    responses: list[GatewayHttpResponse]
    calls: list[tuple[str, str, object]] = field(default_factory=list)

    def request(self, method: str, path: str, *, json_body=None) -> GatewayHttpResponse:
        self.calls.append((method, path, json_body))
        return self.responses.pop(0)


def receipt_response(command_id: UUID | None = None) -> GatewayHttpResponse:
    return GatewayHttpResponse(
        202,
        {
            "command_id": str(command_id or command().command_id),
            "status": "accepted",
            "code": "forge.accepted",
            "message": "Forge accepted the mapped command",
            "details": {"http_status": 201},
        },
    )


def test_submits_frozen_v1_command_as_wire_json_and_parses_receipt() -> None:
    transport = FakeTransport([receipt_response()])
    adapter = HermesGatewayAdapter(transport)

    receipt = adapter.submit(command())

    assert isinstance(adapter, IntegrationContractPort)
    assert receipt.status is SubmissionStatus.ACCEPTED
    assert receipt.details["http_status"] == 201
    method, path, body = transport.calls[0]
    assert (method, path) == ("POST", "/v1/commands")
    assert body["command"] == "create_task"
    assert body["payload"]["title"] == command().payload["title"]


def test_rejects_receipt_for_a_different_command() -> None:
    wrong = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
    with pytest.raises(GatewayClientError, match="does not match"):
        HermesGatewayAdapter(FakeTransport([receipt_response(wrong)])).submit(command())


@pytest.mark.parametrize(
    "response",
    [
        GatewayHttpResponse(401, {"code": "auth.unauthorized"}),
        GatewayHttpResponse(202, None),
        GatewayHttpResponse(202, {"command_id": "bad"}),
    ],
)
def test_rejects_untrustworthy_command_responses(response: GatewayHttpResponse) -> None:
    with pytest.raises(GatewayClientError):
        HermesGatewayAdapter(FakeTransport([response])).submit(command())


def recovery_response(
    events: list[dict[str, object]],
    *,
    cursor: int,
    skipped: int = 0,
) -> GatewayHttpResponse:
    return GatewayHttpResponse(
        200,
        {
            "next_after_sequence": cursor,
            "skipped_event_count": skipped,
            "events": events,
        },
    )


def test_reads_validated_recovery_page_without_owning_cursor_state() -> None:
    event = fixture("task-created-event.json")
    event["sequence"] = 5
    transport = FakeTransport([recovery_response([event], cursor=7, skipped=2)])

    page = HermesGatewayAdapter(transport).get_event_page(4)

    assert transport.calls == [("GET", "/v1/events?after_sequence=4", None)]
    assert [item.sequence for item in page.events] == [5]
    assert page.next_after_sequence == 7
    assert page.skipped_event_count == 2


def test_internal_only_tail_can_advance_cursor_with_no_v1_events() -> None:
    page = HermesGatewayAdapter(
        FakeTransport([recovery_response([], cursor=9, skipped=3)])
    ).get_event_page(6)
    assert page.events == ()
    assert page.next_after_sequence == 9


@pytest.mark.parametrize(
    "response",
    [
        recovery_response([], cursor=3),
        recovery_response([], cursor=5, skipped=-1),
        recovery_response([{"schema_version": 1}], cursor=5),
    ],
)
def test_rejects_invalid_recovery_contract(response: GatewayHttpResponse) -> None:
    with pytest.raises(GatewayClientError):
        HermesGatewayAdapter(FakeTransport([response])).get_event_page(4)


def test_rejects_event_ordering_and_sequence_beyond_cursor() -> None:
    first = fixture("task-created-event.json")
    first["sequence"] = 6
    second = fixture("task-created-event.json")
    second["event_id"] = "fd6dde8c-7414-48f9-b1c0-7c40f42a4e45"
    second["sequence"] = 5
    with pytest.raises(GatewayClientError, match="strictly ordered"):
        HermesGatewayAdapter(
            FakeTransport([recovery_response([first, second], cursor=7)])
        ).get_event_page(4)

    with pytest.raises(GatewayClientError, match="exceeds"):
        HermesGatewayAdapter(
            FakeTransport([recovery_response([first], cursor=5)])
        ).get_event_page(4)


class FakeUrlResponse:
    status = 200

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def test_concrete_transport_sends_gateway_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    observed = {}

    def fake_urlopen(request, timeout):
        observed["request"] = request
        observed["timeout"] = timeout
        return FakeUrlResponse(b'{"next_after_sequence":0,"skipped_event_count":0,"events":[]}')

    monkeypatch.setattr("scoresymphony_hermes.client.urlopen", fake_urlopen)
    transport = UrllibGatewayHttpTransport("http://gateway:8080", "client-secret", timeout_seconds=3)

    response = transport.request("GET", "/v1/events?after_sequence=0")

    request = observed["request"]
    assert request.full_url == "http://gateway:8080/v1/events?after_sequence=0"
    assert request.get_header("Authorization") == "Bearer client-secret"
    assert observed["timeout"] == 3
    assert response.status == 200


def test_concrete_transport_preserves_http_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        raise HTTPError(
            "http://gateway/v1/events",
            401,
            "unauthorized",
            {},
            io.BytesIO(b'{"code":"auth.unauthorized"}'),
        )

    monkeypatch.setattr("scoresymphony_hermes.client.urlopen", fail)
    response = UrllibGatewayHttpTransport("http://gateway", "secret").request(
        "GET", "/v1/events"
    )
    assert response == GatewayHttpResponse(401, {"code": "auth.unauthorized"})


def test_concrete_transport_hides_token_on_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr("scoresymphony_hermes.client.urlopen", fail)
    with pytest.raises(GatewayClientError) as error:
        UrllibGatewayHttpTransport("http://gateway", "client-secret").request("GET", "/healthz")
    assert "client-secret" not in str(error.value)
