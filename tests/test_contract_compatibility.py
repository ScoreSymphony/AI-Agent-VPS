from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from scoresymphony_contracts import CommandV1, EventV1, JsonObject, parse_command, parse_event


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> JsonObject:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_command_fixture_when_checked_by_schema_and_runtime_is_compatible() -> None:
    instance = load_json("tests/fixtures/create-task-command.json")
    schema = load_json("platform/contracts/v1/command.schema.json")
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(instance)
    )
    runtime_result = parse_command(instance)
    assert errors == []
    assert isinstance(runtime_result, CommandV1)


def test_event_fixture_when_checked_by_schema_and_runtime_is_compatible() -> None:
    instance = load_json("tests/fixtures/task-created-event.json")
    schema = load_json("platform/contracts/v1/event.schema.json")
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(instance)
    )
    runtime_result = parse_event(instance)
    assert errors == []
    assert isinstance(runtime_result, EventV1)


def test_schema_when_loaded_declares_supported_v1_dialect() -> None:
    schemas = (
        load_json("platform/contracts/v1/command.schema.json"),
        load_json("platform/contracts/v1/event.schema.json"),
    )
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["properties"]["schema_version"] == {"const": 1}


def test_command_schema_maps_only_verified_forge_lifecycle_intents() -> None:
    schema = load_json("platform/contracts/v1/command.schema.json")
    assert set(schema["properties"]["command"]["enum"]) == {
        "create_task",
        "update_task",
        "start_task",
        "submit_task",
        "request_changes_task",
        "approve_task",
        "cancel_task",
        "retry_execution",
        "cancel_execution",
    }


@pytest.mark.parametrize(
    ("event_type", "task_id", "execution_id", "outcome"),
    [
        ("task.created", None, None, None),
        (
            "task.updated",
            "9a9a0d0d-3c62-4a4a-9ef7-80fb7b3d429c",
            "a7640bf2-e3ed-4d76-a72a-d64e58722ef8",
            None,
        ),
        (
            "execution.started",
            None,
            "a7640bf2-e3ed-4d76-a72a-d64e58722ef8",
            None,
        ),
        (
            "review.completed",
            "9a9a0d0d-3c62-4a4a-9ef7-80fb7b3d429c",
            "a7640bf2-e3ed-4d76-a72a-d64e58722ef8",
            None,
        ),
        (
            "events.snapshot",
            "9a9a0d0d-3c62-4a4a-9ef7-80fb7b3d429c",
            None,
            None,
        ),
        (
            "resources.reported",
            None,
            None,
            {
                "status": "success",
                "code": "command_completed",
                "message": "Invalid for a global event",
                "details": {},
            },
        ),
    ],
)
def test_event_schema_when_state_is_invalid_rejects_wire_message(
    event_type: str,
    task_id: str | None,
    execution_id: str | None,
    outcome: JsonObject | None,
) -> None:
    instance = deepcopy(load_json("tests/fixtures/task-created-event.json"))
    instance["event_type"] = event_type
    instance["task_id"] = task_id
    instance["execution_id"] = execution_id
    instance["outcome"] = outcome
    schema = load_json("platform/contracts/v1/event.schema.json")
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(instance)
    )
    assert errors


def test_source_distribution_builds_wheel_with_canonical_contract_schemas(
    tmp_path: Path,
) -> None:
    egg_base = tmp_path / "egg-info"
    dist_dir = tmp_path / "dist"
    unpack_dir = tmp_path / "unpack"
    wheel_dir = tmp_path / "wheel"
    for directory in (egg_base, dist_dir, unpack_dir, wheel_dir):
        directory.mkdir()
    subprocess.run(
        [
            sys.executable,
            "setup.py",
            "--quiet",
            "egg_info",
            "--egg-base",
            str(egg_base),
            "sdist",
            "--dist-dir",
            str(dist_dir),
        ],
        cwd=ROOT,
        check=True,
    )
    archive = next(dist_dir.glob("*.tar.gz"))
    with tarfile.open(archive) as source_distribution:
        source_distribution.extractall(unpack_dir, filter="data")
    source_root = next(unpack_dir.iterdir())
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(source_root),
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
        ],
        check=True,
    )
    wheel = next(wheel_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel) as built_wheel:
        for name in ("command.schema.json", "event.schema.json"):
            packaged = built_wheel.read(f"scoresymphony_contracts/schemas/v1/{name}")
            canonical = (ROOT / "platform" / "contracts" / "v1" / name).read_bytes()
            assert packaged == canonical
