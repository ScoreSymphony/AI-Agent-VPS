# Current state

Updated: 2026-09-02

## Current objective

Finish the verified V1 boundary and provide the minimum Forge public recovery
surface required before the first production-quality Hermes-Forge adapter.

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
  claiming the current SSE feed already provides durable historical replay.
- ADR-0002 is accepted and aligns V1 to verified Forge lifecycle operations.
- `create_task` carries explicit Forge `project_id` scope.
- Task mutations carry the expected Forge task `version`.
- `run_id` and run-oriented commands/events are replaced by Forge
  `execution_id` / execution terminology.
- Commands that would bypass or duplicate Forge workspace, test, review, worker,
  or merge authority are removed from V1.
- Contract fixtures, compatibility checks, semantic rejection tests, and runtime
  tests cover the corrected vocabulary.
- The transport-neutral deterministic shell-worker reference implementation now
  covers predictable fixture changes, write-path policy evidence, success,
  failure, timeout, cancellation, and explicit retry attempts without an LLM.
- Shell-worker timeout/cancel collection remains deadline-bounded when a direct
  parent exits while descendants retain inherited pipes; POSIX invocations use
  a dedicated process group for bounded termination.
- Workspace write-policy evidence includes relevant file-mode changes, so a
  mode-only mutation such as an executable-bit change cannot bypass the
  declared-write-path check.
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
- Forge internally persists ordered domain events and consumer cursors, but no
  equivalent public historical cursor-read endpoint exists yet.

## Not implemented yet

- Authenticated public Forge historical domain-event read/recovery endpoint.
- Running ScoreSymphony command HTTP endpoint and SSE projection adapter.
- Durable command idempotency integration against Forge-owned state/events.
- Hermes-side V1 tools/adapter.
- Forge-integrated shell-worker end-to-end vertical slice.
- Production authentication/authorization design beyond existing Forge auth.
- Deployment, Control Plane, agent registry, managed externals, specialist
  agents, and KVM placement.

## Next work package

Add the smallest authenticated Forge public API surface that can read ordered
persisted domain events after a sequence cursor. Follow the nested Forge rules:

1. define stable API response/query types;
2. implement a read-only authenticated route backed by `DomainEventRepo`;
3. cover ordering, cursor, limit, authentication, and empty-result behavior;
4. document the endpoint in Forge API docs and changelog;
5. update generated TypeScript types if the public DTO is exported;
6. keep existing live `/api/v1/events` SSE behavior unchanged.

After that endpoint is proven, implement the ScoreSymphony adapter against the
corrected V1 contract and the public Forge surfaces only.

## Blockers

The V1-to-Forge command mapping is no longer a blocker. Production-grade event
recovery remains blocked until the selected authenticated historical read
surface is implemented and tested. The PR must not be merged without a full
repository CI pass.
