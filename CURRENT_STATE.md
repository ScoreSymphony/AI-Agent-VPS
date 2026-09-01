# Current state

Updated: 2026-09-01

## Current objective

Provide an executable, transport-independent V1 contract runtime as the stable
boundary for later Hermes-Forge adapters.

## Implemented in this baseline

- The repository boundary is fixed to `ScoreSymphony/AI-Agent-VPS`.
- Forge is imported as a pinned MIT source snapshot.
- Hermes Agent is imported from a pinned source snapshot with documented
  non-MIT paths excluded from the vendored core.
- Upstream provenance and third-party notices are recorded.
- Hermes is defined as the sole intelligent orchestrator.
- Forge is defined as the deterministic execution/lifecycle engine.
- Component classes and the first managed-external registry entry are defined.
- Version 1 command and event schemas are present.
- V1 commands and events have frozen, typed executable Python envelopes.
- Central validation returns deterministic structured rejections for unknown
  versions, missing fields, malformed identifiers, invalid timestamps, and
  invalid command/event states.
- Command results distinguish success, deterministic rejection, and execution
  failure.
- A transport-independent adapter protocol is present.
- ADR-0001 selects loopback HTTP/JSON with an SSE return path for the first
  adapter slice based on the pinned Forge and Hermes code.
- Baseline validation, tests, and a CI workflow are present.
- A read-only upstream update checker is present.

## Not implemented yet

- Running HTTP/SSE transport and both Hermes/Forge adapters.
- Shared task/run/event persistence across both engines.
- The minimal shell-worker vertical slice.
- Integrated authentication and authorization.
- Production deployment and reverse proxy configuration.
- ScoreSymphony dashboard extensions.
- Managed-external installation and removal.
- Qwen Code installation or model configuration.
- Research, file, infrastructure, monitoring, and deployment agents.
- KVM 4/KVM 8 placement.

## Next work package

Implement the smallest Forge adapter and loopback HTTP/SSE boundary against
`platform/contracts/v1`, without adding Hermes orchestration behavior.

## Acceptance criteria for the next work package

- The HTTP listener binds to loopback and accepts only validated V1 commands.
- V1 commands map to stable Forge operations without importing Forge internals
  into Hermes.
- Forge remains authoritative for task, run, worktree, review, and merge state.
- Durable Forge events project to V1 events with cursor-based resynchronization.
- Adapter success, rejection, failure, duplicate delivery, and malformed input
  are covered by automated tests.
- The complete sequence is covered by an automated end-to-end test.

## Blockers

None for the baseline. Production authentication and exact transport selection
must be decided before exposing the integration beyond localhost.
