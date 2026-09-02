from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "compose.yaml"


class DeploymentValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DeploymentValidationError(message)


def load_compose() -> dict[str, Any]:
    data = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "compose.yaml must contain a mapping")
    return data


def validate_service_logging(service_name: str, service: dict[str, Any]) -> None:
    logging = service.get("logging")
    require(isinstance(logging, dict), f"{service_name} must configure Docker logging")
    require(logging.get("driver") == "json-file", f"{service_name} must use json-file logging")
    options = logging.get("options", {})
    require("max-size" in options, f"{service_name} logging must cap file size")
    require("max-file" in options, f"{service_name} logging must cap retained files")


def validate() -> None:
    compose = load_compose()
    services = compose.get("services")
    require(isinstance(services, dict), "compose.yaml must define services")

    forge = services.get("forge-upstream")
    hermes = services.get("hermes-upstream")
    require(isinstance(forge, dict), "forge-upstream service is required")
    require(isinstance(hermes, dict), "hermes-upstream service is required")

    require(forge.get("build", {}).get("context") == "./core/forge", "Forge build context must stay scoped to core/forge")
    require(forge.get("init") is True, "Forge must run with init enabled")
    ports = forge.get("ports", [])
    require(
        "${SCORESYMPHONY_BIND_HOST:-127.0.0.1}:${SCORESYMPHONY_FORGE_PORT:-8080}:8080" in ports,
        "Forge must bind to loopback by default and expose configurable port 8080",
    )
    require("forge-data:/data" in forge.get("volumes", []), "Forge data must use a persistent volume")

    healthcheck = forge.get("healthcheck")
    require(isinstance(healthcheck, dict), "Forge must define a liveness healthcheck")
    health_test = " ".join(str(part) for part in healthcheck.get("test", []))
    require("127.0.0.1/8080" in health_test, "Forge healthcheck must probe the local HTTP listener")
    forbidden_probe_terms = ("history", "recovery", "events")
    require(
        not any(term in health_test.lower() for term in forbidden_probe_terms),
        "Forge liveness must not depend on unfinished recovery/history APIs",
    )

    require(hermes.get("build", {}).get("context") == "./core/hermes", "Hermes build context must stay scoped to core/hermes")
    require(hermes.get("init") is True, "Hermes must run with init enabled")
    require(hermes.get("command") == ["gateway", "run"], "Hermes smoke service must run the gateway")

    for service_name, service in (("forge-upstream", forge), ("hermes-upstream", hermes)):
        validate_service_logging(service_name, service)
        labels = service.get("labels", {})
        require("io.scoresymphony.component" in labels, f"{service_name} must expose a component label")
        require("io.scoresymphony.role" in labels, f"{service_name} must expose a role label")


if __name__ == "__main__":
    try:
        validate()
    except DeploymentValidationError as exc:
        raise SystemExit(f"deployment validation failed: {exc}") from exc
    print("deployment validation passed")
