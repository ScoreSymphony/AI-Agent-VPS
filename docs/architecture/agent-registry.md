# Agent Registry

Status: implemented foundation for the Controlled Multi-Agent milestone.

## Purpose

The Agent Registry is the control-plane source of truth for **which execution-capable agents exist and what they declare they can do**. It does not own task, execution, workspace, review, gate or merge lifecycle state; those remain Forge-owned according to `ARCHITECTURE.md`.

The registry must be consumed by later scheduler/router, Admin API and dashboard work instead of inferring agent availability from running processes.

## Versioned manifest

Manifest schema version `1` declares:

- stable `agent_id` and display name;
- agent implementation `version`;
- local or remote origin plus remote endpoint when applicable;
- capabilities and tools;
- backend/model/provider profile;
- CPU, memory and optional GPU/VRAM requirements;
- security trust level, permissions and network-access declaration;
- health-check policy;
- allowed task classes;
- arbitrary string labels for placement/querying.

Unknown manifest schema versions are rejected. Parsing is type-strict so malformed persisted metadata cannot silently become a valid agent declaration.

## Registry lifecycle

`AgentRegistry` provides the controlled lifecycle:

1. `register()` creates a unique agent record in `unknown` health state.
2. `update_manifest()` changes declared metadata while preserving identity and increments the optimistic revision.
3. `heartbeat()` records an observation and runtime health.
4. `set_health()` represents operator/control-plane states such as `invalid` or `disabled`.
5. `refresh_stale()` marks agents stale when their declared health window is exceeded.
6. `list(AgentQuery(...))` filters the same registry by capabilities, tools, task classes, origin, health and labels.
7. `remove()` unregisters an agent with optional revision checking.

Every mutation increments a per-agent revision. Callers can supply `expected_revision` for update/remove/explicit health transitions to reject stale control-plane writes.

## Persistence

Two stores are provided:

- `InMemoryAgentRegistryStore` for tests and ephemeral process use;
- `JsonAgentRegistryStore` for a single-writer control-plane process.

The JSON store uses registry document schema version `1` and atomic temporary-file replacement. Its configured file is **mutable runtime data and must not be committed to the repository**.

A later distributed control plane may replace the store through the `AgentRegistryStore` protocol without changing the manifest or registry lifecycle API. Multi-process/distributed locking is intentionally not invented in this issue; a shared database-backed store should provide that when the platform actually needs multiple writers.

## Authority boundary

The registry describes and tracks agents; it does not dispatch work itself.

```text
Hermes decides required capability
        |
        v
Scheduler / Router queries Agent Registry
        |
        v
Forge remains lifecycle + dispatch authority
        |
        v
Selected bounded worker executes assignment
```

This keeps one registry source for agent metadata while preserving the existing rule that Hermes and the gateway must not bypass Forge-owned execution lifecycle and worker dispatch.
