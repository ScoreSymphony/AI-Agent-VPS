from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from threading import Event, Timer

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
    return ShellWorker(
        workspace,
        allowed_executables=(sys.executable,),
        allowed_write_paths=("output.txt", ".retry-state"),
    )


def _fixture_command(
    *arguments: str,
    timeout_seconds: float = 5.0,
    declared_write_paths: tuple[str, ...] = (),
) -> ShellCommand:
    return ShellCommand(
        argv=(sys.executable, "fixture_command.py", *arguments),
        timeout_seconds=timeout_seconds,
        declared_write_paths=declared_write_paths,
    )


def test_reference_worker_is_deterministic_across_clean_workspaces(tmp_path: Path) -> None:
    first_workspace = _workspace(tmp_path, "first")
    second_workspace = _workspace(tmp_path, "second")

    command = _fixture_command(
        "render",
        "input.txt",
        "output.txt",
        declared_write_paths=("output.txt",),
    )
    first_result = _worker(first_workspace).execute(command)
    second_result = _worker(second_workspace).execute(command)

    assert first_result == second_result
    assert first_result.status is ShellExecutionStatus.SUCCEEDED
    assert first_result.exit_code == 0
    assert first_result.error_code is None
    assert first_result.changed_paths == ("output.txt",)
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
    assert result.changed_paths == ()
    assert not (workspace / "should-not-exist.txt").exists()


def test_nonzero_exit_is_structured_failure(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    result = _worker(workspace).execute(_fixture_command("fail", "23"))

    assert result.status is ShellExecutionStatus.FAILED
    assert result.exit_code == 23
    assert result.error_code == "nonzero_exit"
    assert result.stdout == ""
    assert result.stderr == "fixture failure\n"
    assert result.changed_paths == ()


def test_timeout_is_structured_and_does_not_raise(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    result = _worker(workspace).execute(
        _fixture_command("sleep", "1.0", timeout_seconds=0.05)
    )

    assert result.status is ShellExecutionStatus.TIMED_OUT
    assert result.exit_code is None
    assert result.error_code == "timeout"
    assert result.changed_paths == ()


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group semantics")
def test_timeout_remains_bounded_after_parent_exits_with_live_descendant(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    started = time.monotonic()

    result = _worker(workspace).execute(
        _fixture_command(
            "spawn-descendant-and-exit",
            "2.0",
            timeout_seconds=0.10,
        )
    )
    elapsed = time.monotonic() - started

    assert result.status is ShellExecutionStatus.TIMED_OUT
    assert result.exit_code is None
    assert result.error_code == "timeout"
    assert "spawned descendant" in result.stdout
    assert elapsed < 1.5


def test_cancel_is_structured_and_terminates_the_running_process(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    cancel_event = Event()
    cancel_timer = Timer(0.05, cancel_event.set)
    cancel_timer.start()
    try:
        result = _worker(workspace).execute(
            _fixture_command("sleep", "2.0", timeout_seconds=5.0),
            cancel_event=cancel_event,
        )
    finally:
        cancel_timer.cancel()
        cancel_timer.join()

    assert result.status is ShellExecutionStatus.CANCELLED
    assert result.exit_code is None
    assert result.error_code == "cancelled"
    assert result.changed_paths == ()
    assert "finished sleeping" not in result.stdout


def test_retry_is_a_new_deterministic_attempt_in_the_same_workspace(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    worker = _worker(workspace)
    command = _fixture_command(
        "retry-once",
        ".retry-state",
        "output.txt",
        declared_write_paths=(".retry-state", "output.txt"),
    )

    first_result = worker.execute(command)
    second_result = worker.execute(command)

    assert first_result.status is ShellExecutionStatus.FAILED
    assert first_result.exit_code == 75
    assert first_result.error_code == "nonzero_exit"
    assert first_result.changed_paths == (".retry-state",)
    assert second_result.status is ShellExecutionStatus.SUCCEEDED
    assert second_result.exit_code == 0
    assert second_result.error_code is None
    assert second_result.changed_paths == ("output.txt",)
    assert (workspace / "output.txt").read_text(encoding="utf-8") == "retry succeeded\n"


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


def test_worker_rejects_declared_write_path_outside_workspace(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    command = _fixture_command(
        "render",
        "input.txt",
        "../outside.txt",
        declared_write_paths=("../outside.txt",),
    )

    with pytest.raises(ShellCommandValidationError, match="workspace_root"):
        _worker(workspace).execute(command)

    assert not (tmp_path / "outside.txt").exists()


def test_worker_rejects_declared_write_path_not_in_allowlist(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    command = _fixture_command(
        "render",
        "input.txt",
        "forbidden.txt",
        declared_write_paths=("forbidden.txt",),
    )

    with pytest.raises(ShellCommandValidationError, match="not allowlisted"):
        _worker(workspace).execute(command)

    assert not (workspace / "forbidden.txt").exists()


def test_worker_reports_undeclared_workspace_changes_as_policy_violation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    result = _worker(workspace).execute(
        _fixture_command("render", "input.txt", "output.txt")
    )

    assert result.status is ShellExecutionStatus.FAILED
    assert result.exit_code == 0
    assert result.error_code == "path_policy_violation"
    assert result.changed_paths == ("output.txt",)


@pytest.mark.skipif(os.name != "posix", reason="POSIX executable-bit semantics")
def test_worker_reports_undeclared_mode_only_change_as_policy_violation(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    source = workspace / "input.txt"
    before_bytes = source.read_bytes()

    result = _worker(workspace).execute(
        _fixture_command("toggle-executable", "input.txt")
    )

    assert source.read_bytes() == before_bytes
    assert result.status is ShellExecutionStatus.FAILED
    assert result.exit_code == 0
    assert result.error_code == "path_policy_violation"
    assert result.changed_paths == ("input.txt",)


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