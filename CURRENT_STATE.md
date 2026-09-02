# Current State

Updated: **2026-09-02**  
Baseline classification: **Integrated Kernel in progress**  
Production readiness: **not production-ready**

## 1. Current objective

Complete the first production-quality ScoreSymphony-to-Forge Integrated Kernel without changing the authority model:

- Hermes remains the sole intelligent orchestrator.
- Forge remains the canonical deterministic task, execution, workspace, worker dispatch, review, gate and merge authority.
- ScoreSymphony owns the versioned integration contracts, gateway/adapters, project-specific security integration and future Control Plane.
- Workers remain bounded execution primitives.

Historical Forge event recovery and deterministic shell-worker acceptance are no longer blockers. The immediate blockers are live-event integration, Forge-backed worker dispatch, durable command idempotency and the full process-level end-to-end proof.

## 2. Baseline status summary

| Area | Status | Current meaning |
|---|---|---|
| Repository governance / CI | PARTIAL / ACTIVE | strong baseline exists; fresh repo settings must be recreated |
| V1 Forge-aligned contracts | COMPLETE FOR CURRENT KERNEL | command/event vocabulary and concurrency semantics established |
| Historical Forge Domain Event Read | COMPLETE | authenticated persisted-event cursor API exists and is tested |
| Forge command adapter | PARTIAL / ADVANCED | current V1 commands map to public Forge operations; durable idempotency remains |
| ScoreSymphony HTTP gateway | PARTIAL / ADVANCED | authenticated command + historical read + health/readiness exist |
| Live Forge SSE -> V1 | NOT COMPLETE | immediate critical-path work |
| Hermes gateway client / CLI | PARTIAL / ADVANCED | usable command/read path exists; full process E2E still missing |
| Deterministic Shell Worker | COMPLETE AS ACCEPTANCE PRIMITIVE | bounded worker behavior accepted; Forge dispatch wiring still missing |
| Security contracts | COMPLETE AS FOUNDATION | contracts/policy/approval semantics exist; production persistence/enforcement missing |
| Integrated Kernel E2E | PARTIAL | in-process integration exists; Forge->worker and live-event process E2E missing |
| Recovery / durable idempotency | EARLY / PARTIAL | historical recovery exists; restart/dedup/replay ownership still incomplete |
| Reference deployment | PARTIAL | validation/Compose basics and gateway image exist; production wiring deferred |
| Observability | BASELINE ONLY | lifecycle metrics, correlation, alerts and operator diagnostics need expansion |
| Control Plane | NOT IMPLEMENTED | later release gate |
| Agent Registry / Scheduler | NOT IMPLEMENTED | later release gate |
| Component Manager | NOT IMPLEMENTED | later release gate |
| Research / domain agents | NOT IMPLEMENTED | later release gate |
| Production hardening | NOT COMPLETE | final security/recovery/load/upgrade acceptance remains |

## 3. Implemented and verified baseline

### 3.1 Architecture and V1 contracts

- Hermes is the sole intelligent orchestrator.
- Forge is the deterministic lifecycle authority for projects/tasks, executions, workspaces, worker dispatch, test/evidence state, reviews, gates and merge.
- V1 command submission is separated from terminal outcomes through `CommandReceipt` and terminal `command.*` events.
- Read/query concerns are separated from the command plane.
- Parsed nested contract data is recursively read-only after validation.
- Terminal command events require command causation.
- `create_task` carries explicit Forge `project_id` scope.
- Task mutations carry the expected Forge task `version` for optimistic concurrency.
- `run_id` and obsolete run-oriented vocabulary were replaced with `execution_id` / Forge execution terminology.
- Commands that would bypass Forge workspace/test/review/worker/merge authority were removed from V1.
- Contract fixtures, compatibility checks, semantic rejection tests and runtime tests cover the corrected vocabulary.

Current V1 commands:

- `create_task`
- `update_task`
- `start_task`
- `submit_task`
- `request_changes_task`
- `approve_task`
- `cancel_task`
- `retry_execution`
- `cancel_execution`

### 3.2 Historical Forge event recovery

Forge exposes an authenticated historical JSON read on `/api/v1/events` backed by persisted domain events. The implemented surface includes:

- exclusive sequence cursor;
- bounded `limit`;
- ordered public DTOs;
- stable API types;
- generated client bindings where required;
- route-level tests;
- Forge Rust CI coverage;
- unchanged parameterless live SSE behavior.

The ScoreSymphony recovery adapter validates page ordering and cursor behavior, rejects malformed/inconsistent recovery responses fail-closed, advances across unsupported internal Forge events without losing the durable cursor position, and projects supported Forge lifecycle events through the canonical V1 validator.

**Conclusion:** Historical Domain Event Read is complete for the current kernel and is no longer an integration blocker.

### 3.3 Forge command adapter and HTTP transport

- Every current V1 command maps to a verified public Forge HTTP operation.
- Project/task/execution identifiers and task versions are carried through the public boundary.
- A ScoreSymphony-owned HTTP transport provides bearer authentication, bounded timeouts, JSON handling and path/origin protection.
- `ForgeIntegrationAdapter` composes command submission and historical reads without importing private Forge internals or creating a second lifecycle database.

Still missing is a proven durable deduplication/recovery strategy for ambiguous command submissions. Until then, ambiguous transport failures must not trigger blind retries.

### 3.4 ScoreSymphony Gateway and Hermes-side integration

Implemented:

- authenticated ScoreSymphony gateway;
- `POST /v1/commands`;
- `GET /v1/events?after_sequence=N` historical recovery path;
- liveness and Forge-backed readiness separation;
- bounded request bodies;
- fail-closed validation of invalid upstream history;
- separate credentials for Hermes -> Gateway and Gateway -> Forge;
- Hermes-facing authenticated gateway client;
- `scoresymphony-hermes` CLI for low-footprint command submission/event reads;
- in-process acceptance path across Hermes serialization, gateway ingress, Forge mapping, historical event projection and Hermes V1 validation.

Not yet complete:

- process-level Hermes CLI -> real gateway server -> Forge acceptance test;
- canonical live SSE event projection and reconnect/resync;
- optional service-gated permanent Hermes tool registration if CLI ergonomics later prove insufficient.

### 3.5 Deterministic Shell Worker

The shell-worker acceptance primitive is complete for the current reference scope:

- explicit executable allowlisting;
- workspace confinement;
- deterministic execution environment/result normalization;
- bounded command timeout;
- success and non-zero failure handling;
- cooperative cancellation;
- caller-controlled explicit retry attempts;
- POSIX process-group termination for bounded descendant cleanup;
- declared and allowlisted write paths;
- deterministic `changed_paths` evidence;
- mode-only changes included in write-policy evidence;
- deterministic fixture workspace/tests.

The worker deliberately owns **no** orchestration, lifecycle, review, approval, merge, recovery or autonomous retry policy.

Still missing: Forge-owned dispatch wiring and the complete Forge-integrated worker lifecycle E2E.

### 3.6 Security foundation

Shared contracts and deterministic reference semantics exist for principals and credentials, authorization/resource/scope requests, policy decisions, operation digests, approval requests/records, expiry, self-approval policy and consumed approval state against replay.

Reference policy precedence is:

```text
DENY > REQUIRE_APPROVAL > ALLOW
```

The V1 `actor` field is asserted command data and is not authentication evidence. Production ingress must bind it to an authenticated principal.

Still missing:

- production authentication middleware/provisioning;
- persistent roles, policies and bindings;
- persistent approvals and atomic approval consumption;
- re-authorization before protected dispatch;
- persistent secret-safe audit storage/events;
- complete command-ingress and worker-dispatch enforcement;
- Forge authentication bootstrap and production secret injection.

### 3.7 Repository, CI, deployment and provenance

Present:

- repository governance/issue/PR templates;
- baseline validation;
- Python/Pytest and packaging checks;
- deployment validation;
- Compose validation;
- Forge Rust validation;
- non-root gateway container image;
- runtime configuration contract;
- pinned Forge/Hermes upstream metadata in `UPSTREAMS.yaml`;
- third-party provenance/license documentation in `THIRD_PARTY_NOTICES.md`.

Production gateway Compose wiring is intentionally not claimed complete until Forge authentication bootstrap and secret injection are defined.

## 4. Not implemented yet

The following must not be described as operational or complete:

- live Forge SSE -> canonical V1 event projection;
- race-safe catch-up -> live transition;
- reconnect and `events.resync_required` handling through Historical Read;
- durable consumer cursor persistence policy;
- process-level Hermes CLI -> Gateway -> Forge acceptance;
- durable command idempotency against Forge-owned state/events;
- Forge-owned dispatch wiring for the deterministic shell worker;
- full Hermes -> Gateway -> Forge -> Worker -> Review/Gate -> terminal event E2E;
- production authentication and credential provisioning;
- persistent RBAC/policies/role bindings;
- persistent approvals with atomic consumption;
- production audit storage;
- production gateway Compose wiring;
- complete restart/orphan/lease/replay recovery;
- Agent Registry;
- Resource Scheduler / capacity control;
- worker families beyond the shell-worker reference;
- independent ScoreSymphony reviewer path;
- model/coding backend adapter layer;
- ScoreSymphony Control Plane;
- Multi-Agent Terminal and Workflow Graph;
- Component Manager and managed external pilot;
- Research Broker;
- user-facing secure file/workspace functions;
- domain-specific music/research agents;
- ScoreSymphony fachliche application integration;
- final multi-node/VPS placement;
- final production security/recovery/load/upgrade acceptance.

## 5. Immediate critical path: Integrated Kernel

### IK-1 - Live Forge SSE projection

- connect to Forge live SSE through the public authenticated boundary;
- parse supported public event shapes;
- project lifecycle events into canonical V1 events;
- preserve sequence, correlation and causation semantics;
- fail explicitly on invalid upstream data.

### IK-2 - Reconnect and historical resynchronization

- recover disconnects through the existing Historical Event Read;
- handle `events.resync_required`;
- make catch-up -> live transition gap-free/race-safe;
- deduplicate overlap without creating a second lifecycle state;
- advance consumer cursor only after successful processing.

### IK-3 - Forge-owned Shell Worker dispatch

- connect the accepted deterministic shell worker behind Forge task/execution lifecycle;
- use Forge-created isolated workspace;
- preserve executable/path policies;
- return exit state, evidence and changed paths into Forge-owned lifecycle state;
- cover success, failure, timeout, cancellation and caller-controlled retry.

### IK-4 - Durable command idempotency

- choose a Forge-owned durable deduplication/recovery mechanism;
- persist enough command identity/correlation state to resolve ambiguous submissions;
- prove duplicate delivery cannot create a second task/execution lifecycle;
- define bounded behavior for timeout/network/server ambiguity;
- prohibit blind retry until the original outcome is resolved.

### IK-5 - Process-level and full E2E acceptance

Automate at least:

1. Hermes produces a valid V1 command.
2. Hermes-side client/CLI sends through authenticated Gateway.
3. Gateway validates/authenticates and calls Forge public API.
4. Forge creates the project-bound task.
5. Forge starts execution/workspace and dispatches shell worker.
6. Worker changes only the allowed fixture and returns evidence.
7. Forge records evidence/tests and applies review/gates.
8. Failure/review/gate cases remain blocked.
9. Successful lifecycle terminates deterministically.
10. Hermes receives validated terminal V1 event(s).
11. Duplicate command delivery does not create a second lifecycle.
12. Stale task version is rejected deterministically.
13. Live-event disconnect recovers historically and resumes without gaps.

Only after these are proven should **Integrated Kernel** be marked complete.

## 6. Parallel work allowed while Integrated Kernel is built

### Security implementation

- bind authenticated principals to V1 `actor` assertions;
- canonicalize protected operations/digests;
- add persistent role/policy configuration and role bindings;
- add persistent approvals and atomic approved -> consumed transition;
- re-evaluate authorization immediately before protected dispatch;
- add secret-safe audit events/storage;
- prove denied/stale/mismatched/expired/consumed/unapproved requests never reach Forge adapter or worker dispatch.

### Repository / CI / deployment hygiene

- keep Python, contract, deployment, Compose and Forge Rust gates required;
- keep dependency/license/security checks aligned with repository policy;
- normalize Forge Cargo lock/dependency state before tightening locked checks;
- keep documentation synchronized with implemented behavior;
- do not expose gateway publicly before production auth/secret bootstrap exists.

## 7. Release path after Integrated Kernel

1. **Recoverable Runtime** - durable replay/restart/orphan/lease/idempotency and recovery correctness.
2. **Operable Deployment** - production auth/policy/approvals, reproducible deployment, secrets, backup/restore and operator runbooks.
3. **Controlled Multi-Agent** - registry, resource admission/scheduling, additional workers and independent review path.
4. **Extensible Platform** - model/coding adapters, Control Plane, terminal/graph and Component Manager.
5. **Research / Domain Ready** - research provenance, secure user file/workspace features, domain workers and ScoreSymphony application integration.
6. **Production Candidate** - final security/recovery/load/agent-safety/upgrade hardening and complete documentation.

Detailed work-package acceptance criteria are maintained in `ROADMAP.md`.

## 8. Clone-ready baseline rules

The new repository should start from a verified snapshot of the **current `main` working tree** and should not import the old `.git` directory.

The fresh baseline must preserve all current source/tests/docs, `LICENSE` and nested upstream license/copyright notices, `UPSTREAMS.yaml`, `THIRD_PARTY_NOTICES.md`, ADR/security/deployment documentation and source-controlled CI workflows.

GitHub-hosted state does not move with the files. Branch protection/rules, required checks, secrets, Actions settings, issues, milestones and other repository settings must be recreated explicitly.

Old issues/PRs/branches remain historical evidence in the archived source repo and should not be copied wholesale into the clean repository.

See `BASELINE_HANDOFF.md` for the exact migration procedure and the proposed fresh issue/milestone structure.