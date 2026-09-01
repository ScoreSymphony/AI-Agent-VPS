#!/usr/bin/env python3
"""Validate manifests, provenance, contracts, and architecture invariants."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]


def read_yaml(relative_path: str):
    return yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))


def read_json(relative_path: str):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def validate_schema(instance, schema_path: str) -> list[str]:
    validator = Draft202012Validator(
        read_json(schema_path), format_checker=FormatChecker()
    )
    return [error.message for error in sorted(validator.iter_errors(instance), key=str)]


def main() -> int:
    errors: list[str] = []
    components = read_yaml("COMPONENTS.yaml")
    upstreams = read_yaml("UPSTREAMS.yaml")

    for manifest, schema in (
        (components, "schemas/components.schema.json"),
        (upstreams, "schemas/upstreams.schema.json"),
    ):
        errors.extend(validate_schema(manifest, schema))

    for name, component in components.get("components", {}).items():
        if component.get("bundled"):
            path = ROOT / component.get("path", "")
            if component.get("license") != "MIT":
                errors.append(f"bundled component {name} is not declared MIT")
            if not path.is_dir():
                errors.append(f"bundled component {name} is missing: {path}")
            elif not (path / "LICENSE").is_file():
                errors.append(f"bundled component {name} has no LICENSE file")
            else:
                for license_path in path.rglob("LICENSE*"):
                    if not license_path.is_file():
                        continue
                    license_text = license_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
                    if not license_text.lstrip().startswith("MIT License"):
                        errors.append(
                            f"bundled component {name} contains a non-MIT "
                            f"license file: {license_path.relative_to(ROOT)}"
                        )
        elif component.get("kind") in {"managed_external", "remote_external"}:
            forbidden_path = ROOT / "external" / "managed" / name
            if forbidden_path.exists():
                errors.append(
                    f"external component {name} is present in the Git checkout: "
                    f"{forbidden_path}"
                )

    for name, upstream in upstreams.get("upstreams", {}).items():
        component = components.get("components", {}).get(name)
        if not component:
            errors.append(f"upstream {name} has no component entry")
            continue
        if component.get("pin") != upstream.get("pinned_commit"):
            errors.append(f"pin mismatch for {name}")
        if component.get("path") != upstream.get("path"):
            errors.append(f"path mismatch for {name}")
        upstream_root = ROOT / upstream.get("path", "")
        for excluded_path in upstream.get("excluded_paths", []):
            candidate = upstream_root / excluded_path
            contains_files = candidate.is_file() or (
                candidate.is_dir()
                and any(path.is_file() for path in candidate.rglob("*"))
            )
            if contains_files:
                errors.append(
                    f"excluded upstream path was reintroduced: "
                    f"{candidate.relative_to(ROOT)}"
                )

    orchestrator = read_yaml("config/orchestrator.yaml")
    if orchestrator.get("orchestrator", {}).get("engine") != "hermes":
        errors.append("Hermes is not configured as orchestrator")
    if orchestrator.get("orchestrator", {}).get("sole_authority") is not True:
        errors.append("sole orchestration authority is not enabled")
    if orchestrator.get("execution", {}).get("strategic_planning") is not False:
        errors.append("Forge strategic planning must be disabled")

    for fixture, schema in (
        (
            "tests/fixtures/create-task-command.json",
            "platform/contracts/v1/command.schema.json",
        ),
        (
            "tests/fixtures/task-created-event.json",
            "platform/contracts/v1/event.schema.json",
        ),
    ):
        errors.extend(validate_schema(read_json(fixture), schema))

    if errors:
        print("Baseline validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Baseline valid: 2 bundled MIT core components, "
        "1 disabled managed external component, contracts v1."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
