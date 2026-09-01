from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from .models import ContractRejection, JsonObject, JsonValue, RejectionCode


PACKAGE_SCHEMA_ROOT: Final = Path(__file__).resolve().parent / "schemas" / "v1"
REPOSITORY_SCHEMA_ROOT: Final = Path(__file__).resolve().parents[2] / "platform" / "contracts" / "v1"
IDENTIFIER_FIELDS: Final = frozenset(
    {
        "command_id",
        "event_id",
        "task_id",
        "execution_id",
        "project_id",
        "correlation_id",
        "causation_id",
    }
)
TIMESTAMP_FIELDS: Final = frozenset({"issued_at", "occurred_at"})


def _load_schema(name: str) -> JsonObject:
    package_path = PACKAGE_SCHEMA_ROOT / name
    schema_path = package_path if package_path.is_file() else REPOSITORY_SCHEMA_ROOT / name
    raw: JsonValue = json.loads(schema_path.read_text(encoding="utf-8"))
    match raw:
        case dict() as schema:
            return schema
        case unreachable:
            raise TypeError(f"contract schema {name} must be an object: {unreachable!r}")


COMMAND_VALIDATOR: Final = Draft202012Validator(
    _load_schema("command.schema.json"), format_checker=FormatChecker()
)
EVENT_VALIDATOR: Final = Draft202012Validator(
    _load_schema("event.schema.json"), format_checker=FormatChecker()
)


def error_path(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.absolute_path) or "$"


def schema_rejection(error: ValidationError) -> ContractRejection:
    path = error_path(error)
    leaf = path.rsplit(".", maxsplit=1)[-1]
    if error.validator == "required" and isinstance(error.instance, Mapping):
        missing = sorted(set(error.validator_value) - set(error.instance))[0]
        return ContractRejection(
            RejectionCode.MISSING_REQUIRED_FIELD,
            f"required field is missing: {missing}",
            missing if path == "$" else f"{path}.{missing}",
        )
    if leaf in IDENTIFIER_FIELDS:
        return ContractRejection(
            RejectionCode.INVALID_IDENTIFIER,
            f"invalid identifier: {leaf}",
            path,
        )
    if leaf in TIMESTAMP_FIELDS:
        return ContractRejection(
            RejectionCode.INVALID_TIMESTAMP,
            f"invalid timestamp: {leaf}",
            path,
        )
    return ContractRejection(RejectionCode.SCHEMA_VIOLATION, error.message, path)
