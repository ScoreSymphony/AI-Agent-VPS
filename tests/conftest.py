from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def load_json_fixture(repo_root: Path) -> Callable[[str], Any]:
    def _load(relative_path: str) -> Any:
        path = repo_root / "tests" / "fixtures" / relative_path
        return json.loads(path.read_text(encoding="utf-8"))

    return _load
