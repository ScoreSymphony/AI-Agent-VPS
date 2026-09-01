#!/usr/bin/env python3
"""Read-only check for newer Forge and Hermes upstream commits."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def remote_commit(repository: str, branch: str) -> str:
    process = subprocess.run(
        ["git", "ls-remote", repository, f"refs/heads/{branch}"],
        check=True,
        capture_output=True,
        text=True,
    )
    line = process.stdout.strip()
    if not line:
        raise RuntimeError(f"No commit returned for {repository} {branch}")
    return line.split()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "UPSTREAMS.yaml"
    )
    args = parser.parse_args()
    data = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    updates = 0

    for name, upstream in data["upstreams"].items():
        current = remote_commit(upstream["repository"], upstream["default_branch"])
        pinned = upstream["pinned_commit"]
        state = "current" if current == pinned else "review available"
        updates += current != pinned
        print(f"{name}: {state}")
        print(f"  pinned: {pinned}")
        print(f"  remote: {current}")

    return 2 if updates else 0


if __name__ == "__main__":
    raise SystemExit(main())
