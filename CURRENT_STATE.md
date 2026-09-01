# Current state

Updated: 2026-09-02

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
- Parsed nested JSON data is recursively read-only after validation.
- Central validation returns deterministic structured rejections for unknown
  versions, missing fields, malformed identifiers, invalid timestamps, and
  invalid command/event states.
- Command submission is separated from terminal execution: submission returns
  an ingress `CommandReceipt`, while terminal truth is represented by durable
  command outcome events.
- Read/query concerns are not encoded as V1 command kinds.
- Terminal command events require `causation_id` to identify their command.
- Separate command-submission and event-read ports are present, with a
  composite integration protocol for adapters.
- ADR-0001 selects loopback HTTP/JSON with an SSE return path for the first
  adapter slice based on the pinned Forge and Hermes code.
- Baseline validation, tests, and a CI workflow are present.
- A read-only upstream update checker is present.

## Not implemented yet

- Running HTTP/SSE transport and both Hermes/Forge adapters.
- Shared task/run/event persistence across both engines.
- Resource/status query contracts beyond cursor-based event reads.
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
- Submission receipts only report ingress state and never impersonate terminal
  command completion.
- V1 commands map to stable Forge operations without importing Forge internals
  into Hermes.
- Forge remains authoritative for task, run, worktree, review, and merge state.
- Durable Forge events project to V1 events with cursor-based resynchronization.
- Terminal command events preserve command causation.
- Adapter acceptance, duplicate detection, rejection, failure, malformed input,
  and reconnect/replay behavior are covered by automated tests.
- The complete sequence is covered by an automated end-to-end test.

## Blockers

None for the baseline. Production authentication and exact transport selection
must be decided before exposing the integration beyond localhost.
