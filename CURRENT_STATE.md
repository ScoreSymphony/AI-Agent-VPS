# Current state

Updated: 2026-09-02

## Current objective

Build the first production-quality ScoreSymphony-to-Forge adapter and integrated
kernel on top of the verified V1 boundary, authenticated Forge historical event
recovery, the deterministic shell-worker acceptance surface, and the shared
security contracts without changing Forge lifecycle ownership.

## Implemented on main

- Hermes remains the sole intelligent orchestrator.
- Forge remains the deterministic task, execution, workspace, review, gate, and
  merge authority.
- V1 command submission is separated from terminal command outcomes through
  `CommandReceipt` and terminal `command.*` events.
- Read/query concerns are separated from the command plane.
- Parsed nested contract data is recursively read-only after validation.
- Terminal command events require command causation.
- ADR-0001 accurately describes HTTP/JSON + SSE as the live transport.
- ADR-0002 is accepted and aligns V1 to verified Forge lifecycle operations.
- `create_task` carries explicit Forge `project_id` scope.
- Task mutations carry the expected Forge task `version`.
- `run_id` and run-oriented commands/events are replaced by Forge
  `execution_id` / execution terminology.
- Commands that would bypass or duplicate Forge workspace, test, review, worker,
  or merge authority are removed from V1.
- Contract fixtures, compatibility checks, semantic rejection tests, and runtime
  tests cover the corrected vocabulary.
- Forge exposes authenticated historical domain-event recovery through
  `/api/v1/events` historical-read mode using stable public query/response DTOs,
  an exclusive `after_sequence` cursor, bounded limits, deterministic invalid
  input handling, and ordered reads backed by `DomainEventRepo`.
- Historical event recovery is covered for authentication, beginning/middle/end
  cursors, empty results, ordering, limits, invalid input, and concurrent
  append/read behavior.
- Existing `/api/v1/events` live SSE behavior remains unchanged when historical
  query parameters are absent, including `events.resync_required` signaling.
- Historical recovery behavior is documented in Forge and exported through
  generated TypeScript client types.
- The transport-neutral deterministic shell-worker reference implementation now
  covers predictable fixture changes, write-path policy evidence, success,
  failure, timeout, cancellation, and explicit retry attempts without an LLM.
- Shell-worker timeout/cancel collection remains deadline-bounded when a direct
  parent exits while descendants retain inherited pipes; POSIX invocations use
  a dedicated process group for bounded termination.
- Workspace write-policy evidence includes relevant file-mode changes, so a
  mode-only mutation such as an executable-bit change cannot bypass the
  declared-write-path check.
- Baseline validation, Pytest, packaging checks, Forge Rust checks, and GitHub
  Actions definitions remain present.

## Verified integration facts

- Forge task creation is project-scoped.
- Forge task updates and task actions support optimistic concurrency.
- Forge owns task start/dispatch, workspace creation, review/gates, and merge.
- Forge execution retry/cancel has public execution endpoints.
- Forge live events include task, workspace, execution, review, and merge
  lifecycle information that can be normalized into V1.
- Forge `/api/v1/events` provides both the existing live broadcast SSE stream
  and an authenticated historical JSON read mode selected by recovery query
  parameters.
- Forge persists ordered domain events and exposes them through the public
  recovery boundary; ScoreSymphony consumers do not need direct Forge database
  access.

## Not implemented yet

- Running ScoreSymphony command HTTP endpoint and SSE projection adapter.
- Production-quality Forge adapter for the complete V1 command/event surface.
- Durable command idempotency integration against Forge-owned state/events.
- Hermes-side V1 tools/adapter.
- Forge-integrated shell-worker end-to-end vertical slice.
- Full production authentication/authorization, policy, and approval behavior
  across the integrated ScoreSymphony runtime.
- Reproducible production-like deployment, observability, and operational
  runbooks for the integrated runtime.
- Control Plane, agent registry, resource scheduling, managed externals,
  specialist agents, and configurable KVM/worker placement.

## Next work package

Implement the production-quality Forge adapter and transport runtime against the
corrected V1 contract and public Forge surfaces only:

1. map every supported V1 command to the corresponding public Forge operation;
2. preserve `project_id`, `task_id`, `execution_id`, expected task `version`,
   `correlation_id`, and command causation across the boundary;
3. normalize Forge task, workspace, execution, review, gate, merge, and recovery
   events into stable V1 events;
4. project Forge conflicts and rejections deterministically without creating a
   second lifecycle authority;
5. implement the loopback ScoreSymphony command HTTP endpoint and live SSE
   projection;
6. use authenticated historical event reads for reconnect/catch-up and make the
   transition back to live SSE race-safe;
7. integrate durable duplicate-command handling against Forge-owned truth;
8. prove the adapter with the deterministic shell-worker through an end-to-end
   vertical slice before adding LLM-worker uncertainty.

Hermes-side tools can be prepared in parallel against the frozen V1 contract,
but they must consume the same adapter/runtime boundary rather than importing
Forge internals.

## Blockers

Historical Forge event recovery is no longer a blocker. The critical path is
now the production Forge adapter plus HTTP/SSE transport integration and its
end-to-end proof against the deterministic shell worker. Changes must continue
to preserve Forge as the sole lifecycle authority and must not be merged without
the repository's required CI gates passing.
