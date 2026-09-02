# Current state

Updated: 2026-09-02

## Current objective

Finish and verify the Forge public recovery boundary, then build the first
production-quality ScoreSymphony V1-to-Forge adapter against public Forge
surfaces only.

## Implemented in this branch

- Hermes remains the sole intelligent orchestrator.
- Forge remains the deterministic task, execution, workspace, review, gate, and
  merge authority.
- V1 command submission is separated from terminal command outcomes through
  `CommandReceipt` and terminal `command.*` events.
- Read/query concerns are separated from the command plane.
- Parsed nested contract data is recursively read-only after validation.
- Terminal command events require command causation.
- ADR-0001 accurately describes HTTP/JSON + SSE as the live transport without
  treating the in-memory SSE feed as durable history.
- ADR-0002 is accepted and aligns V1 to verified Forge lifecycle operations.
- `create_task` carries explicit Forge `project_id` scope.
- Task mutations carry the expected Forge task `version`.
- `run_id` and run-oriented commands/events are replaced by Forge
  `execution_id` / execution terminology.
- Commands that would bypass or duplicate Forge workspace, test, review, worker,
  or merge authority are removed from V1.
- Contract fixtures, compatibility checks, semantic rejection tests, and runtime
  tests cover the corrected vocabulary.
- Forge now exposes authenticated historical domain-event reads through
  `/api/v1/events` when `after_sequence` or `limit` is supplied, backed by
  `DomainEventRepo::list_events_after`.
- Historical event query/response DTOs are public `api-types` contracts with
  generated TypeScript bindings instead of route-private types.
- Historical read tests cover authentication, beginning/middle/end cursors,
  empty results, strict ordering, limits, invalid input, and concurrent
  append/read behavior.
- Calling `/api/v1/events` without historical query parameters retains the live
  broadcast SSE behavior, including `events.resync_required` on lag.
- The deterministic shell reference worker core exists independently; it is not
  yet wired into the Forge lifecycle end to end.
- Baseline validation, Pytest, packaging checks, and GitHub Actions definitions
  remain present.

## Verified integration facts

- Forge task creation is project-scoped.
- Forge task updates and task actions support optimistic concurrency.
- Forge owns task start/dispatch, workspace creation, review/gates, and merge.
- Forge execution retry/cancel has public execution endpoints.
- Forge live events include task, workspace, execution, review, and merge
  lifecycle information that can be normalized into V1.
- Forge `/api/v1/events` is a broadcast SSE stream and signals
  `events.resync_required` on lag.
- Forge persists ordered domain events and exposes authenticated cursor-based
  historical reads without requiring a client to access Forge database
  internals.

## Not implemented yet

- Running ScoreSymphony command HTTP endpoint and V1 SSE projection adapter.
- Forge V1 command/event adapter against public Forge surfaces.
- Durable command idempotency integration against Forge-owned state/events.
- Hermes-side V1 tools/adapter.
- Shell-worker integration into the complete Hermes-to-Forge lifecycle.
- Production authentication/authorization design beyond existing Forge auth.
- Deployment, Control Plane, agent registry, managed externals, specialist
  agents, and KVM placement.

## Next work package

Build the Forge adapter against the corrected V1 contract and public Forge
surfaces only:

1. map each supported V1 command to the corresponding public Forge operation;
2. carry project/task/execution identifiers, task versions, correlation and
   causation metadata correctly;
3. normalize Forge lifecycle/domain events into stable V1 events;
4. project optimistic-concurrency and other Forge failures into deterministic
   V1 rejections/failures;
5. add durable command-idempotency behavior without creating a second lifecycle
   authority;
6. test the adapter independently before wiring the HTTP/SSE runtime and Hermes.

## Blockers

The historical recovery surface is implemented at the code/contract level and
is no longer the architectural blocker for starting the Forge adapter. The
current top-level GitHub quality workflow validates the Python platform baseline
but does not compile or execute the nested Forge Rust test suite, so the recovery
change must not be treated as release-verified or merged from this follow-up
branch until the relevant Forge Rust tests/build checks have passed.
