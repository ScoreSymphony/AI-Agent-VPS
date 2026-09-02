from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path


def _render(source_name: str, output_name: str) -> int:
    source = Path(source_name).read_text(encoding="utf-8")
    normalized = "\n".join(line.rstrip() for line in source.splitlines()) + "\n"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    Path(output_name).write_text(
        f"sha256={digest}\n{normalized}",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {"lines": len(normalized.splitlines()), "sha256": digest},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


def _echo(arguments: list[str]) -> int:
    print(json.dumps(arguments, ensure_ascii=True, separators=(",", ":")))
    return 0


def _environment() -> int:
    keys = ("LANG", "LC_ALL", "TZ", "PYTHONHASHSEED", "PYTHONIOENCODING", "PYTHONUTF8")
    print(
        json.dumps(
            {key: os.environ.get(key) for key in keys},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


def _retry_once(marker_name: str, output_name: str) -> int:
    marker = Path(marker_name)
    if not marker.exists():
        marker.write_text("retry-required\n", encoding="utf-8", newline="\n")
        print("retry required", file=sys.stderr)
        return 75
    Path(output_name).write_text("retry succeeded\n", encoding="utf-8", newline="\n")
    print("retry succeeded")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        return 64

    operation, *arguments = argv
    if operation == "render" and len(arguments) == 2:
        return _render(arguments[0], arguments[1])
    if operation == "echo":
        return _echo(arguments)
    if operation == "environment" and not arguments:
        return _environment()
    if operation == "fail" and len(arguments) == 1:
        print("fixture failure", file=sys.stderr)
        return int(arguments[0])
    if operation == "sleep" and len(arguments) == 1:
        time.sleep(float(arguments[0]))
        print("finished sleeping")
        return 0
    if operation == "retry-once" and len(arguments) == 2:
        return _retry_once(arguments[0], arguments[1])

    return 64


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
