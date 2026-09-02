from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from uuid import UUID

import pytest

from scoresymphony_contracts import EventType, IntegrationContractPort
from scoresymphony_forge import (
    ForgeEventAdapter,
    ForgeEventProjectionError,
    ForgeHttpResponse,
    ForgeIntegrationAdapter,
    ForgeTransportError,
    UrllibForgeHttpTransport,
)


EVENT_ID = "10000000-0000-4000-8000-000000000001"
TASK_ID = "10000000-0000-4000-8000-000000000002"
EXECUTION_ID = "10000000-0000-4000-8000-000000000003"
CORRELATION_ID = "10000000-0000-4000-8000-000000000004"


@dataclass
class FakeTransport:
    response: ForgeHttpResponse
    calls: list[tuple[str, str, object]] = field(default_factory=list)

    def request(self, method: str, path: str, *, json_body=None) -> ForgeHttpResponse:
        self.calls.append((method, path, json_body))
        return self.response


def raw_event(
    *,
    sequence: int = 1,
    event_type: str = "task.created",
    entity_id: str = TASK_ID,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "sequence": sequence,
        "id": EVENT_ID,
        "event_type": event_type,
        "entity_type": "task",
        "entity_id": entity_id,
        "actor_type": "system",
        "actor_id": None,
        "scope_type": "project",
        "scope_id": "10000000-0000-4000-8000-000000000005",
        "correlation_id": CORRELATION_ID,
        "causation_id": None,
        "causation_depth": 0,
        "dedupe_key": None,
        "payload_json": json.dumps(payload or {"state": "created"}),
        "created_at": "2026-09-02T08:00:00Z",
    }


def history(
    events: list[dict[str, object]],
    next_cursor: int,
    *,
    after_sequence: int = 0,
    limit: int = 100,
) -> ForgeHttpResponse:
    return ForgeHttpResponse(
        200,
        {
            "after_sequence": after_sequence,
            "limit": limit,
            "next_after_sequence": next_cursor,
            "events": events,
        },
    )


def test_projects_task_history_through_v1_contract() -> None:
    transport = FakeTransport(history([raw_event()], 1))

    page = ForgeEventAdapter(transport).get_event_page()

    assert transport.calls == [("GET", "/api/v1/events?after_sequence=0&limit=100", None)]
    assert page.next_after_sequence == 1
    assert page.skipped_event_count == 0
    assert len(page.events) == 1
    event = page.events[0]
    assert event.event_type is EventType.TASK_CREATED
    assert event.task_id == UUID(TASK_ID)
    assert event.execution_id is None
    assert event.actor.id == "forge-runtime"


def test_composite_adapter_implements_the_v1_integration_port() -> None:
    adapter = ForgeIntegrationAdapter(FakeTransport(history([], 0)))
    assert isinstance(adapter, IntegrationContractPort)
    assert adapter.get_events() == ()


def test_projects_execution_entity_and_payload_task_id() -> None:
    event = raw_event(
        event_type="execution.completed",
        entity_id=EXECUTION_ID,
        payload={"task_id": TASK_ID, "exit_code": 0},
    )

    projected = ForgeEventAdapter(FakeTransport(history([event], 1))).get_events()[0]

    assert projected.event_type is EventType.EXECUTION_COMPLETED
    assert projected.task_id == UUID(TASK_ID)
    assert projected.execution_id == UUID(EXECUTION_ID)
    assert projected.data["exit_code"] == 0


def test_skipped_internal_event_still_advances_durable_cursor() -> None:
    internal = raw_event(sequence=1, event_type="notification.created")
    supported = raw_event(sequence=2, event_type="task.updated")
    transport = FakeTransport(history([internal, supported], 2))

    page = ForgeEventAdapter(transport).get_event_page(after_sequence=0)

    assert page.next_after_sequence == 2
    assert page.skipped_event_count == 1
    assert [event.sequence for event in page.events] == [2]


@pytest.mark.parametrize(
    "response",
    [
        ForgeHttpResponse(200, None),
        ForgeHttpResponse(200, {"events": [], "next_after_sequence": "1"}),
        history([raw_event(sequence=2), raw_event(sequence=1)], 1),
        history([raw_event() | {"payload_json": "[1,2]"}], 1),
        history([raw_event() | {"id": "not-a-uuid"}], 1),
        ForgeHttpResponse(
            200,
            {
                "after_sequence": 9,
                "limit": 100,
                "next_after_sequence": 9,
                "events": [],
            },
        ),
    ],
)
def test_rejects_malformed_or_unordered_history(response: ForgeHttpResponse) -> None:
    with pytest.raises(ForgeEventProjectionError):
        ForgeEventAdapter(FakeTransport(response)).get_event_page()


def test_rejects_failed_history_read_without_claiming_empty_page() -> None:
    with pytest.raises(ForgeTransportError, match="HTTP 401"):
        ForgeEventAdapter(FakeTransport(ForgeHttpResponse(401, {"code": "unauthorized"}))).get_events()


class FakeUrlResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def test_concrete_transport_sends_bearer_and_json(monkeypatch: pytest.MonkeyPatch) -> None:
    observed = {}

    def fake_urlopen(request, timeout):
        observed["request"] = request
        observed["timeout"] = timeout
        return FakeUrlResponse(202, b'{"accepted":true}')

    monkeypatch.setattr("scoresymphony_forge.transport.urlopen", fake_urlopen)
    transport = UrllibForgeHttpTransport("http://forge:3000", "secret", timeout_seconds=4)

    response = transport.request("POST", "/api/v1/tasks/x", json_body={"version": 3})

    request = observed["request"]
    assert request.full_url == "http://forge:3000/api/v1/tasks/x"
    assert request.get_header("Authorization") == "Bearer secret"
    assert json.loads(request.data) == {"version": 3}
    assert observed["timeout"] == 4
    assert response == ForgeHttpResponse(202, {"accepted": True})


def test_concrete_transport_preserves_http_error_body(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        raise HTTPError(
            "http://forge/api/v1/tasks/x",
            409,
            "conflict",
            {},
            io.BytesIO(b'{"code":"task.version_conflict"}'),
        )

    monkeypatch.setattr("scoresymphony_forge.transport.urlopen", fail)
    response = UrllibForgeHttpTransport("http://forge", "secret").request(
        "POST", "/api/v1/tasks/x"
    )
    assert response.status == 409
    assert response.body == {"code": "task.version_conflict"}


def test_concrete_transport_wraps_connection_error_without_leaking_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr("scoresymphony_forge.transport.urlopen", fail)
    with pytest.raises(ForgeTransportError) as error:
        UrllibForgeHttpTransport("http://forge", "top-secret").request("GET", "/api/v1/events")
    assert "top-secret" not in str(error.value)


def test_concrete_transport_rejects_cross_origin_path() -> None:
    transport = UrllibForgeHttpTransport("http://forge", "secret")
    with pytest.raises(ForgeTransportError):
        transport.request("GET", "//attacker.invalid/path")
