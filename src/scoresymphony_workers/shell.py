from __future__ import annotations

import hashlib
import math
import os
import signal
import stat
import subprocess
import time
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from threading import Event
from types import MappingProxyType
from typing import Mapping, Sequence


class ShellExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class ShellWorkerConfigurationError(ValueError):
    """Raised when the reference worker itself is configured unsafely or invalidly."""


class ShellCommandValidationError(ValueError):
    """Raised when a requested command violates the worker boundary."""


@dataclass(frozen=True, slots=True)
class ShellCommand:
    """One explicit process invocation executed without a command shell."""

    argv: tuple[str, ...]
    cwd: str = "."
    timeout_seconds: float = 30.0
    declared_write_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "argv", tuple(self.argv))
        object.__setattr__(self, "declared_write_paths", tuple(self.declared_write_paths))

        if not self.argv:
            raise ShellCommandValidationError("argv must contain an executable")
        if any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in self.argv):
            raise ShellCommandValidationError(
                "argv entries must be non-empty strings without NUL bytes"
            )
        if not isinstance(self.cwd, str) or not self.cwd or "\x00" in self.cwd:
            raise ShellCommandValidationError(
                "cwd must be a non-empty string without NUL bytes"
            )
        if any(
            not isinstance(path, str) or not path or "\x00" in path
            for path in self.declared_write_paths
        ):
            raise ShellCommandValidationError(
                "declared_write_paths entries must be non-empty strings without NUL bytes"
            )
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(float(self.timeout_seconds))
            or self.timeout_seconds <= 0
        ):
            raise ShellCommandValidationError("timeout_seconds must be a positive number")


@dataclass(frozen=True, slots=True)
class ShellExecutionResult:
    """Stable, serializable evidence produced by one shell-worker invocation."""

    status: ShellExecutionStatus
    argv: tuple[str, ...]
    cwd: str
    exit_code: int | None
    stdout: str
    stderr: str
    error_code: str | None = None
    changed_paths: tuple[str, ...] = ()

    @property
    def stdout_sha256(self) -> str:
        return hashlib.sha256(self.stdout.encode("utf-8")).hexdigest()

    @property
    def stderr_sha256(self) -> str:
        return hashlib.sha256(self.stderr.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "argv": list(self.argv),
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "error_code": self.error_code,
            "changed_paths": list(self.changed_paths),
        }


class ShellWorker:
    """Deterministic reference process runner for fixture and integration work.

    This class intentionally does not publish Forge events and is not a security sandbox.
    The integration runtime remains responsible for lifecycle events, approvals, isolation,
    retries/recovery, and durable orchestration state.
    """

    _DETERMINISTIC_ENV = MappingProxyType(
        {
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TZ": "UTC",
            "PYTHONHASHSEED": "0",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
    )
    _CANCEL_POLL_SECONDS = 0.05
    _TERMINATION_GRACE_SECONDS = 1.0

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        allowed_executables: Sequence[str | Path],
        allowed_write_paths: Sequence[str | Path] = (),
        max_timeout_seconds: float = 120.0,
        extra_environment: Mapping[str, str] | None = None,
    ) -> None:
        root = Path(workspace_root).expanduser().resolve()
        if not root.is_dir():
            raise ShellWorkerConfigurationError(
                f"workspace_root must be an existing directory: {root}"
            )

        if (
            isinstance(max_timeout_seconds, bool)
            or not isinstance(max_timeout_seconds, (int, float))
            or not math.isfinite(float(max_timeout_seconds))
            or max_timeout_seconds <= 0
        ):
            raise ShellWorkerConfigurationError(
                "max_timeout_seconds must be a positive number"
            )

        normalized_executables: set[str] = set()
        for executable in allowed_executables:
            executable_path = Path(executable).expanduser()
            if not executable_path.is_absolute():
                raise ShellWorkerConfigurationError(
                    "allowed executables must use absolute paths"
                )
            try:
                resolved = executable_path.resolve(strict=True)
            except OSError as exc:
                raise ShellWorkerConfigurationError(
                    f"allowed executable does not exist: {executable_path}"
                ) from exc
            if not resolved.is_file():
                raise ShellWorkerConfigurationError(
                    f"allowed executable is not a file: {resolved}"
                )
            normalized_executables.add(self._path_key(resolved))

        if not normalized_executables:
            raise ShellWorkerConfigurationError(
                "at least one allowed executable must be configured"
            )

        normalized_write_paths: set[str] = set()
        for write_path in allowed_write_paths:
            try:
                normalized_write_paths.add(self._normalize_workspace_path(root, write_path))
            except ShellCommandValidationError as exc:
                raise ShellWorkerConfigurationError(str(exc)) from exc

        environment = dict(self._DETERMINISTIC_ENV)
        # Windows needs these variables for reliable process startup. They are inherited
        # only when present and cannot be overridden per command.
        for key in ("SystemRoot", "WINDIR"):
            value = os.environ.get(key)
            if value:
                environment[key] = value

        if extra_environment:
            for key, value in extra_environment.items():
                if not isinstance(key, str) or not key or "\x00" in key or "=" in key:
                    raise ShellWorkerConfigurationError(
                        "environment keys must be non-empty strings without NUL or '='"
                    )
                if not isinstance(value, str) or "\x00" in value:
                    raise ShellWorkerConfigurationError(
                        "environment values must be strings without NUL bytes"
                    )
                if key in self._DETERMINISTIC_ENV:
                    raise ShellWorkerConfigurationError(
                        f"deterministic environment key cannot be overridden: {key}"
                    )
                environment[key] = value

        self._workspace_root = root
        self._allowed_executables = frozenset(normalized_executables)
        self._allowed_write_paths = frozenset(normalized_write_paths)
        self._max_timeout_seconds = float(max_timeout_seconds)
        self._environment = MappingProxyType(environment)

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def execute(
        self,
        command: ShellCommand,
        *,
        cancel_event: Event | None = None,
    ) -> ShellExecutionResult:
        if command.timeout_seconds > self._max_timeout_seconds:
            raise ShellCommandValidationError(
                "command timeout exceeds worker max_timeout_seconds"
            )

        cwd = self._resolve_cwd(command.cwd)
        executable = self._resolve_executable(command.argv[0])
        declared_write_paths = self._validate_declared_write_paths(
            command.declared_write_paths
        )
        argv = (str(executable), *command.argv[1:])
        before = self._snapshot_workspace()

        popen_kwargs: dict[str, object] = {}
        if os.name == "posix":
            popen_kwargs["start_new_session"] = True
        elif os.name == "nt":
            popen_kwargs["creationflags"] = getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )

        if cancel_event is not None and cancel_event.is_set():
            return ShellExecutionResult(
                status=ShellExecutionStatus.CANCELLED,
                argv=tuple(command.argv),
                cwd=command.cwd,
                exit_code=None,
                stdout="",
                stderr="",
                error_code="cancelled",
            )

        before = self._snapshot_workspace()

        popen_kwargs: dict[str, object] = {}
        if os.name == "posix":
            popen_kwargs["start_new_session"] = True
        elif os.name == "nt":
            popen_kwargs["creationflags"] = getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )

        try:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=dict(self._environment),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                **popen_kwargs,
            )
        except OSError as exc:
            result = ShellExecutionResult(
                status=ShellExecutionStatus.FAILED,
                argv=tuple(command.argv),
                cwd=command.cwd,
                exit_code=None,
                stdout="",
                stderr=self._normalize_output(str(exc)),
                error_code="spawn_error",
            )
            return self._attach_workspace_evidence(result, before, declared_write_paths)

        deadline = time.monotonic() + float(command.timeout_seconds)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stdout, stderr = self._terminate_and_collect(process)
                result = ShellExecutionResult(
                    status=ShellExecutionStatus.TIMED_OUT,
                    argv=tuple(command.argv),
                    cwd=command.cwd,
                    exit_code=None,
                    stdout=stdout,
                    stderr=stderr,
                    error_code="timeout",
                )
                return self._attach_workspace_evidence(
                    result, before, declared_write_paths
                )

            wait_seconds = min(self._CANCEL_POLL_SECONDS, remaining)
            try:
                stdout, stderr = process.communicate(timeout=wait_seconds)
                break
            except subprocess.TimeoutExpired:
                if cancel_event is not None and cancel_event.is_set():
                    stdout, stderr = self._terminate_and_collect(process)
                    result = ShellExecutionResult(
                        status=ShellExecutionStatus.CANCELLED,
                        argv=tuple(command.argv),
                        cwd=command.cwd,
                        exit_code=None,
                        stdout=stdout,
                        stderr=stderr,
                        error_code="cancelled",
                    )
                    return self._attach_workspace_evidence(
                        result, before, declared_write_paths
                    )

        status = (
            ShellExecutionStatus.SUCCEEDED
            if process.returncode == 0
            else ShellExecutionStatus.FAILED
        )
        result = ShellExecutionResult(
            status=status,
            argv=tuple(command.argv),
            cwd=command.cwd,
            exit_code=process.returncode,
            stdout=self._normalize_output(stdout),
            stderr=self._normalize_output(stderr),
            error_code=None if process.returncode == 0 else "nonzero_exit",
        )
        return self._attach_workspace_evidence(result, before, declared_write_paths)

    def _resolve_cwd(self, relative_cwd: str) -> Path:
        candidate = (self._workspace_root / relative_cwd).resolve()
        try:
            candidate.relative_to(self._workspace_root)
        except ValueError as exc:
            raise ShellCommandValidationError(
                "cwd must stay within workspace_root"
            ) from exc
        if not candidate.is_dir():
            raise ShellCommandValidationError(
                f"cwd must resolve to an existing directory: {relative_cwd}"
            )
        return candidate

    def _resolve_executable(self, requested: str) -> Path:
        requested_path = Path(requested).expanduser()
        if not requested_path.is_absolute():
            raise ShellCommandValidationError(
                "argv[0] must be an absolute executable path"
            )
        try:
            resolved = requested_path.resolve(strict=True)
        except OSError as exc:
            raise ShellCommandValidationError(
                f"executable does not exist: {requested_path}"
            ) from exc
        if self._path_key(resolved) not in self._allowed_executables:
            raise ShellCommandValidationError(
                f"executable is not allowlisted: {resolved}"
            )
        return resolved

    def _validate_declared_write_paths(self, paths: Sequence[str]) -> frozenset[str]:
        normalized = frozenset(
            self._normalize_workspace_path(self._workspace_root, path) for path in paths
        )
        disallowed = normalized - self._allowed_write_paths
        if disallowed:
            formatted = ", ".join(sorted(disallowed))
            raise ShellCommandValidationError(
                f"declared write paths are not allowlisted: {formatted}"
            )
        return normalized

    def _attach_workspace_evidence(
        self,
        result: ShellExecutionResult,
        before: Mapping[str, str],
        declared_write_paths: frozenset[str],
    ) -> ShellExecutionResult:
        after = self._snapshot_workspace()
        changed_paths = tuple(
            sorted(
                path
                for path in before.keys() | after.keys()
                if before.get(path) != after.get(path)
            )
        )
        unexpected = set(changed_paths) - declared_write_paths
        if unexpected:
            return replace(
                result,
                status=ShellExecutionStatus.FAILED,
                error_code="path_policy_violation",
                changed_paths=changed_paths,
            )
        return replace(result, changed_paths=changed_paths)

    def _snapshot_workspace(self) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for path in sorted(self._workspace_root.rglob("*")):
            relative = path.relative_to(self._workspace_root).as_posix()
            mode = stat.S_IMODE(path.lstat().st_mode)
            if path.is_symlink():
                snapshot[relative] = f"symlink:{mode:o}:{os.readlink(path)}"
            elif path.is_dir():
                snapshot[relative] = f"directory:{mode:o}"
            elif path.is_file():
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                snapshot[relative] = f"file:{mode:o}:{digest.hexdigest()}"
            else:
                snapshot[relative] = f"other:{mode:o}"
        return snapshot

    @classmethod
    def _normalize_workspace_path(cls, root: Path, requested: str | Path) -> str:
        requested_path = Path(requested)
        if requested_path.is_absolute():
            raise ShellCommandValidationError(
                "write paths must be workspace-relative"
            )
        candidate = (root / requested_path).resolve()
        try:
            relative = candidate.relative_to(root)
        except ValueError as exc:
            raise ShellCommandValidationError(
                "write paths must stay within workspace_root"
            ) from exc
        if relative == Path("."):
            raise ShellCommandValidationError(
                "workspace_root itself cannot be used as an allowed write path"
            )
        return relative.as_posix()

    def _terminate_and_collect(
        self, process: subprocess.Popen[str]
    ) -> tuple[str, str]:
        self._signal_process_group(process, force=False)
        try:
            stdout, stderr = process.communicate(timeout=self._TERMINATION_GRACE_SECONDS)
        except subprocess.TimeoutExpired as first_timeout:
            self._signal_process_group(process, force=True)
            try:
                stdout, stderr = process.communicate(
                    timeout=self._TERMINATION_GRACE_SECONDS
                )
            except subprocess.TimeoutExpired as final_timeout:
                stdout = (
                    final_timeout.stdout
                    if final_timeout.stdout is not None
                    else first_timeout.stdout
                )
                stderr = (
                    final_timeout.stderr
                    if final_timeout.stderr is not None
                    else first_timeout.stderr
                )
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
                try:
                    process.wait(timeout=self._CANCEL_POLL_SECONDS)
                except subprocess.TimeoutExpired:
                    pass
        return self._normalize_output(stdout), self._normalize_output(stderr)

    @staticmethod
    def _signal_process_group(
        process: subprocess.Popen[str], *, force: bool
    ) -> None:
        if os.name == "posix":
            group_signal = signal.SIGKILL if force else signal.SIGTERM
            try:
                os.killpg(process.pid, group_signal)
            except ProcessLookupError:
                pass
            return

        try:
            if force:
                process.kill()
            else:
                process.terminate()
        except OSError:
            pass

    @staticmethod
    def _path_key(path: Path) -> str:
        return os.path.normcase(str(path))

    @staticmethod
    def _normalize_output(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        return value.replace("\r\n", "\n").replace("\r", "\n")
