#!/usr/bin/env python3
"""Fail CI when tracked repository content contains high-confidence secrets.

This scanner intentionally focuses on strong signatures and tracked secret files.
It complements, but does not replace, GitHub Secret Scanning / push protection.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_SIZE = 2 * 1024 * 1024

ALLOWED_ENV_FILES = {".env.example"}
SENSITIVE_SUFFIXES = {".key", ".p12", ".pfx"}

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private key",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b")),
)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]


def sensitive_path_reason(path: Path) -> str | None:
    rel = path.relative_to(ROOT)
    name = rel.name

    if name.startswith(".env") and name not in ALLOWED_ENV_FILES:
        return "tracked environment file"

    if rel.suffix.lower() in SENSITIVE_SUFFIXES:
        return f"tracked private credential/container file ({rel.suffix})"

    return None


def scan_text(text: str) -> list[str]:
    return [label for label, pattern in PATTERNS if pattern.search(text)]


def main() -> int:
    violations: list[str] = []

    for path in tracked_files():
        if not path.is_file():
            continue

        reason = sensitive_path_reason(path)
        if reason:
            violations.append(f"{path.relative_to(ROOT)}: {reason}")
            continue

        try:
            if path.stat().st_size > MAX_FILE_SIZE:
                continue
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for finding in scan_text(text):
            violations.append(f"{path.relative_to(ROOT)}: possible {finding}")

    if violations:
        print("Secret scan failed. Do not print or paste the secret value into CI logs.", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1

    print("Secret scan passed: no high-confidence secret signatures found in tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
