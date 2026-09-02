from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "compose.yaml"
RUNBOOK_PATH = ROOT / "docs" / "operations" / "REFERENCE_DEPLOYMENT.md"
HELPER_PATH = ROOT / "scripts" / "reference_deployment.py"


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


def validate_resource_limits(service_name: str, service: dict[str, Any]) -> None:
    require(service.get("cpus"), f"{service_name} must define a CPU limit")
    require(service.get("mem_limit"), f"{service_name} must define a memory limit")
    pids_limit = service.get("pids_limit")
    require(isinstance(pids_limit, int) and pids_limit > 0, f"{service_name} must define a positive PID limit")


def validate_no_new_privileges(service_name: str, service: dict[str, Any]) -> None:
    security_opt = service.get("security_opt", [])
    require(
        "no-new-privileges:true" in security_opt,
        f"{service_name} must prevent privilege escalation",
    )


def validate() -> None:
    compose = load_compose()
    services = compose.get("services")
    require(isinstance(services, dict), "compose.yaml must define services")

    forge = services.get("forge-upstream")
    gateway = services.get("gateway")
    hermes = services.get("hermes-upstream")
    require(isinstance(forge, dict), "forge-upstream service is required")
    require(isinstance(gateway, dict), "gateway service is required")
    require(isinstance(hermes, dict), "hermes-upstream service is required")

    forge_profiles = set(forge.get("profiles", []))
    require(
        {"upstream-smoke", "reference"}.issubset(forge_profiles),
        "Forge must participate in smoke and reference profiles",
    )
    require(forge.get("build", {}).get("context") == "./core/forge", "Forge build context must stay scoped to core/forge")
    require(forge.get("init") is True, "Forge must run with init enabled")
    require(forge.get("restart") == "unless-stopped", "Forge must use the supported restart policy")
    ports = forge.get("ports", [])
    require(
        "${SCORESYMPHONY_BIND_HOST:-127.0.0.1}:${SCORESYMPHONY_FORGE_PORT:-8080}:8080" in ports,
        "Forge must bind to loopback by default and expose configurable port 8080",
    )
    forge_environment = forge.get("environment", {})
    require(
        forge_environment.get("FORGE_SERVER_BIND") == "0.0.0.0:8080",
        "Forge must listen on container port 8080",
    )
    require("forge-data:/data" in forge.get("volumes", []), "Forge data must use a persistent volume")

    healthcheck = forge.get("healthcheck")
    require(isinstance(healthcheck, dict), "Forge must define a liveness healthcheck")
    health_test = " ".join(str(part) for part in healthcheck.get("test", []))
    require("127.0.0.1/8080" in health_test, "Forge healthcheck must probe the local HTTP listener")
    forbidden_probe_terms = ("history", "recovery", "events")
    require(
        not any(term in health_test.lower() for term in forbidden_probe_terms),
        "Forge liveness must not depend on recovery/history APIs",
    )
    validate_resource_limits("forge-upstream", forge)
    validate_no_new_privileges("forge-upstream", forge)

    gateway_profiles = set(gateway.get("profiles", []))
    require("reference" in gateway_profiles, "Gateway must participate in the reference profile")
    gateway_build = gateway.get("build", {})
    require(gateway_build.get("context") == ".", "Gateway build context must be repository root")
    require(gateway_build.get("dockerfile") == "Dockerfile.gateway", "Gateway must use Dockerfile.gateway")
    require(gateway.get("init") is True, "Gateway must run with init enabled")
    require(gateway.get("restart") == "unless-stopped", "Gateway must use the supported restart policy")
    gateway_ports = gateway.get("ports", [])
    require(
        "${SCORESYMPHONY_BIND_HOST:-127.0.0.1}:${SCORESYMPHONY_GATEWAY_PORT:-8090}:8090" in gateway_ports,
        "Gateway must bind to loopback by default and expose configurable port 8090",
    )
    gateway_environment = gateway.get("environment", {})
    require(
        gateway_environment.get("FORGE_BASE_URL") == "http://forge-upstream:8080",
        "Gateway must address Forge over the private Compose network",
    )
    require(gateway_environment.get("SCORESYMPHONY_GATEWAY_HOST") == "0.0.0.0", "Gateway must listen on its container interface")
    require(gateway_environment.get("SCORESYMPHONY_GATEWAY_PORT") == "8090", "Gateway container port must be stable")
    require("FORGE_BEARER_TOKEN" in gateway_environment, "Gateway must receive the Forge credential through runtime configuration")
    require(
        "SCORESYMPHONY_GATEWAY_BEARER_TOKEN" in gateway_environment,
        "Gateway must receive its client credential through runtime configuration",
    )

    depends_on = gateway.get("depends_on", {}).get("forge-upstream", {})
    require(depends_on.get("condition") == "service_healthy", "Gateway must wait for healthy Forge")
    gateway_health = gateway.get("healthcheck")
    require(isinstance(gateway_health, dict), "Gateway must define a readiness-aware healthcheck")
    gateway_probe = " ".join(str(part) for part in gateway_health.get("test", [])).lower()
    require("/readyz" in gateway_probe, "Gateway healthcheck must use dependency-aware readiness")
    require(gateway.get("read_only") is True, "Gateway filesystem must be read-only")
    require("ALL" in gateway.get("cap_drop", []), "Gateway must drop all Linux capabilities")
    require(gateway.get("tmpfs"), "Gateway must use tmpfs for temporary writable space")
    validate_resource_limits("gateway", gateway)
    validate_no_new_privileges("gateway", gateway)

    require(hermes.get("build", {}).get("context") == "./core/hermes", "Hermes build context must stay scoped to core/hermes")
    require(hermes.get("init") is True, "Hermes must run with init enabled")
    require(hermes.get("command") == ["gateway", "run"], "Hermes smoke service must run the gateway")
    require(hermes.get("restart") == "unless-stopped", "Hermes smoke service must use the supported restart policy")
    validate_resource_limits("hermes-upstream", hermes)
    validate_no_new_privileges("hermes-upstream", hermes)

    for service_name, service in (
        ("forge-upstream", forge),
        ("gateway", gateway),
        ("hermes-upstream", hermes),
    ):
        validate_service_logging(service_name, service)
        labels = service.get("labels", {})
        require("io.scoresymphony.component" in labels, f"{service_name} must expose a component label")
        require("io.scoresymphony.role" in labels, f"{service_name} must expose a role label")

    require(RUNBOOK_PATH.is_file(), "reference deployment runbook is required")
    require(HELPER_PATH.is_file(), "reference deployment lifecycle helper is required")


if __name__ == "__main__":
    try:
        validate()
    except DeploymentValidationError as exc:
        raise SystemExit(f"deployment validation failed: {exc}") from exc
    print("deployment validation passed")
