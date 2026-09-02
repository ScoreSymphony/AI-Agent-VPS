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
- Forge has an authenticated public historical domain-event read mode backed by
  persisted domain events, with route-level tests and Rust CI coverage.
- The transport-neutral deterministic shell-worker reference implementation
  covers executable allowlisting, workspace confinement, deterministic
  environment and result handling, predictable fixture changes, success,
  failure, timeout, cooperative cancellation, and explicit caller-controlled
  retry attempts without an LLM.
- Shell-worker timeout and cancellation collection remain deadline-bounded when a
  direct parent exits while descendants retain inherited pipes; POSIX
  invocations use a dedicated process group for bounded descendant termination.
- Shell-worker write policy is enforced through declared and allowlisted write
  paths.
- Workspace write-policy evidence includes relevant content changes and file-mode
  changes, so a mode-only mutation such as an executable-bit change cannot bypass
  the declared-write-path check.
- Security contract primitives define principals, credentials, resource scopes,
  authorization requests and decisions, approval records, and shared ports.
- Deterministic reference policy semantics are default-deny with precedence
  `DENY > REQUIRE_APPROVAL > ALLOW`.
- Approval validation binds approval to the exact authorization request and
  required policy, supports expiry, defaults to no self-approval, and models
  consumed approvals for replay prevention.
- Repository governance templates are present for implementation work, ADRs,
  upstream updates, security hardening, and architecture-aware pull request
  reviews.
- Baseline validation, Pytest, packaging checks, deployment validation, Compose
  validation, Forge Rust validation, and GitHub Actions quality gates are
  present.

## Verified integration facts

- Forge task creation is project-scoped.
- Forge task updates and task actions support optimistic concurrency.
- Forge owns task start and dispatch, workspace creation, review and gates, and
  merge.
- Forge execution retry and cancellation have public execution endpoints.
- Forge live events include task, workspace, execution, review, and merge
  lifecycle information that can be normalized into V1.
- Forge `/api/v1/events` remains the live broadcast SSE stream and signals
  `events.resync_required` on lag.
- Forge also exposes the authenticated historical domain-event read capability
  required for adapter recovery after a sequence cursor.
- The shell worker is a bounded execution primitive, not an orchestrator and not
  an owner of Forge lifecycle, approvals, recovery, retry policy, or merge
  policy.
- The V1 command `actor` is asserted command data and is not authentication
  evidence; runtime ingress must bind it to an authenticated principal.

## Not implemented yet

- Running ScoreSymphony command HTTP endpoint and SSE projection adapter.
- Durable command idempotency integration against Forge-owned state and events.
- Hermes-side V1 tools and adapter.
- Forge-backed dispatch wiring for the shell-worker reference implementation.
- Full Forge-integrated shell-worker end-to-end vertical slice.
- Production authentication middleware and credential provisioning.
- Persistent RBAC and policy configuration.
- Persistent role bindings.
- Persistent approval storage with atomic approval consumption.
- Security audit storage and audit-event wiring.
- Control Plane.
- Agent registry.
- Managed externals.
- Specialist agents.
- Final multi-VPS placement and operations wiring.

## Next work package

The critical path is the integrated ScoreSymphony Forge adapter and runtime:

1. map each V1 command only to verified public Forge operations;
2. normalize live Forge events into V1 events;
3. use the authenticated historical event read for cursor recovery and resync;
4. preserve command causation, correlation, explicit adapter failures, and
   Forge-owned idempotency and lifecycle state;
5. route bounded worker dispatch behind Forge rather than around it;
6. integrate the deterministic shell worker into the Forge-owned execution path;
7. cover command submission, live events, historical recovery, cancellation,
   retry behavior, worker evidence, and failure handling in an end-to-end
   vertical slice.

In parallel, security implementation can proceed behind the shared ports:

1. bind authenticated principals to V1 actor assertions at ingress;
2. define and enforce canonical operation serialization and digests;
3. add persistent role and policy configuration;
4. add persistent role bindings;
5. add persistent approvals with atomic approved-to-consumed transition;
6. re-evaluate authorization immediately before approval consumption and
   dispatch;
7. add secret-safe audit events and persistent audit storage;
8. prove denied, stale-policy, mismatched-payload, expired, consumed, or
   unapproved requests never reach the Forge adapter.

Repository and CI hardening should continue alongside the runtime work:

1. keep Python, Compose, deployment, and Forge Rust checks as required quality
   gates;
2. keep governance and security reporting workflows aligned with repository
   policy;
3. normalize and lock Forge dependency state once the current Cargo lockfile
   drift is resolved;
4. keep `CURRENT_STATE.md`, architecture documentation, and roadmap documents
   factual as implementation progresses.

## Blockers

The historical recovery surface and deterministic shell-worker acceptance surface
are no longer blockers.

The remaining critical-path risk is correct adapter and runtime integration
across command submission, live-event projection, historical recovery,
worker dispatch, idempotency, and security gates.

Security contracts are prepared, but production authentication, persistent
authorization policy, role bindings, approvals, atomic approval consumption, and
audit wiring must not be described as operational until those integrations and
their tests exist.

The shell-worker reference implementation is sufficiently defined for
integration work, but it must remain behind Forge-owned dispatch and lifecycle
authority rather than becoming a parallel execution authority.