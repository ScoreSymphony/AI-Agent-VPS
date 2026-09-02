"""Versioned agent manifests and the control-plane agent registry."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Callable, Iterable, Mapping, Protocol


AGENT_MANIFEST_SCHEMA_VERSION = 1
AGENT_REGISTRY_SCHEMA_VERSION = 1
_AGENT_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")


class AgentOrigin(StrEnum):
    LOCAL = "local"
    REMOTE = "remote"


class AgentHealth(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STALE = "stale"
    INVALID = "invalid"
    DISABLED = "disabled"


class HealthCheckKind(StrEnum):
    HEARTBEAT = "heartbeat"
    HTTP = "http"
    PROCESS = "process"


class AgentRegistryError(RuntimeError):
    """Base error for controlled registry lifecycle operations."""


class AgentAlreadyRegisteredError(AgentRegistryError):
    pass


class AgentNotFoundError(AgentRegistryError):
    pass


class AgentRevisionConflictError(AgentRegistryError):
    pass


class AgentRegistryFormatError(AgentRegistryError):
    pass


@dataclass(frozen=True, slots=True)
class BackendProfile:
    backend_class: str
    model: str | None = None
    provider: str | None = None

    def __post_init__(self) -> None:
        _require_token(self.backend_class, "backend_class")
        if self.model is not None:
            _require_nonempty(self.model, "model")
        if self.provider is not None:
            _require_nonempty(self.provider, "provider")


@dataclass(frozen=True, slots=True)
class ResourceProfile:
    cpu_cores: float = 1.0
    memory_mb: int = 512
    gpu_required: bool = False
    vram_mb: int = 0

    def __post_init__(self) -> None:
        if self.cpu_cores <= 0:
            raise ValueError("cpu_cores must be positive")
        if self.memory_mb < 1:
            raise ValueError("memory_mb must be positive")
        if self.vram_mb < 0:
            raise ValueError("vram_mb must not be negative")
        if not self.gpu_required and self.vram_mb:
            raise ValueError("vram_mb requires gpu_required=true")


@dataclass(frozen=True, slots=True)
class AgentSecurityProfile:
    trust_level: str = "restricted"
    permissions: frozenset[str] = field(default_factory=frozenset)
    network_access: bool = False

    def __post_init__(self) -> None:
        _require_token(self.trust_level, "trust_level")
        object.__setattr__(self, "permissions", _tokens(self.permissions, "permissions"))


@dataclass(frozen=True, slots=True)
class AgentHealthCheck:
    kind: HealthCheckKind = HealthCheckKind.HEARTBEAT
    interval_seconds: int = 30
    stale_after_seconds: int = 120
    endpoint: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", HealthCheckKind(self.kind))
        if self.interval_seconds < 1:
            raise ValueError("interval_seconds must be positive")
        if self.stale_after_seconds < self.interval_seconds:
            raise ValueError("stale_after_seconds must be >= interval_seconds")
        if self.kind is HealthCheckKind.HTTP:
            if not self.endpoint or not self.endpoint.strip():
                raise ValueError("HTTP health checks require an endpoint")
        elif self.endpoint is not None:
            raise ValueError("endpoint is only valid for HTTP health checks")


@dataclass(frozen=True, slots=True)
class AgentManifest:
    agent_id: str
    display_name: str
    version: str
    origin: AgentOrigin
    capabilities: frozenset[str]
    tools: frozenset[str]
    backend: BackendProfile
    resources: ResourceProfile
    security: AgentSecurityProfile
    health_check: AgentHealthCheck
    allowed_task_classes: frozenset[str]
    endpoint: str | None = None
    labels: Mapping[str, str] = field(default_factory=dict, hash=False)
    schema_version: int = AGENT_MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "origin", AgentOrigin(self.origin))
        if self.schema_version != AGENT_MANIFEST_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported agent manifest schema_version: {self.schema_version}"
            )
        if not _AGENT_ID_RE.fullmatch(self.agent_id):
            raise ValueError(
                "agent_id must be 1-64 lowercase characters using letters, digits, '.', '_' or '-'"
            )
        _require_nonempty(self.display_name, "display_name")
        _require_token(self.version, "version")
        object.__setattr__(
            self,
            "capabilities",
            _tokens(self.capabilities, "capabilities", required=True),
        )
        object.__setattr__(self, "tools", _tokens(self.tools, "tools"))
        object.__setattr__(
            self,
            "allowed_task_classes",
            _tokens(self.allowed_task_classes, "allowed_task_classes", required=True),
        )
        if self.origin is AgentOrigin.REMOTE:
            if not self.endpoint or not self.endpoint.strip():
                raise ValueError("remote agents require an endpoint")
        elif self.endpoint is not None:
            raise ValueError("local agents must not declare a remote endpoint")
        labels = dict(self.labels)
        for key, value in labels.items():
            _require_token(key, "label key")
            _require_nonempty(value, f"label {key!r}")
        object.__setattr__(self, "labels", MappingProxyType(labels))


@dataclass(frozen=True, slots=True)
class AgentRecord:
    manifest: AgentManifest
    health: AgentHealth
    registered_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None = None
    health_reason: str | None = None
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "health", AgentHealth(self.health))
        _require_aware(self.registered_at, "registered_at")
        _require_aware(self.updated_at, "updated_at")
        if self.last_seen_at is not None:
            _require_aware(self.last_seen_at, "last_seen_at")
        if self.updated_at < self.registered_at:
            raise ValueError("updated_at must not precede registered_at")
        if self.last_seen_at is not None and self.last_seen_at < self.registered_at:
            raise ValueError("last_seen_at must not precede registered_at")
        if self.revision < 1:
            raise ValueError("revision must be positive")
        if self.health is AgentHealth.INVALID and not self.health_reason:
            raise ValueError("invalid agents require health_reason")


@dataclass(frozen=True, slots=True)
class AgentQuery:
    capabilities: frozenset[str] = field(default_factory=frozenset)
    tools: frozenset[str] = field(default_factory=frozenset)
    task_classes: frozenset[str] = field(default_factory=frozenset)
    origins: frozenset[AgentOrigin] = field(default_factory=frozenset)
    health: frozenset[AgentHealth] = field(default_factory=frozenset)
    labels: Mapping[str, str] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capabilities", _tokens(self.capabilities, "capabilities"))
        object.__setattr__(self, "tools", _tokens(self.tools, "tools"))
        object.__setattr__(self, "task_classes", _tokens(self.task_classes, "task_classes"))
        object.__setattr__(
            self,
            "origins",
            frozenset(AgentOrigin(item) for item in self.origins),
        )
        object.__setattr__(
            self,
            "health",
            frozenset(AgentHealth(item) for item in self.health),
        )
        object.__setattr__(self, "labels", MappingProxyType(dict(self.labels)))


class AgentRegistryStore(Protocol):
    def load(self) -> tuple[AgentRecord, ...]: ...

    def save(self, records: Iterable[AgentRecord]) -> None: ...


class InMemoryAgentRegistryStore:
    def __init__(self, records: Iterable[AgentRecord] = ()) -> None:
        self._records = tuple(records)

    def load(self) -> tuple[AgentRecord, ...]:
        return self._records

    def save(self, records: Iterable[AgentRecord]) -> None:
        self._records = tuple(records)


class JsonAgentRegistryStore:
    """Atomic JSON persistence for control-plane agent metadata/state.

    The path is runtime configuration; registry data itself is not repository
    source data and must not be committed to the monorepo.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> tuple[AgentRecord, ...]:
        if not self.path.exists():
            return ()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AgentRegistryFormatError(
                f"cannot read agent registry: {self.path}"
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != AGENT_REGISTRY_SCHEMA_VERSION
        ):
            raise AgentRegistryFormatError(
                "unsupported or malformed agent registry document"
            )
        raw_agents = payload.get("agents")
        if not isinstance(raw_agents, list):
            raise AgentRegistryFormatError("agent registry 'agents' must be a list")
        try:
            records = tuple(parse_agent_record(item) for item in raw_agents)
        except (KeyError, TypeError, ValueError) as exc:
            raise AgentRegistryFormatError(
                "agent registry contains an invalid record"
            ) from exc
        ids = [record.manifest.agent_id for record in records]
        if len(ids) != len(set(ids)):
            raise AgentRegistryFormatError(
                "agent registry contains duplicate agent ids"
            )
        return records

    def save(self, records: Iterable[AgentRecord]) -> None:
        payload = {
            "schema_version": AGENT_REGISTRY_SCHEMA_VERSION,
            "agents": [
                agent_record_to_dict(record)
                for record in sorted(
                    records,
                    key=lambda item: item.manifest.agent_id,
                )
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        except BaseException:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise


class AgentRegistry:
    """Thread-safe source of truth for registered execution-capable agents."""

    def __init__(
        self,
        store: AgentRegistryStore | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store or InMemoryAgentRegistryStore()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        records = self._store.load()
        self._records = {
            record.manifest.agent_id: record for record in records
        }
        if len(self._records) != len(records):
            raise AgentRegistryFormatError(
                "agent registry contains duplicate agent ids"
            )

    def register(self, manifest: AgentManifest) -> AgentRecord:
        now = self._now()
        with self._lock:
            if manifest.agent_id in self._records:
                raise AgentAlreadyRegisteredError(manifest.agent_id)
            record = AgentRecord(
                manifest=manifest,
                health=AgentHealth.UNKNOWN,
                registered_at=now,
                updated_at=now,
            )
            self._records[manifest.agent_id] = record
            try:
                self._persist()
            except BaseException:
                del self._records[manifest.agent_id]
                raise
            return record

    def get(self, agent_id: str) -> AgentRecord:
        with self._lock:
            return self._require(agent_id)

    def list(self, query: AgentQuery | None = None) -> tuple[AgentRecord, ...]:
        query = query or AgentQuery()
        with self._lock:
            return tuple(
                record
                for _, record in sorted(self._records.items())
                if _matches(record, query)
            )

    def update_manifest(
        self,
        manifest: AgentManifest,
        *,
        expected_revision: int | None = None,
    ) -> AgentRecord:
        now = self._now()
        with self._lock:
            current = self._require(manifest.agent_id)
            self._require_revision(current, expected_revision)
            replacement = replace(
                current,
                manifest=manifest,
                updated_at=now,
                revision=current.revision + 1,
            )
            self._records[manifest.agent_id] = replacement
            try:
                self._persist()
            except BaseException:
                self._records[manifest.agent_id] = current
                raise
            return replacement

    def heartbeat(
        self,
        agent_id: str,
        *,
        health: AgentHealth = AgentHealth.HEALTHY,
        reason: str | None = None,
    ) -> AgentRecord:
        if health in {
            AgentHealth.STALE,
            AgentHealth.INVALID,
            AgentHealth.DISABLED,
        }:
            raise ValueError(
                "heartbeat health must describe an observed runtime state"
            )
        now = self._now()
        with self._lock:
            current = self._require(agent_id)
            replacement = replace(
                current,
                health=health,
                last_seen_at=now,
                updated_at=now,
                health_reason=reason,
                revision=current.revision + 1,
            )
            self._records[agent_id] = replacement
            try:
                self._persist()
            except BaseException:
                self._records[agent_id] = current
                raise
            return replacement

    def set_health(
        self,
        agent_id: str,
        health: AgentHealth,
        *,
        reason: str | None = None,
        expected_revision: int | None = None,
    ) -> AgentRecord:
        if health is AgentHealth.INVALID and not reason:
            raise ValueError("invalid agents require a reason")
        now = self._now()
        with self._lock:
            current = self._require(agent_id)
            self._require_revision(current, expected_revision)
            replacement = replace(
                current,
                health=health,
                updated_at=now,
                health_reason=reason,
                revision=current.revision + 1,
            )
            self._records[agent_id] = replacement
            try:
                self._persist()
            except BaseException:
                self._records[agent_id] = current
                raise
            return replacement

    def refresh_stale(self) -> tuple[AgentRecord, ...]:
        now = self._now()
        changed: list[AgentRecord] = []
        with self._lock:
            for agent_id, current in tuple(self._records.items()):
                if current.health in {
                    AgentHealth.INVALID,
                    AgentHealth.DISABLED,
                    AgentHealth.STALE,
                }:
                    continue
                reference = current.last_seen_at or current.registered_at
                age = (now - reference).total_seconds()
                if age <= current.manifest.health_check.stale_after_seconds:
                    continue
                replacement = replace(
                    current,
                    health=AgentHealth.STALE,
                    updated_at=now,
                    health_reason=(
                        "health observation exceeded stale_after_seconds"
                    ),
                    revision=current.revision + 1,
                )
                self._records[agent_id] = replacement
                changed.append(replacement)
            if changed:
                try:
                    self._persist()
                except BaseException:
                    self._records = {
                        item.manifest.agent_id: item
                        for item in self._store.load()
                    }
                    raise
        return tuple(changed)

    def remove(
        self,
        agent_id: str,
        *,
        expected_revision: int | None = None,
    ) -> AgentRecord:
        with self._lock:
            current = self._require(agent_id)
            self._require_revision(current, expected_revision)
            del self._records[agent_id]
            try:
                self._persist()
            except BaseException:
                self._records[agent_id] = current
                raise
            return current

    def _require(self, agent_id: str) -> AgentRecord:
        try:
            return self._records[agent_id]
        except KeyError:
            raise AgentNotFoundError(agent_id) from None

    @staticmethod
    def _require_revision(
        current: AgentRecord,
        expected_revision: int | None,
    ) -> None:
        if (
            expected_revision is not None
            and current.revision != expected_revision
        ):
            raise AgentRevisionConflictError(
                f"agent {current.manifest.agent_id!r} is revision "
                f"{current.revision}, expected {expected_revision}"
            )

    def _persist(self) -> None:
        self._store.save(self._records.values())

    def _now(self) -> datetime:
        value = self._clock()
        _require_aware(value, "clock result")
        return value


def _matches(record: AgentRecord, query: AgentQuery) -> bool:
    manifest = record.manifest
    return (
        query.capabilities.issubset(manifest.capabilities)
        and query.tools.issubset(manifest.tools)
        and query.task_classes.issubset(manifest.allowed_task_classes)
        and (not query.origins or manifest.origin in query.origins)
        and (not query.health or record.health in query.health)
        and all(
            manifest.labels.get(key) == value
            for key, value in query.labels.items()
        )
    )


def agent_manifest_to_dict(manifest: AgentManifest) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "agent_id": manifest.agent_id,
        "display_name": manifest.display_name,
        "version": manifest.version,
        "origin": manifest.origin.value,
        "endpoint": manifest.endpoint,
        "capabilities": sorted(manifest.capabilities),
        "tools": sorted(manifest.tools),
        "backend": {
            "backend_class": manifest.backend.backend_class,
            "model": manifest.backend.model,
            "provider": manifest.backend.provider,
        },
        "resources": {
            "cpu_cores": manifest.resources.cpu_cores,
            "memory_mb": manifest.resources.memory_mb,
            "gpu_required": manifest.resources.gpu_required,
            "vram_mb": manifest.resources.vram_mb,
        },
        "security": {
            "trust_level": manifest.security.trust_level,
            "permissions": sorted(manifest.security.permissions),
            "network_access": manifest.security.network_access,
        },
        "health_check": {
            "kind": manifest.health_check.kind.value,
            "interval_seconds": manifest.health_check.interval_seconds,
            "stale_after_seconds": (
                manifest.health_check.stale_after_seconds
            ),
            "endpoint": manifest.health_check.endpoint,
        },
        "allowed_task_classes": sorted(manifest.allowed_task_classes),
        "labels": dict(manifest.labels),
    }


def parse_agent_manifest(value: object) -> AgentManifest:
    if not isinstance(value, dict):
        raise TypeError("manifest must be an object")
    backend = _mapping(value["backend"], "backend")
    resources = _mapping(value["resources"], "resources")
    security = _mapping(value["security"], "security")
    health_check = _mapping(value["health_check"], "health_check")
    labels = _mapping(value.get("labels", {}), "labels")
    return AgentManifest(
        schema_version=_integer(value["schema_version"], "schema_version"),
        agent_id=_string(value["agent_id"], "agent_id"),
        display_name=_string(value["display_name"], "display_name"),
        version=_string(value["version"], "version"),
        origin=AgentOrigin(_string(value["origin"], "origin")),
        endpoint=_optional_str(value.get("endpoint")),
        capabilities=frozenset(
            _string_list(value["capabilities"], "capabilities")
        ),
        tools=frozenset(_string_list(value["tools"], "tools")),
        backend=BackendProfile(
            backend_class=_string(
                backend["backend_class"],
                "backend.backend_class",
            ),
            model=_optional_str(backend.get("model")),
            provider=_optional_str(backend.get("provider")),
        ),
        resources=ResourceProfile(
            cpu_cores=_number(
                resources["cpu_cores"],
                "resources.cpu_cores",
            ),
            memory_mb=_integer(
                resources["memory_mb"],
                "resources.memory_mb",
            ),
            gpu_required=_bool(
                resources["gpu_required"],
                "resources.gpu_required",
            ),
            vram_mb=_integer(
                resources["vram_mb"],
                "resources.vram_mb",
            ),
        ),
        security=AgentSecurityProfile(
            trust_level=_string(
                security["trust_level"],
                "security.trust_level",
            ),
            permissions=frozenset(
                _string_list(
                    security["permissions"],
                    "security.permissions",
                )
            ),
            network_access=_bool(
                security["network_access"],
                "security.network_access",
            ),
        ),
        health_check=AgentHealthCheck(
            kind=HealthCheckKind(
                _string(health_check["kind"], "health_check.kind")
            ),
            interval_seconds=_integer(
                health_check["interval_seconds"],
                "health_check.interval_seconds",
            ),
            stale_after_seconds=_integer(
                health_check["stale_after_seconds"],
                "health_check.stale_after_seconds",
            ),
            endpoint=_optional_str(health_check.get("endpoint")),
        ),
        allowed_task_classes=frozenset(
            _string_list(
                value["allowed_task_classes"],
                "allowed_task_classes",
            )
        ),
        labels={
            _string(key, "label key"): _string(item, f"label {key!r}")
            for key, item in labels.items()
        },
    )


def agent_record_to_dict(record: AgentRecord) -> dict[str, object]:
    return {
        "manifest": agent_manifest_to_dict(record.manifest),
        "health": record.health.value,
        "registered_at": record.registered_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "last_seen_at": (
            record.last_seen_at.isoformat()
            if record.last_seen_at
            else None
        ),
        "health_reason": record.health_reason,
        "revision": record.revision,
    }


def parse_agent_record(value: object) -> AgentRecord:
    if not isinstance(value, dict):
        raise TypeError("agent record must be an object")
    return AgentRecord(
        manifest=parse_agent_manifest(value["manifest"]),
        health=AgentHealth(_string(value["health"], "health")),
        registered_at=_datetime(
            value["registered_at"],
            "registered_at",
        ),
        updated_at=_datetime(value["updated_at"], "updated_at"),
        last_seen_at=(
            _datetime(value["last_seen_at"], "last_seen_at")
            if value.get("last_seen_at") is not None
            else None
        ),
        health_reason=_optional_str(value.get("health_reason")),
        revision=_integer(value["revision"], "revision"),
    )


def _mapping(value: object, name: str) -> Mapping[object, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    return value


def _string_list(value: object, name: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not all(isinstance(item, str) for item in value)
    ):
        raise TypeError(f"{name} must be a list of strings")
    return tuple(value)


def _bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
    return value


def _datetime(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be an ISO-8601 string")
    parsed = datetime.fromisoformat(value)
    _require_aware(parsed, name)
    return parsed


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    return float(value)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("optional string field must be a string or null")
    return value


def _tokens(
    values: Iterable[str],
    name: str,
    *,
    required: bool = False,
) -> frozenset[str]:
    result = frozenset(values)
    if required and not result:
        raise ValueError(f"{name} must not be empty")
    for value in result:
        _require_token(value, name)
    return result


def _require_token(value: str, name: str) -> None:
    _require_nonempty(value, name)
    if value != value.strip() or any(character.isspace() for character in value):
        raise ValueError(f"{name} entries must not contain whitespace")


def _require_nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
