from __future__ import annotations

import hashlib
import math
import os
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence


class ShellExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "argv", tuple(self.argv))

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
        }


class ShellWorker:
    """Deterministic reference process runner for fixture and integration work.

    This class intentionally does not publish Forge events and is not a security sandbox.
    The integration runtime remains responsible for lifecycle events, approvals, isolation,
    and durable orchestration state.
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

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        allowed_executables: Sequence[str | Path],
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
        self._max_timeout_seconds = float(max_timeout_seconds)
        self._environment = MappingProxyType(environment)

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def execute(self, command: ShellCommand) -> ShellExecutionResult:
        if command.timeout_seconds > self._max_timeout_seconds:
            raise ShellCommandValidationError(
                "command timeout exceeds worker max_timeout_seconds"
            )

        cwd = self._resolve_cwd(command.cwd)
        executable = self._resolve_executable(command.argv[0])
        argv = (str(executable), *command.argv[1:])

        try:
            completed = subprocess.run(
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
                timeout=float(command.timeout_seconds),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ShellExecutionResult(
                status=ShellExecutionStatus.TIMED_OUT,
                argv=tuple(command.argv),
                cwd=command.cwd,
                exit_code=None,
                stdout=self._normalize_output(exc.stdout),
                stderr=self._normalize_output(exc.stderr),
                error_code="timeout",
            )
        except OSError as exc:
            return ShellExecutionResult(
                status=ShellExecutionStatus.FAILED,
                argv=tuple(command.argv),
                cwd=command.cwd,
                exit_code=None,
                stdout="",
                stderr=self._normalize_output(str(exc)),
                error_code="spawn_error",
            )

        status = (
            ShellExecutionStatus.SUCCEEDED
            if completed.returncode == 0
            else ShellExecutionStatus.FAILED
        )
        return ShellExecutionResult(
            status=status,
            argv=tuple(command.argv),
            cwd=command.cwd,
            exit_code=completed.returncode,
            stdout=self._normalize_output(completed.stdout),
            stderr=self._normalize_output(completed.stderr),
            error_code=None if completed.returncode == 0 else "nonzero_exit",
        )

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
