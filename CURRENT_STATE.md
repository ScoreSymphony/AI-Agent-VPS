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
- Forge has an authenticated public historical domain-event read mode backed by
  persisted domain events, with route-level tests and Rust CI coverage.
- The transport-neutral deterministic shell reference worker covers executable
  allowlisting, workspace confinement, deterministic environment/result handling,
  timeout limits, cooperative cancellation, explicit caller-controlled retries,
  declared/allowlisted write paths, content and mode-change evidence, and POSIX
  process-group termination for descendants that retain inherited pipes.
- Security contract primitives define principals, credentials, resource scopes,
  authorization requests/decisions, approval records, and shared ports.
- Deterministic reference policy semantics are default-deny with precedence
  `DENY > REQUIRE_APPROVAL > ALLOW`.
- Approval validation binds approval to the exact authorization request and
  required policy, supports expiry, defaults to no self-approval, and models
  consumed approvals for replay prevention.
- Repository governance templates, baseline validation, Pytest, packaging checks,
  deployment validation, Compose validation, Forge Rust validation, and GitHub
  Actions quality gates are present.

## Verified integration facts

- Forge task creation is project-scoped.
- Forge task updates and task actions support optimistic concurrency.
- Forge owns task start/dispatch, workspace creation, review/gates, and merge.
- Forge execution retry/cancel has public execution endpoints.
- Forge live events include task, workspace, execution, review, and merge
  lifecycle information that can be normalized into V1.
- Forge `/api/v1/events` remains the live broadcast SSE stream and signals
  `events.resync_required` on lag.
- Forge also exposes the authenticated historical domain-event read capability
  required for adapter recovery after a sequence cursor.
- The shell worker is a bounded execution primitive, not an orchestrator and not
  an owner of Forge lifecycle, approvals, recovery, retry policy, or merge policy.
- The V1 command `actor` is asserted command data and is not authentication
  evidence; runtime ingress must bind it to an authenticated principal.

## Not implemented yet

- Running ScoreSymphony command HTTP endpoint and SSE projection adapter.
- Durable command idempotency integration against Forge-owned state/events.
- Hermes-side V1 tools/adapter.
- Forge-backed dispatch wiring for the shell reference worker.
- Production authentication middleware and credential provisioning.
- Persistent RBAC/policy configuration, role bindings, approval storage, atomic
  approval consumption, and security audit storage.
- Control Plane, agent registry, managed externals, specialist agents, and final
  multi-VPS placement/operations wiring.

## Next work package

The critical path is the integrated ScoreSymphony Forge adapter/runtime:

1. map each V1 command only to verified public Forge operations;
2. normalize live Forge events into V1 events;
3. use the authenticated historical event read for cursor recovery/resync;
4. preserve command causation, correlation, explicit adapter failures, and
   Forge-owned idempotency/lifecycle state;
5. route bounded worker dispatch behind Forge rather than around it;
6. cover command, live event, recovery, cancellation, retry, and worker evidence
   in an end-to-end vertical slice.

In parallel, security implementation can proceed behind the shared ports:

1. bind authenticated principals to V1 actor assertions at ingress;
2. add persistent role/policy configuration;
3. add persistent approvals with atomic approved-to-consumed transition;
4. add secret-safe audit events;
5. prove denied, stale-policy, mismatched-payload, or unapproved requests never
   reach the Forge adapter.

## Blockers

The historical recovery surface and deterministic shell-worker acceptance surface
are no longer blockers. The remaining critical-path risk is correct adapter/runtime
integration across command, live-event, recovery, worker-dispatch, and security
gates. Security contracts are prepared, but production auth, policy persistence,
approvals, and audit wiring must not be described as operational until those
integrations and tests exist.
