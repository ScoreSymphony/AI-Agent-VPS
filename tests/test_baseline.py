from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from scoresymphony_control.component_registry import list_components, load_registry


ROOT = Path(__file__).resolve().parents[1]


def load_yaml(name: str):
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def validate(instance_path: str, schema_path: str) -> None:
    instance = json.loads((ROOT / instance_path).read_text(encoding="utf-8"))
    schema = json.loads((ROOT / schema_path).read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def test_manifest_schemas() -> None:
    for manifest_name, schema_name in (
        ("COMPONENTS.yaml", "schemas/components.schema.json"),
        ("UPSTREAMS.yaml", "schemas/upstreams.schema.json"),
    ):
        schema = json.loads((ROOT / schema_name).read_text(encoding="utf-8"))
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(
            load_yaml(manifest_name)
        )


def test_bundled_components_are_mit_and_present() -> None:
    components = load_yaml("COMPONENTS.yaml")["components"]
    for component in components.values():
        if component["bundled"]:
            assert component["license"] == "MIT"
            assert (ROOT / component["path"]).is_dir()
            assert (ROOT / component["path"] / "LICENSE").is_file()


def test_core_pins_match_upstream_manifest() -> None:
    components = load_yaml("COMPONENTS.yaml")["components"]
    upstreams = load_yaml("UPSTREAMS.yaml")["upstreams"]
    for name, upstream in upstreams.items():
        assert components[name]["pin"] == upstream["pinned_commit"]
        assert components[name]["path"] == upstream["path"]
        assert components[name]["source"] == upstream["repository"]


def test_reviewed_upstream_exclusions_are_absent() -> None:
    upstreams = load_yaml("UPSTREAMS.yaml")["upstreams"]
    for upstream in upstreams.values():
        root = ROOT / upstream["path"]
        for excluded_path in upstream.get("excluded_paths", []):
            candidate = root / excluded_path
            if candidate.is_dir():
                assert not any(path.is_file() for path in candidate.rglob("*"))
            else:
                assert not candidate.exists()


def test_nested_bundled_license_files_are_mit() -> None:
    components = load_yaml("COMPONENTS.yaml")["components"]
    for component in components.values():
        if not component["bundled"]:
            continue
        for license_path in (ROOT / component["path"]).rglob("LICENSE*"):
            if license_path.is_file():
                text = license_path.read_text(encoding="utf-8", errors="replace")
                assert text.lstrip().startswith("MIT License"), license_path


def test_external_components_are_not_bundled() -> None:
    components = load_yaml("COMPONENTS.yaml")["components"]
    for component in components.values():
        if component["kind"] in {"managed_external", "remote_external"}:
            assert component["bundled"] is False
            assert "boundary" in component


def test_orchestrator_is_single_and_flat() -> None:
    config = load_yaml("config/orchestrator.yaml")
    assert config["orchestrator"]["engine"] == "hermes"
    assert config["orchestrator"]["sole_authority"] is True
    assert config["orchestrator"]["delegation"] == {
        "orchestrator_enabled": False,
        "max_spawn_depth": 1,
    }
    assert config["execution"]["engine"] == "forge"
    assert config["execution"]["strategic_planning"] is False


def test_contract_fixtures() -> None:
    validate(
        "tests/fixtures/create-task-command.json",
        "platform/contracts/v1/command.schema.json",
    )
    validate(
        "tests/fixtures/task-created-event.json",
        "platform/contracts/v1/event.schema.json",
    )


def test_component_registry_reports_expected_state() -> None:
    rows = list_components(load_registry(ROOT / "COMPONENTS.yaml"), ROOT)
    state = {row["name"]: row["status"] for row in rows}
    assert state == {
        "forge": "bundled",
        "hermes": "bundled",
        "qwen-code": "disabled",
    }


def test_compose_is_an_explicit_upstream_smoke_profile() -> None:
    compose = load_yaml("compose.yaml")
    assert set(compose["services"]) == {"forge-upstream", "hermes-upstream"}
    for service in compose["services"].values():
        assert service["profiles"] == ["upstream-smoke"]
