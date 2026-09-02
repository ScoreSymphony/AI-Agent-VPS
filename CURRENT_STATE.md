# Current state

Updated: 2026-09-02

## Current objective

Build the first production-quality ScoreSymphony-to-Forge adapter and integrated
kernel on top of the verified V1 boundary, authenticated Forge historical event
recovery, the deterministic shell-worker acceptance surface, and the shared
security contracts without changing Forge lifecycle ownership.

## Implemented in this branch

* Hermes remains the sole intelligent orchestrator.
* Forge remains the deterministic task, execution, workspace, review, gate, and
  merge authority.
* V1 command submission is separated from terminal command outcomes through
  `CommandReceipt` and terminal `command.*` events.
* Read/query concerns are separated from the command plane.
* Parsed nested contract data is recursively read-only after validation.
* Terminal command events require command causation.
* ADR-0001 accurately describes HTTP/JSON + SSE as the live transport.
* ADR-0002 is accepted and aligns V1 to verified Forge lifecycle operations.
* `create_task` carries explicit Forge `project_id` scope.
* Task mutations carry the expected Forge task `version`.
* `run_id` and run-oriented commands/events are replaced by Forge
  `execution_id` / execution terminology.
* Commands that would bypass or duplicate Forge workspace, test, review, worker,
  or merge authority are removed from V1.
* Contract fixtures, compatibility checks, semantic rejection tests, and runtime
  tests cover the corrected vocabulary.
* Forge exposes an authenticated historical JSON read on `/api/v1/events` backed
  by persisted domain events, with exclusive cursor, bounded limit, ordered
  public DTOs, generated client bindings, route-level tests, and Rust CI
  coverage while preserving the parameterless live SSE route.
* Every V1 command maps to a verified public Forge HTTP operation through the
  ScoreSymphony-owned command adapter.
* The Forge recovery adapter validates page ordering and cursors, advances over
  unsupported internal Forge events, and projects supported lifecycle events
  through the canonical V1 validator.
* A concrete standard-library HTTP transport supplies bearer authentication,
  bounded timeouts, JSON handling, and cross-origin path protection.
* `ForgeIntegrationAdapter` composes command submission and durable event reads
  without importing Forge internals or creating a second lifecycle state.
* A startable authenticated ScoreSymphony gateway validates raw commands,
  exposes command receipts and cursor-based recovery pages, separates liveness
  from Forge-backed readiness, caps request bodies, and fails closed on invalid
  upstream history.
* A Hermes-facing authenticated gateway client serializes immutable V1
  commands, validates matching receipts and recovery pages, advances across
  gateway-reported internal-event gaps, and retains no competing lifecycle or
  cursor state.
* A low-footprint `scoresymphony-hermes` CLI exposes command submission and
  cursor-based event reads through Hermes' existing terminal capability without
  modifying Hermes core or adding a permanent model-tool schema.
* An in-process integration acceptance test crosses Hermes serialization,
  authenticated gateway ingress, Forge command mapping, historical Forge event
  projection, gateway recovery output, and Hermes-side V1 validation.
* The transport-neutral deterministic shell-worker reference implementation
  covers executable allowlisting, workspace confinement, deterministic
  environment and result handling, predictable fixture changes, success,
  failure, timeout, cooperative cancellation, and explicit caller-controlled
  retry attempts without an LLM.
* Shell-worker timeout and cancellation collection remain deadline-bounded when
  a direct parent exits while descendants retain inherited pipes; POSIX
  invocations use a dedicated process group for bounded descendant termination.
* Shell-worker write policy is enforced through declared and allowlisted write
  paths.
* Workspace write-policy evidence includes relevant content changes and file-mode
  changes, so a mode-only mutation such as an executable-bit change cannot
  bypass the declared-write-path check.
* The shell worker remains a bounded execution primitive rather than an
  orchestrator or owner of Forge lifecycle, approvals, recovery, retry policy,
  or merge policy.
* Security contract primitives define principals, credentials, resource scopes,
  authorization requests and decisions, approval records, and shared ports.
* Deterministic reference policy semantics are default-deny with precedence
  `DENY > REQUIRE_APPROVAL > ALLOW`.
* Approval validation binds approval to the exact authorization request and
  required policy, supports expiry, defaults to no self-approval, and models
  consumed approvals for replay prevention.
* The V1 command `actor` is asserted command data and is not authentication
  evidence; runtime ingress must bind it to an authenticated principal.
* Repository governance templates are present for implementation work, ADRs,
  upstream updates, security hardening, and architecture-aware pull request
  reviews.
* Baseline validation, Pytest, packaging checks, deployment validation, Compose
  validation, Forge Rust validation, and GitHub Actions quality gates are
  present.
* A non-root gateway container image and runtime configuration contract are
  present; Compose wiring is intentionally deferred until Forge authentication
  bootstrap and secret injection are defined.

## Verified integration facts

* Forge task creation is project-scoped.
* Forge task updates and task actions support optimistic concurrency.
* Forge owns task start and dispatch, workspace creation, review and gates, and
  merge.
* Forge execution retry and cancellation have public execution endpoints.
* Forge live events include task, workspace, execution, review, and merge
  lifecycle information that can be normalized into V1.
* Forge `/api/v1/events` remains the live broadcast SSE stream and signals
  `events.resync_required` on lag.
* Forge also exposes an authenticated historical domain-event read capability
  backed by persisted domain events for recovery after an exclusive sequence
  cursor.
* The historical event surface exposes stable public DTOs and is covered by
  Rust API tests and CI.
* Historical recovery and deterministic shell-worker acceptance are therefore
  no longer blockers for adapter integration.
* The shell worker must remain behind Forge-owned dispatch and lifecycle
  authority rather than becoming a parallel execution authority.
* The V1 command `actor` must be bound to an authenticated principal at runtime;
  it must never be treated as authentication evidence on its own.

## Not implemented yet

* Live Forge SSE projection into canonical V1 events.
* Process-level Hermes CLI → gateway → Forge acceptance coverage.
* Durable command idempotency integration against Forge-owned state and events.
* Forge-backed dispatch wiring for the deterministic shell-worker reference
  implementation.
* Full Forge-integrated shell-worker end-to-end vertical slice.
* Integration of shared security contracts into command ingress and worker
  dispatch.
* Production authentication middleware and credential provisioning.
* Forge authentication bootstrap and production secret injection.
* Persistent RBAC and policy configuration.
* Persistent role bindings.
* Persistent approval storage with atomic approval consumption.
* Security audit storage and audit-event wiring.
* Optional service-gated Hermes tool registration around the
  ScoreSymphony-owned gateway client if terminal/CLI ergonomics prove
  insufficient.
* Production Compose wiring for the ScoreSymphony gateway.
* Control Plane.
* Agent registry.
* Managed externals.
* Specialist agents.
* Final multi-VPS placement and operations wiring.

## Next work package

The immediate critical path is to promote the proven integration components into
a process-level and Forge-owned execution vertical slice.

1. Add a process-level acceptance test using the `scoresymphony-hermes` CLI and
   the ScoreSymphony gateway server.
2. Implement live Forge SSE consumption and normalize supported Forge lifecycle
   events into canonical V1 events.
3. Reuse authenticated historical event recovery for reconnect and
   `events.resync_required` handling.
4. Ensure recovery consumers persist cursors only after successful page
   processing.
5. Preserve command causation, correlation, explicit adapter failures, and
   Forge-owned lifecycle state throughout live and historical event handling.
6. Define Forge authentication bootstrap and secret injection before adding the
   gateway to production Compose.
7. Connect Forge dispatch to the deterministic shell worker through Forge-owned
   lifecycle operations rather than directly from Hermes or the gateway.
8. Cover command submission, live events, historical recovery, worker dispatch,
   cancellation, retry behavior, worker evidence, and failure handling in an
   end-to-end vertical slice.
9. Resolve durable command idempotency using Forge-owned state or events before
   allowing blind retry of ambiguous command submissions.

In parallel, security implementation should proceed behind the existing shared
security ports:

1. bind authenticated principals to V1 `actor` assertions at ingress;
2. define and enforce canonical operation serialization and digests;
3. add persistent role and policy configuration;
4. add persistent role bindings;
5. add persistent approvals with atomic approved-to-consumed transition;
6. re-evaluate authorization immediately before approval consumption and
   dispatch;
7. add secret-safe audit events and persistent audit storage;
8. prove denied, stale-policy, mismatched-payload, expired, consumed, or
   unapproved requests never reach the Forge adapter or worker dispatch.

Repository and CI hardening should continue alongside runtime work:

1. keep Python, Compose, deployment, and Forge Rust checks as required quality
   gates;
2. keep governance and security reporting workflows aligned with repository
   policy;
3. normalize and lock Forge dependency state once the current Cargo lockfile
   drift is resolved;
4. keep `CURRENT_STATE.md`, architecture documentation, and roadmap documents
   factual as implementation progresses.

## Blockers

The historical recovery surface and deterministic shell-worker acceptance
surface are no longer blockers.

The remaining critical-path risks are:

* correct live-event projection and reconnect/resync behavior;
* Forge-backed shell-worker dispatch without creating a parallel lifecycle;
* durable command idempotency for ambiguous network or server failures;
* production authentication bootstrap and secret provisioning;
* security-gate integration before command execution and worker dispatch;
* successful process-level and end-to-end acceptance coverage.

Durable command idempotency remains unresolved. Network or server failures must
not cause command submission to be retried blindly until a Forge-owned
deduplication or recovery strategy has been proven.

Security contracts are prepared, but production authentication, persistent
authorization policy, role bindings, approvals, atomic approval consumption,
and audit wiring must not be described as operational until those integrations
and their tests exist.

The gateway container and runtime configuration exist, but production Compose
wiring must remain deferred until Forge authentication bootstrap and secret
injection are explicitly defined.

The shell-worker reference implementation is sufficiently defined for
integration work, but it must remain behind Forge-owned dispatch and lifecycle
authority rather than becoming a parallel execution authority.

This branch should not be merged until the full repository quality-gate suite,
including Forge Rust checks, passes.
