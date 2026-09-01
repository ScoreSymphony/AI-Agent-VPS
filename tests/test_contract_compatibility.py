from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from scoresymphony_contracts import CommandV1, EventV1, JsonObject, parse_command, parse_event


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> JsonObject:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_command_fixture_when_checked_by_schema_and_runtime_is_compatible() -> None:
    # Given
    instance = load_json("tests/fixtures/create-task-command.json")
    schema = load_json("platform/contracts/v1/command.schema.json")

    # When
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            instance
        )
    )
    runtime_result = parse_command(instance)

    # Then
    assert errors == []
    assert isinstance(runtime_result, CommandV1)


def test_event_fixture_when_checked_by_schema_and_runtime_is_compatible() -> None:
    # Given
    instance = load_json("tests/fixtures/task-created-event.json")
    schema = load_json("platform/contracts/v1/event.schema.json")

    # When
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            instance
        )
    )
    runtime_result = parse_event(instance)

    # Then
    assert errors == []
    assert isinstance(runtime_result, EventV1)


def test_schema_when_loaded_declares_supported_v1_dialect() -> None:
    # Given
    schemas = (
        load_json("platform/contracts/v1/command.schema.json"),
        load_json("platform/contracts/v1/event.schema.json"),
    )

    # When / Then
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["properties"]["schema_version"] == {"const": 1}


@pytest.mark.parametrize(
    ("event_type", "task_id", "run_id", "outcome"),
    [
        ("task.created", None, None, None),
        ("task.updated", "9a9a0d0d-3c62-4a4a-9ef7-80fb7b3d429c", "a7640bf2-e3ed-4d76-a72a-d64e58722ef8", None),
        ("run.started", None, "a7640bf2-e3ed-4d76-a72a-d64e58722ef8", None),
        ("review.completed", "9a9a0d0d-3c62-4a4a-9ef7-80fb7b3d429c", None, None),
        ("events.snapshot", "9a9a0d0d-3c62-4a4a-9ef7-80fb7b3d429c", None, None),
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
    run_id: str | None,
    outcome: JsonObject | None,
) -> None:
    # Given
    instance = deepcopy(load_json("tests/fixtures/task-created-event.json"))
    instance["event_type"] = event_type
    instance["task_id"] = task_id
    instance["run_id"] = run_id
    instance["outcome"] = outcome
    schema = load_json("platform/contracts/v1/event.schema.json")

    # When
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(instance)
    )

    # Then
    assert errors
