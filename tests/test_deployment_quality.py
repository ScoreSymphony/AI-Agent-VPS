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


def test_forge_is_loopback_bound_and_persistent_by_default(repo_root: Path) -> None:
    forge = load_compose(repo_root)["services"]["forge-upstream"]
    assert "${SCORESYMPHONY_BIND_HOST:-127.0.0.1}:${SCORESYMPHONY_FORGE_PORT:-8080}:8080" in forge["ports"]
    assert forge["environment"]["FORGE_SERVER_BIND"] == "0.0.0.0:8080"
    assert "forge-data:/data" in forge["volumes"]


def test_forge_healthcheck_is_transport_liveness_only(repo_root: Path) -> None:
    forge = load_compose(repo_root)["services"]["forge-upstream"]
    probe = " ".join(str(part) for part in forge["healthcheck"]["test"]).lower()
    assert "127.0.0.1/8080" in probe
    assert all(term not in probe for term in ("history", "recovery", "events"))


def test_platform_services_have_bounded_container_logs(repo_root: Path) -> None:
    services = load_compose(repo_root)["services"]
    for service_name in ("forge-upstream", "hermes-upstream"):
        logging = services[service_name]["logging"]
        assert logging["driver"] == "json-file"
        assert logging["options"]["max-size"]
        assert logging["options"]["max-file"]


def test_example_environment_keeps_forge_private_by_default(repo_root: Path) -> None:
    env_example = (repo_root / ".env.example").read_text(encoding="utf-8")
    assert "SCORESYMPHONY_BIND_HOST=127.0.0.1" in env_example
    assert "SCORESYMPHONY_FORGE_LOG_LEVEL=info" in env_example
    assert "SCORESYMPHONY_LOG_MAX_SIZE=10m" in env_example
    assert "SCORESYMPHONY_LOG_MAX_FILES=3" in env_example
