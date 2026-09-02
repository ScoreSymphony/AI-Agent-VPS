from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scan_secrets.py"
SPEC = importlib.util.spec_from_file_location("scan_secrets", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
scan_secrets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan_secrets)


def test_detects_private_key_header() -> None:
    findings = scan_secrets.scan_text("-----BEGIN PRIVATE KEY-----\nredacted\n")
    assert "private key" in findings


def test_detects_github_token_shape() -> None:
    findings = scan_secrets.scan_text("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd")
    assert "GitHub token" in findings


def test_placeholder_text_is_not_flagged() -> None:
    assert scan_secrets.scan_text("OPENAI_API_KEY=dummy\nTOKEN=changeme\n") == []


def test_local_env_variants_are_sensitive() -> None:
    assert scan_secrets.sensitive_path_reason(scan_secrets.ROOT / ".env.local") == "tracked environment file"
    assert scan_secrets.sensitive_path_reason(scan_secrets.ROOT / ".env.example") is None
