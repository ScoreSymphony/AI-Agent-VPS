from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from scoresymphony_contracts import CommandReceipt, SubmissionStatus, parse_event, readonly_json
from scoresymphony_hermes.client import HermesRecoveryPage
from scoresymphony_hermes.cli import main


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class FakeAdapter:
    transport: object

    def submit(self, command):
        return CommandReceipt(
            command.command_id,
            SubmissionStatus.ACCEPTED,
            "forge.accepted",
            "accepted",
            readonly_json({}),
        )

    def get_event_page(self, after_sequence):
        raw = json.loads((ROOT / "tests/fixtures/task-created-event.json").read_text())
        raw["sequence"] = after_sequence + 1
        event = parse_event(raw)
        assert not hasattr(event, "path")
        return HermesRecoveryPage((event,), after_sequence + 1, 0)


@pytest.fixture
def fake_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCORESYMPHONY_GATEWAY_BEARER_TOKEN", "test-token")
    monkeypatch.setattr("scoresymphony_hermes.cli.UrllibGatewayHttpTransport", lambda *a, **k: object())
    monkeypatch.setattr("scoresymphony_hermes.cli.HermesGatewayAdapter", FakeAdapter)


def test_cli_requires_gateway_credential(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.delenv("SCORESYMPHONY_GATEWAY_BEARER_TOKEN", raising=False)
    assert main(["events"]) == 2
    assert json.loads(capsys.readouterr().err)["code"] == "configuration.gateway_token_missing"


def test_cli_submits_valid_stdin_command(fake_runtime, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    command = (ROOT / "tests/fixtures/create-task-command.json").read_text()
    monkeypatch.setattr("sys.stdin", io.StringIO(command))
    assert main(["submit", "-"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["status"] == "accepted"
    assert body["code"] == "forge.accepted"


def test_cli_rejects_invalid_command_before_gateway(fake_runtime, tmp_path: Path, capsys) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version":99}', encoding="utf-8")
    assert main(["submit", str(path)]) == 2
    body = json.loads(capsys.readouterr().err)
    assert body["code"] == "missing_required_field"


def test_cli_reads_recovery_page(fake_runtime, capsys) -> None:
    assert main(["events", "--after-sequence", "8"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["next_after_sequence"] == 9
    assert body["events"][0]["sequence"] == 9
