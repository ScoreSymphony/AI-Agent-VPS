from __future__ import annotations

from pathlib import Path

import pytest

from scoresymphony_gateway.cli import _read_secret


def test_read_secret_prefers_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret_file = tmp_path / "secret"
    secret_file.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_BEARER_TOKEN", "from-env")
    monkeypatch.setenv("FORGE_BEARER_TOKEN_FILE", str(secret_file))

    assert _read_secret("FORGE_BEARER_TOKEN") == "from-file"


def test_read_secret_uses_environment_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORGE_BEARER_TOKEN_FILE", raising=False)
    monkeypatch.setenv("FORGE_BEARER_TOKEN", "from-env")

    assert _read_secret("FORGE_BEARER_TOKEN") == "from-env"


def test_read_secret_fails_closed_when_configured_file_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FORGE_BEARER_TOKEN", "from-env")
    monkeypatch.setenv("FORGE_BEARER_TOKEN_FILE", str(tmp_path / "missing"))

    with pytest.raises(RuntimeError, match="FORGE_BEARER_TOKEN_FILE could not be read"):
        _read_secret("FORGE_BEARER_TOKEN")


def test_read_secret_rejects_empty_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret_file = tmp_path / "secret"
    secret_file.write_text("\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_BEARER_TOKEN_FILE", str(secret_file))

    with pytest.raises(RuntimeError, match="FORGE_BEARER_TOKEN_FILE must not be empty"):
        _read_secret("FORGE_BEARER_TOKEN")


def test_read_secret_rejects_missing_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORGE_BEARER_TOKEN_FILE", raising=False)
    monkeypatch.delenv("FORGE_BEARER_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="FORGE_BEARER_TOKEN or FORGE_BEARER_TOKEN_FILE is required"):
        _read_secret("FORGE_BEARER_TOKEN")
