from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from scoresymphony_workers import (
    ShellCommand,
    ShellCommandValidationError,
    ShellExecutionStatus,
    ShellWorker,
)


FIXTURE_REPOSITORY = Path(__file__).parent / "fixtures" / "shell_worker_repository"


def _workspace(tmp_path: Path, name: str = "repository") -> Path:
    workspace = tmp_path / name
    shutil.copytree(FIXTURE_REPOSITORY, workspace)
    return workspace


def _worker(workspace: Path) -> ShellWorker:
    return ShellWorker(workspace, allowed_executables=(sys.executable,))


def _fixture_command(*arguments: str, timeout_seconds: float = 5.0) -> ShellCommand:
    return ShellCommand(
        argv=(sys.executable, "fixture_command.py", *arguments),
        timeout_seconds=timeout_seconds,
    )


def test_reference_worker_is_deterministic_across_clean_workspaces(tmp_path: Path) -> None:
    first_workspace = _workspace(tmp_path, "first")
    second_workspace = _workspace(tmp_path, "second")

    command = _fixture_command("render", "input.txt", "output.txt")
    first_result = _worker(first_workspace).execute(command)
    second_result = _worker(second_workspace).execute(command)

    assert first_result == second_result
    assert first_result.status is ShellExecutionStatus.SUCCEEDED
    assert first_result.exit_code == 0
    assert first_result.error_code is None
    assert (first_workspace / "output.txt").read_bytes() == (
        second_workspace / "output.txt"
    ).read_bytes()
    assert first_result.as_dict()["stdout_sha256"] == first_result.stdout_sha256


def test_shell_metacharacters_are_passed_as_literal_arguments(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    literal = "hello; touch should-not-exist.txt"

    result = _worker(workspace).execute(_fixture_command("echo", literal))

    assert result.status is ShellExecutionStatus.SUCCEEDED
    assert json.loads(result.stdout) == [literal]
    assert not (workspace / "should-not-exist.txt").exists()


def test_nonzero_exit_is_structured_failure(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    result = _worker(workspace).execute(_fixture_command("fail", "23"))

    assert result.status is ShellExecutionStatus.FAILED
    assert result.exit_code == 23
    assert result.error_code == "nonzero_exit"
    assert result.stdout == ""
    assert result.stderr == "fixture failure\n"


def test_timeout_is_structured_and_does_not_raise(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    result = _worker(workspace).execute(
        _fixture_command("sleep", "1.0", timeout_seconds=0.05)
    )

    assert result.status is ShellExecutionStatus.TIMED_OUT
    assert result.exit_code is None
    assert result.error_code == "timeout"


def test_worker_uses_deterministic_process_environment(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    result = _worker(workspace).execute(_fixture_command("environment"))

    assert result.status is ShellExecutionStatus.SUCCEEDED
    assert json.loads(result.stdout) == {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "TZ": "UTC",
    }


def test_worker_rejects_workspace_escape(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    command = ShellCommand(
        argv=(sys.executable, "fixture_command.py", "echo", "safe"),
        cwd="..",
    )

    with pytest.raises(ShellCommandValidationError, match="workspace_root"):
        _worker(workspace).execute(command)


def test_worker_rejects_non_allowlisted_executable(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    not_allowed = str(Path(sys.executable).parent / "not-allowlisted-executable")
    command = ShellCommand(argv=(not_allowed,))

    with pytest.raises(ShellCommandValidationError, match="does not exist|allowlisted"):
        _worker(workspace).execute(command)


def test_worker_rejects_relative_executable_names(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    command = ShellCommand(argv=(Path(sys.executable).name, "--version"))

    with pytest.raises(ShellCommandValidationError, match="absolute executable path"):
        _worker(workspace).execute(command)


def test_worker_rejects_timeout_above_configured_limit(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    worker = ShellWorker(
        workspace,
        allowed_executables=(sys.executable,),
        max_timeout_seconds=1.0,
    )

    with pytest.raises(ShellCommandValidationError, match="max_timeout_seconds"):
        worker.execute(_fixture_command("echo", "safe", timeout_seconds=1.01))
