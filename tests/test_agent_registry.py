from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scoresymphony_control.agent_registry import (
    AgentAlreadyRegisteredError,
    AgentHealth,
    AgentHealthCheck,
    AgentManifest,
    AgentNotFoundError,
    AgentOrigin,
    AgentQuery,
    AgentRegistry,
    AgentRegistryFormatError,
    AgentRevisionConflictError,
    AgentSecurityProfile,
    BackendProfile,
    HealthCheckKind,
    JsonAgentRegistryStore,
    ResourceProfile,
    agent_manifest_to_dict,
    parse_agent_manifest,
)


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def manifest(
    agent_id: str = "worker.local",
    *,
    origin: AgentOrigin = AgentOrigin.LOCAL,
    endpoint: str | None = None,
    capabilities: tuple[str, ...] = ("shell",),
    tools: tuple[str, ...] = ("git",),
    task_classes: tuple[str, ...] = ("coding",),
) -> AgentManifest:
    return AgentManifest(
        agent_id=agent_id,
        display_name=agent_id,
        version="1.2.3",
        origin=origin,
        endpoint=endpoint,
        capabilities=frozenset(capabilities),
        tools=frozenset(tools),
        backend=BackendProfile("deterministic"),
        resources=ResourceProfile(cpu_cores=1.0, memory_mb=512),
        security=AgentSecurityProfile(
            permissions=frozenset({"workspace.write"})
        ),
        health_check=AgentHealthCheck(
            interval_seconds=10,
            stale_after_seconds=30,
        ),
        allowed_task_classes=frozenset(task_classes),
        labels={"pool": "default"},
    )


def test_register_get_update_remove_lifecycle() -> None:
    clock = Clock()
    registry = AgentRegistry(clock=clock)
    record = registry.register(manifest())

    assert record.health is AgentHealth.UNKNOWN
    assert record.revision == 1
    with pytest.raises(AgentAlreadyRegisteredError):
        registry.register(manifest())

    clock.advance(1)
    changed = registry.update_manifest(
        manifest(capabilities=("shell", "python")),
        expected_revision=1,
    )
    assert changed.revision == 2
    assert "python" in changed.manifest.capabilities

    with pytest.raises(AgentRevisionConflictError):
        registry.remove("worker.local", expected_revision=1)
    removed = registry.remove("worker.local", expected_revision=2)
    assert removed.manifest.agent_id == "worker.local"
    with pytest.raises(AgentNotFoundError):
        registry.get("worker.local")


def test_metadata_validation_rejects_invalid_agent_shapes() -> None:
    with pytest.raises(ValueError):
        manifest("UPPER")
    with pytest.raises(ValueError):
        manifest("remote.worker", origin=AgentOrigin.REMOTE)
    with pytest.raises(ValueError):
        AgentHealthCheck(kind=HealthCheckKind.HTTP, endpoint=None)
    with pytest.raises(ValueError):
        ResourceProfile(gpu_required=False, vram_mb=1024)


def test_heartbeat_and_stale_state_tracking() -> None:
    clock = Clock()
    registry = AgentRegistry(clock=clock)
    registry.register(manifest())
    registry.heartbeat("worker.local")

    assert registry.get("worker.local").health is AgentHealth.HEALTHY
    clock.advance(31)
    changed = registry.refresh_stale()

    assert [item.manifest.agent_id for item in changed] == ["worker.local"]
    assert registry.get("worker.local").health is AgentHealth.STALE


def test_invalid_state_is_explicit_and_requires_reason() -> None:
    registry = AgentRegistry(clock=Clock())
    registry.register(manifest())

    with pytest.raises(ValueError):
        registry.set_health("worker.local", AgentHealth.INVALID)

    record = registry.set_health(
        "worker.local",
        AgentHealth.INVALID,
        reason="manifest incompatible with runtime",
    )
    assert record.health is AgentHealth.INVALID
    assert record.health_reason


def test_mixed_local_remote_query_uses_one_registry_source() -> None:
    registry = AgentRegistry(clock=Clock())
    registry.register(
        manifest(
            "local.shell",
            capabilities=("shell", "coding"),
        )
    )
    registry.register(
        manifest(
            "remote.gpu",
            origin=AgentOrigin.REMOTE,
            endpoint="https://gpu.example.invalid/agent",
            capabilities=("coding", "gpu"),
            tools=("python",),
            task_classes=("coding", "inference"),
        )
    )
    registry.heartbeat("local.shell")
    registry.heartbeat("remote.gpu")

    coding = registry.list(
        AgentQuery(
            capabilities=frozenset({"coding"}),
            health=frozenset({AgentHealth.HEALTHY}),
        )
    )
    assert [item.manifest.agent_id for item in coding] == [
        "local.shell",
        "remote.gpu",
    ]

    remote = registry.list(
        AgentQuery(
            origins=frozenset({AgentOrigin.REMOTE}),
            task_classes=frozenset({"inference"}),
        )
    )
    assert [item.manifest.agent_id for item in remote] == ["remote.gpu"]


def test_json_store_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    clock = Clock()
    first = AgentRegistry(JsonAgentRegistryStore(path), clock=clock)
    first.register(
        manifest(
            "remote.gpu",
            origin=AgentOrigin.REMOTE,
            endpoint="https://gpu.example.invalid/agent",
        )
    )
    first.heartbeat(
        "remote.gpu",
        health=AgentHealth.DEGRADED,
        reason="high load",
    )

    second = AgentRegistry(JsonAgentRegistryStore(path), clock=clock)
    loaded = second.get("remote.gpu")

    assert loaded.health is AgentHealth.DEGRADED
    assert loaded.manifest.origin is AgentOrigin.REMOTE
    assert loaded.revision == 2


def test_json_store_rejects_malformed_document(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    path.write_text(
        '{"schema_version":1,"agents":[{"bad":true}]}',
        encoding="utf-8",
    )

    with pytest.raises(AgentRegistryFormatError):
        AgentRegistry(JsonAgentRegistryStore(path))


def test_manifest_serialization_is_versioned_and_strict() -> None:
    payload = agent_manifest_to_dict(manifest())

    assert payload["schema_version"] == 1
    assert parse_agent_manifest(payload) == manifest()

    payload["schema_version"] = "1"
    with pytest.raises(TypeError):
        parse_agent_manifest(payload)


def test_remote_and_local_records_survive_same_persistent_store(
    tmp_path: Path,
) -> None:
    path = tmp_path / "agents.json"
    clock = Clock()
    registry = AgentRegistry(JsonAgentRegistryStore(path), clock=clock)
    registry.register(manifest("local.one"))
    registry.register(
        manifest(
            "remote.one",
            origin=AgentOrigin.REMOTE,
            endpoint="https://remote.invalid",
        )
    )

    restored = AgentRegistry(JsonAgentRegistryStore(path), clock=clock)
    assert [
        (record.manifest.agent_id, record.manifest.origin)
        for record in restored.list()
    ] == [
        ("local.one", AgentOrigin.LOCAL),
        ("remote.one", AgentOrigin.REMOTE),
    ]
