from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from scoresymphony_contracts import CommandV1, EventType, parse_command
from scoresymphony_forge import ForgeHttpResponse, ForgeIntegrationAdapter
from scoresymphony_gateway import GatewayApplication
from scoresymphony_hermes import GatewayHttpResponse, HermesGatewayAdapter


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class PublicForgeFixture:
    calls: list[tuple[str, str, object]] = field(default_factory=list)

    def request(self, method: str, path: str, *, json_body=None) -> ForgeHttpResponse:
        self.calls.append((method, path, json_body))
        if method == "POST":
            return ForgeHttpResponse(201, {"id": "9a9a0d0d-3c62-4a4a-9ef7-80fb7b3d429c"})
        return ForgeHttpResponse(
            200,
            {
                "after_sequence": 0,
                "limit": 100,
                "next_after_sequence": 1,
                "events": [
                    {
                        "sequence": 1,
                        "id": "fd6dde8c-7414-48f9-b1c0-7c40f42a4e44",
                        "event_type": "task.created",
                        "entity_type": "task",
                        "entity_id": "9a9a0d0d-3c62-4a4a-9ef7-80fb7b3d429c",
                        "actor_type": "system",
                        "actor_id": None,
                        "scope_type": "project",
                        "scope_id": "5fd2a333-547f-4db3-a221-7281f59c3abc",
                        "correlation_id": "159d4955-1584-4888-b7bd-314c02a515a3",
                        "causation_id": "6fd31d31-e8d9-4ac8-9f65-b7ae97976ac2",
                        "causation_depth": 1,
                        "dedupe_key": "fixture",
                        "payload_json": '{"state":"created"}',
                        "created_at": "2026-09-01T16:00:01Z",
                    }
                ],
            },
        )


class InProcessGatewayTransport:
    def __init__(self, app: GatewayApplication) -> None:
        self._app = app

    def request(self, method: str, path: str, *, json_body=None) -> GatewayHttpResponse:
        route, _, query = path.partition("?")
        raw = b"" if json_body is None else json.dumps(json_body).encode()
        response = self._app.handle(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": route,
                "QUERY_STRING": query,
                "CONTENT_TYPE": "application/json",
                "CONTENT_LENGTH": str(len(raw)),
                "HTTP_AUTHORIZATION": "Bearer gateway-client-secret",
                "wsgi.input": io.BytesIO(raw),
            }
        )
        return GatewayHttpResponse(response.status, response.body)


def test_hermes_command_and_recovery_cross_every_scoresymphony_boundary() -> None:
    forge = PublicForgeFixture()
    gateway = GatewayApplication(
        ForgeIntegrationAdapter(forge),
        "gateway-client-secret",
    )
    hermes = HermesGatewayAdapter(InProcessGatewayTransport(gateway))
    raw_command = json.loads((ROOT / "tests/fixtures/create-task-command.json").read_text())
    command = parse_command(raw_command)
    assert isinstance(command, CommandV1)

    receipt = hermes.submit(command)
    page = hermes.get_event_page(0)

    assert receipt.command_id == command.command_id
    assert forge.calls[0] == (
        "POST",
        f"/api/v1/projects/{command.payload['project_id']}/tasks",
        {
            "title": command.payload["title"],
            "description": None,
        },
    )
    assert forge.calls[1] == ("GET", "/api/v1/events?after_sequence=0&limit=100", None)
    assert page.next_after_sequence == 1
    assert page.events[0].event_type is EventType.TASK_CREATED
    assert page.events[0].correlation_id == command.correlation_id
