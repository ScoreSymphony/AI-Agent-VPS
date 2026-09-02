# Current state

Updated: 2026-09-02

## Current objective

Build the first production-quality ScoreSymphony-to-Forge adapter and integrated
kernel on top of the verified V1 boundary, authenticated Forge historical event
recovery, the deterministic shell-worker acceptance surface, and the shared
security contracts without changing Forge lifecycle ownership.

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
- Forge exposes an authenticated historical JSON read on `/api/v1/events` with
  exclusive cursor, bounded limit, ordered public DTOs, and generated client
  bindings while preserving the parameterless live SSE route.
- Every V1 command maps to a verified public Forge HTTP operation through the
  ScoreSymphony-owned command adapter.
- The Forge recovery adapter validates page ordering and cursors, advances over
  unsupported internal Forge events, and projects supported lifecycle events
  through the canonical V1 validator.
- A concrete standard-library HTTP transport supplies bearer authentication,
  bounded timeouts, JSON handling, and cross-origin path protection.
- `ForgeIntegrationAdapter` composes command submission and durable event reads
  without importing Forge internals or creating a second lifecycle state.
- A startable authenticated ScoreSymphony gateway validates raw commands,
  exposes command receipts and cursor-based recovery pages, separates liveness
  from Forge-backed readiness, caps request bodies, and fails closed on invalid
  upstream history.
- A non-root gateway container image and runtime configuration contract are
  present; Compose wiring is intentionally deferred until Forge authentication
  bootstrap and secret injection are defined.
- A Hermes-facing authenticated gateway client serializes immutable V1
  commands, validates matching receipts and recovery pages, advances across
  gateway-reported internal-event gaps, and retains no competing lifecycle or
  cursor state.
- A low-footprint `scoresymphony-hermes` CLI exposes command submission and
  cursor-based event reads through Hermes' existing terminal capability without
  modifying Hermes core or adding a permanent model-tool schema.
- An in-process integration acceptance test now crosses Hermes serialization,
  authenticated gateway ingress, Forge command mapping, historical Forge event
  projection, gateway recovery output, and Hermes-side V1 validation.

## Verified integration facts

- Forge task creation is project-scoped.
- Forge task updates and task actions support optimistic concurrency.
- Forge owns task start/dispatch, workspace creation, review/gates, and merge.
- Forge execution retry/cancel has public execution endpoints.
- Forge live events include task, workspace, execution, review, and merge
  lifecycle information that can be normalized into V1.
- Forge `/api/v1/events` is a broadcast SSE stream and signals
  `events.resync_required` on lag.
- Forge's authenticated historical read exposes those persisted events as
  stable public DTOs and is covered by Rust API tests and CI.

## Not implemented yet

- Live SSE projection adapter.
- Durable command idempotency integration against Forge-owned state/events.
- Optional service-gated Hermes tool registration around the ScoreSymphony-owned
  gateway client if terminal/CLI ergonomics prove insufficient.
- Forge-integrated shell-worker end-to-end vertical slice.
- Integration of the pending shared security-contract branch into command
  ingress and worker execution.
- Deployment, Control Plane, agent registry, managed externals, specialist
  agents, and KVM placement.

## Next work package

Promote the proven in-process integration slice to a process-level acceptance
test using the Hermes CLI and gateway server, then connect Forge dispatch to the
deterministic shell worker through Forge-owned lifecycle operations. Define
Forge authentication bootstrap and secret injection before adding the gateway
to Compose. Recovery consumers must persist cursors only after successful page
processing.

## Blockers

Durable command idempotency is still unresolved: network/server failures cannot
be retried blindly until a Forge-owned dedupe/recovery strategy is proven. Live
SSE normalization also remains unimplemented. This branch must not be merged
without a full repository CI pass, including the Forge Rust checks.
