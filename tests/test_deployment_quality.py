from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


def load_compose(repo_root: Path) -> dict[str, Any]:
    return yaml.safe_load((repo_root / "compose.yaml").read_text(encoding="utf-8"))


def test_deployment_validator_passes(repo_root: Path) -> None:
    subprocess.run(
        [sys.executable, "scripts/validate_deployment.py"],
        cwd=repo_root,
        check=True,
    )


def test_forge_is_loopback_bound_persistent_and_reference_enabled(repo_root: Path) -> None:
    forge = load_compose(repo_root)["services"]["forge-upstream"]
    assert {"upstream-smoke", "reference"}.issubset(set(forge["profiles"]))
    assert "${SCORESYMPHONY_BIND_HOST:-127.0.0.1}:${SCORESYMPHONY_FORGE_PORT:-8080}:8080" in forge["ports"]
    assert forge["environment"]["FORGE_SERVER_BIND"] == "0.0.0.0:8080"
    assert "forge-data:/data" in forge["volumes"]
    assert forge["restart"] == "unless-stopped"
    assert forge["cpus"]
    assert forge["mem_limit"]
    assert forge["pids_limit"] > 0
    assert "no-new-privileges:true" in forge["security_opt"]


def test_forge_healthcheck_is_transport_liveness_only(repo_root: Path) -> None:
    forge = load_compose(repo_root)["services"]["forge-upstream"]
    probe = " ".join(str(part) for part in forge["healthcheck"]["test"]).lower()
    assert "127.0.0.1/8080" in probe
    assert all(term not in probe for term in ("history", "recovery", "events"))


def test_reference_gateway_is_private_dependency_aware_and_hardened(repo_root: Path) -> None:
    compose = load_compose(repo_root)
    gateway = compose["services"]["gateway"]
    assert "reference" in gateway["profiles"]
    assert gateway["build"] == {"context": ".", "dockerfile": "Dockerfile.gateway"}
    assert "${SCORESYMPHONY_BIND_HOST:-127.0.0.1}:${SCORESYMPHONY_GATEWAY_PORT:-8090}:8090" in gateway["ports"]
    assert gateway["environment"]["FORGE_BASE_URL"] == "http://forge-upstream:8080"
    assert gateway["environment"]["FORGE_BEARER_TOKEN_FILE"] == "/run/secrets/forge_bearer_token"
    assert gateway["environment"]["SCORESYMPHONY_GATEWAY_BEARER_TOKEN_FILE"] == "/run/secrets/gateway_bearer_token"
    assert {"forge_bearer_token", "gateway_bearer_token"}.issubset(set(gateway["secrets"]))
    assert compose["secrets"]["forge_bearer_token"]["file"] == "${SCORESYMPHONY_FORGE_TOKEN_FILE:-./.runtime/secrets/forge_bearer_token}"
    assert compose["secrets"]["gateway_bearer_token"]["file"] == "${SCORESYMPHONY_GATEWAY_TOKEN_FILE:-./.runtime/secrets/gateway_bearer_token}"
    assert gateway["depends_on"]["forge-upstream"]["condition"] == "service_healthy"
    probe = " ".join(str(part) for part in gateway["healthcheck"]["test"]).lower()
    assert "/readyz" in probe
    assert gateway["restart"] == "unless-stopped"
    assert gateway["read_only"] is True
    assert "ALL" in gateway["cap_drop"]
    assert "no-new-privileges:true" in gateway["security_opt"]
    assert gateway["tmpfs"]
    assert gateway["cpus"]
    assert gateway["mem_limit"]
    assert gateway["pids_limit"] > 0


def test_platform_services_have_bounded_container_logs(repo_root: Path) -> None:
    services = load_compose(repo_root)["services"]
    for service_name in ("forge-upstream", "gateway", "hermes-upstream"):
        logging = services[service_name]["logging"]
        assert logging["driver"] == "json-file"
        assert logging["options"]["max-size"]
        assert logging["options"]["max-file"]


def test_example_environment_keeps_reference_private_and_bounded(repo_root: Path) -> None:
    env_example = (repo_root / ".env.example").read_text(encoding="utf-8")
    assert "SCORESYMPHONY_BIND_HOST=127.0.0.1" in env_example
    assert "SCORESYMPHONY_FORGE_LOG_LEVEL=info" in env_example
    assert "SCORESYMPHONY_FORGE_CPUS=2.0" in env_example
    assert "SCORESYMPHONY_FORGE_MEMORY=2g" in env_example
    assert "SCORESYMPHONY_GATEWAY_CPUS=1.0" in env_example
    assert "SCORESYMPHONY_GATEWAY_MEMORY=512m" in env_example
    assert "SCORESYMPHONY_FORGE_TOKEN_FILE=.runtime/secrets/forge_bearer_token" in env_example
    assert "SCORESYMPHONY_GATEWAY_TOKEN_FILE=.runtime/secrets/gateway_bearer_token" in env_example
    assert "SCORESYMPHONY_LOG_MAX_SIZE=10m" in env_example
    assert "SCORESYMPHONY_LOG_MAX_FILES=3" in env_example


def test_reference_operational_assets_exist(repo_root: Path) -> None:
    helper = repo_root / "scripts" / "reference_deployment.py"
    runbook = repo_root / "docs" / "operations" / "REFERENCE_DEPLOYMENT.md"
    assert helper.is_file()
    assert runbook.is_file()
    helper_text = helper.read_text(encoding="utf-8")
    for operation in ("init-secrets", "preflight", "start", "stop", "status", "diagnose", "backup", "restore"):
        assert f'"{operation}"' in helper_text
    runbook_text = runbook.read_text(encoding="utf-8")
    for section in ("Backup", "Restore", "Upgrade procedure", "Rollback procedure", "Reverse proxy and TLS"):
        assert section in runbook_text
