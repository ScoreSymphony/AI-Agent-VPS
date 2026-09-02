# ScoreSymphony Agent Platform - Roadmap

Updated: **2026-09-02**  
Repository baseline: `ScoreSymphony/AI-Agent-VPS`  
Current release gate: **Integrated Kernel**

## 1. Purpose

This roadmap describes the path from the current verified ScoreSymphony Agent
Platform baseline to a Production Candidate. It replaces stale planning language
that treated Historical Forge Event Recovery or the deterministic Shell Worker
as future blockers; both are already implemented as accepted building blocks.

There is no historical phase numbering. Priority and order are determined by
technical dependencies, security boundaries and verifiable release gates.

The roadmap is deployment-neutral. Single-node is the reproducible reference
baseline. Multiple VPS hosts, remote workers, GPU nodes or separate
monitoring/backup systems are optional deployment profiles selected later from
measurements and failure-domain requirements.

## 2. Status legend

- **COMPLETE** - acceptance surface required by the current roadmap exists and
  is verified for its intended scope.
- **PARTIAL** - meaningful implementation exists, but acceptance criteria remain.
- **NOT STARTED** - no production-claimable implementation exists yet.
- **ONGOING** - cross-cutting work that already has a baseline and continues
  through later release gates.

A work package being COMPLETE does not imply the entire release gate is complete.
For example, the Shell Worker acceptance primitive is complete while its
Forge-owned dispatch integration is still part of the Integrated Kernel.

## 3. Non-negotiable architecture

- **Hermes is the sole intelligent orchestrator.**
- **Forge is the canonical deterministic lifecycle authority** for projects,
  tasks, versions, executions, workspaces, worker dispatch, evidence/tests,
  reviews, gates, merge and durable lifecycle events.
- ScoreSymphony integrates Hermes and Forge only through versioned
  ScoreSymphony contracts and verified public Forge interfaces.
- Workers are bounded executors and do not become orchestrators.
- Command submission and terminal outcome remain separate concepts.
- No private Forge database dependency is allowed in Hermes.
- No second task/execution/review/merge truth is allowed in Gateway, Hermes,
  workers or the future Control Plane.
- `actor` is asserted command data, not authentication evidence.
- Security boundaries are default-deny and high-risk actions require explicit,
  auditable authorization/approval.
- The core remains license/provenance clean. Upstream and external components
  keep their source, version and license identity.
- The platform must remain usable without introducing additional recurring paid
  AI/API dependencies as an architectural requirement.

## 4. Current critical path

Historical recovery and Shell Worker acceptance are already available. The
shortest path to the next release gate is now:

```text
Live Forge SSE -> V1
        |
Reconnect + historical resync
        |
Forge-owned Shell Worker dispatch
        |
Durable command idempotency
        |
Process-level Hermes -> Gateway -> Forge -> Worker E2E
        |
Integrated Kernel release gate
```

Security persistence/enforcement and CI/deployment hygiene can proceed in
parallel where they do not alter the same lifecycle boundary.

---

# Work packages

## 1. Repository Governance and CI Hardening

**Status: ONGOING**  
**Priority: P0 / cross-cutting**

### Already present

- architecture-aware PR and issue templates;
- baseline validation;
- Python/Pytest and packaging checks;
- deployment validation;
- Compose validation;
- Forge Rust validation;
- source-controlled workflow configuration;
- provenance/license tracking for upstream snapshots.

### Still required

- recreate branch rules/required checks in the fresh repository;
- keep dependency, license and secret/security checks aligned with available
  GitHub/free tooling;
- normalize Forge Cargo dependency/lock state before tightening locked checks;
- continuously require factual `CURRENT_STATE.md` / architecture changes when
  behavior changes.

### Acceptance

Productive changes cannot bypass required checks/review policy; failed required
checks block merge; no real credentials are committed or leaked by CI.

---

## 2. Historical Forge Domain Event Read

**Status: COMPLETE**  
**Priority: P0 foundation**

Implemented authenticated read-only access to persisted Forge domain events with
exclusive `after_sequence` cursor, bounded limit, ordered stable public DTOs,
invalid-input handling, route tests, generated bindings where required and Rust
CI coverage. Parameterless Forge live SSE remains unchanged.

### Acceptance

Met for the current kernel scope. This work package is no longer a blocker.

---

## 3. Forge Adapter

**Status: PARTIAL / ADVANCED**  
**Priority: P0**

### Already present

- all current V1 commands map to verified public Forge HTTP operations;
- `project_id`, `task_id`, `execution_id` and task versions are carried through;
- historical Forge event pages are validated and supported lifecycle events are
  projected into canonical V1 event shapes;
- private Forge database/services are not imported into Hermes;
- command transport uses authenticated public Forge boundaries.

### Still required

- finish live-event normalization path;
- prove deterministic duplicate handling through durable Forge-owned idempotency;
- ensure every public Forge rejection/concurrency failure is projected with
  stable ScoreSymphony failure semantics;
- integrate worker dispatch only behind Forge-owned lifecycle.

### Acceptance

Every V1 command/event needed by the Integrated Kernel is covered by public
Forge interfaces, duplicate/ambiguous delivery cannot create a second lifecycle,
and no private Forge internals leak into Hermes.

---

## 4. ScoreSymphony HTTP/SSE Transport Runtime

**Status: PARTIAL / ADVANCED**  
**Priority: P0 - immediate critical path**

### Already present

- authenticated ScoreSymphony Gateway;
- HTTP/JSON command ingress;
- command validation and `CommandReceipt` behavior;
- authenticated historical event recovery;
- health/readiness separation;
- request bounds and fail-closed upstream validation;
- authenticated Forge transport.

### Still required

- live Forge SSE consumption;
- V1 projection of supported live lifecycle events;
- disconnect handling;
- `events.resync_required` handling;
- race-safe historical catch-up -> live transition;
- overlap deduplication without second lifecycle state;
- cursor advancement only after successful processing;
- bounded buffers/backpressure/timeouts.

### Acceptance

A live connection may fail at arbitrary points and recover through historical
reads without silent gaps, incorrect cursor advancement or duplicate lifecycle
state.

---

## 5. Hermes Adapter and ScoreSymphony Tools

**Status: PARTIAL / ADVANCED**  
**Priority: P0**

### Already present

- authenticated Hermes-side Gateway client;
- `scoresymphony-hermes` CLI;
- current V1 command serialization;
- historical event read/validation;
- in-process Hermes -> Gateway -> Forge integration acceptance.

### Still required

- consume terminal/live V1 event flow in the process-level path;
- process-level CLI -> Gateway -> Forge acceptance;
- verify correlation/causation preservation end to end;
- optionally add service-gated permanent Hermes tool registration only if CLI
  ergonomics prove insufficient.

### Acceptance

Hermes can plan and submit through V1, observe terminal lifecycle truth, and
never gains its own workspace/test/review/merge authority.

---

## 6. Deterministic Shell Worker

**Status: COMPLETE AS REFERENCE WORKER**  
**Priority: P0 foundation**

Implemented executable allowlisting, workspace confinement, deterministic
environment/results, timeout, non-zero failure, cooperative cancellation,
caller-controlled retries, POSIX descendant termination, declared write-path
policy and deterministic changed-path evidence including file-mode changes.

### Important boundary

Completion here means the worker primitive is accepted. Forge-owned dispatch
wiring is still part of Work Package 7 / Integrated Kernel.

---

## 7. Integrated Kernel - Full End-to-End Slice

**Status: PARTIAL - CURRENT RELEASE GATE**  
**Priority: P0**

### Already present

- V1 contracts;
- authenticated command Gateway;
- public Forge command mapping;
- historical recovery;
- Hermes client/CLI;
- deterministic Shell Worker;
- in-process integration acceptance;
- Security Contract foundation.

### Required to close the gate

1. Hermes produces a valid V1 task intent.
2. Authenticated Gateway accepts/validates the command.
3. Forge creates the project-bound task.
4. Forge starts execution and isolated workspace.
5. Forge dispatches the bounded Shell Worker.
6. Worker changes only the allowed fixture and returns evidence.
7. Forge stores test/evidence state and applies review/gates.
8. Failed review/gates block completion/merge.
9. Successful lifecycle reaches controlled terminal state.
10. Terminal outcome reaches Hermes as validated V1 event.
11. Duplicate command delivery creates no second lifecycle.
12. Stale task version is deterministically rejected.
13. Live event disconnect recovers via Historical Read and resumes without gaps.

### Immediate sub-work

- **IK-1:** Live Forge SSE -> V1 projection.
- **IK-2:** reconnect/resync + cursor-safe catch-up/live transition.
- **IK-3:** Forge-owned Shell Worker dispatch.
- **IK-4:** durable command idempotency / ambiguous-submission recovery.
- **IK-5:** process-level/full E2E acceptance suite.

---

## 8. Reliability, Persistence and Recovery

**Status: PARTIAL / EARLY**  
**Priority: P0 after Integrated Kernel**

### Foundation already present

- durable Forge domain events;
- authenticated historical event recovery;
- explicit command/correlation/causation concepts;
- bounded worker timeout/cancellation behavior.

### Still required

- durable command idempotency and Hermes-intent/Forge-object correlation;
- restart-safe command/result recovery;
- event replay invariants and cursor persistence;
- expired lease detection;
- crashed worker / half-finished execution detection;
- orphaned workspace policy;
- retry budgets;
- bounded repair loops;
- minimal platform backup/restore state;
- fail-closed inconsistency handling.

### Acceptance / Release gate: Recoverable Runtime

Restarts lose no confirmed task, do not duplicate completed/running work, replay
reconstructs the same auditable state, and unresolved inconsistency fails closed
and visibly.

---

## 9. Security, Policy and Approval Layer

**Status: PARTIAL - CONTRACT FOUNDATION COMPLETE**  
**Priority: P0 before external/production exposure**

### Already present

- principal/credential/resource/scope contracts;
- authorization requests/decisions;
- default-deny reference semantics;
- `DENY > REQUIRE_APPROVAL > ALLOW` precedence;
- exact operation/policy binding;
- approval expiry, no-self-approval default and consumed state.

### Still required

- bind authenticated principal to V1 `actor` assertion;
- persistent roles/policies/bindings;
- persistent approvals with atomic consumption;
- re-authorization before dispatch;
- secret-safe persistent security audit;
- policy enforcement at command ingress and worker dispatch;
- production credential provisioning/rotation;
- Forge auth bootstrap and secret injection;
- egress, path, command, resource and privilege-escalation enforcement tests.

### Acceptance

Unauthorized commands/paths/tools/egress/privilege changes never reach protected
Forge/worker actions, and approvals cannot be replayed or used for a different
operation.

---

## 10. Reproducible Reference Deployment

**Status: PARTIAL**  
**Priority: P1 after security bootstrap is defined**

### Already present

- deployment/Compose validation foundation;
- persistent Forge data baseline;
- health/liveness basics;
- bounded logging/restart configuration baseline;
- non-root Gateway image;
- runtime configuration contract.

### Still required

- production Gateway Compose wiring;
- reproducible Forge auth bootstrap and secret injection;
- complete readiness/dependency checks;
- migrations/upgrade/rollback procedure;
- backup/restore;
- resource limits and permissions review;
- reverse proxy/TLS only after production auth baseline;
- operator start/stop/update/diagnosis/recovery runbook.

### Acceptance / Release gate: Operable Deployment

A fresh supported host can start the platform reproducibly and run the complete
Integrated Kernel without manual source edits.

---

## 11. Observability and Operations

**Status: PARTIAL / BASELINE**  
**Priority: P1 continuous**

Required correlation dimensions include `correlation_id`, `command_id`,
`task_id`, `execution_id`, worker/agent identity and relevant event sequence.

Still required: lifecycle latency/error/retry/queue metrics, CPU/RAM/I/O/storage
and worker utilization, replay/recovery diagnostics, actionable alerts for
service failure, blocked queues, orphaned leases, backup failure and unusual
resource pressure.

### Acceptance

A failed lifecycle can be reconstructed from logs/events/metrics and alerts state
an actionable operator response.

---

## 12. Agent Registry

**Status: NOT STARTED**  
**Priority: P1**

Versioned agent manifest covering identity/type, capabilities, tools,
model/backend, resource requirements, security profile, health, version and
allowed task classes.

### Acceptance

Agents can be registered, validated, enabled and disabled without changing core
platform contracts.

---

## 13. Resource Scheduler and Capacity Control

**Status: NOT STARTED**  
**Priority: P1**

Deterministically check CPU, RAM, storage, concurrency, workspace capacity,
model/backend limits and policy before worker start. Hermes selects capability;
runtime controls admissibility and start timing.

### Acceptance

Over-capacity or policy-forbidden work is delayed/rejected before execution and
cannot bypass resource limits.

---

## 14. Worker Families

**Status: NOT STARTED BEYOND SHELL REFERENCE**  
**Priority: P1/P2 incremental**

Candidate worker classes: Coding, Research, File, Infrastructure/Server,
Monitoring, Deployment, Review and domain-specific music/research workers.

Each worker receives minimum rights, explicit tools and a resource/security
profile.

---

## 15. Independent Review Path

**Status: NOT STARTED**  
**Priority: P1**

Separate reviewer should be read-only by default, inspect evidence/diffs/tests
and policy violations, support bounded repair cycles, and feed its result into
Forge gates without gaining uncontrolled merge/privilege authority.

Forge's existing review lifecycle is an authority foundation, not by itself the
complete independent ScoreSymphony reviewer implementation.

---

## 16. Model and Coding Adapter Layer

**Status: NOT STARTED AS GENERAL LAYER**  
**Priority: P1**

Keep coding/model backends interchangeable without changing V1 or Forge
lifecycle semantics. Intended classes include local models, OpenAI-compatible
local endpoints, external coding CLIs, Codex/FCC where technically and
license-compatible, Qwen workers and future compatible backends.

No backend may become a second orchestrator or introduce a mandatory recurring
paid API dependency into the platform architecture.

---

## 17. ScoreSymphony Control Plane - MVP

**Status: NOT STARTED**  
**Priority: P1 after stable runtime**

Required views eventually include platform/blockers, projects/tasks/executions,
workspaces, events/audit, tests/reviews/gates/approvals, agents/models/tools,
resources/queues, components, health and settings/policies.

### Rules

UI reads canonical runtime state, creates no second lifecycle database, shows
explicit approvals for risky actions, and every mutation remains authorized and
auditable.

---

## 18. Multi-Agent Terminal and Workflow Graph

**Status: NOT STARTED**  
**Priority: P1/P2 after Control Plane foundation**

- terminal surface such as xterm.js with strict session/agent rights;
- explicit session-to-agent mapping;
- no implicit privilege expansion;
- workflow graph such as React Flow/xyflow using actual runtime
  task/execution/review/approval relations rather than a parallel workflow state.

---

## 19. Component Manager

**Status: NOT STARTED**  
**Priority: P1 after security + Agent Registry**

Component classes: `core`, `vendored`, `managed_external`, `remote_external`.

Required lifecycle: source/version/checksum/license metadata, install, health,
update, rollback, removal, operator approval and failure isolation from core.

### Pilot acceptance

At least one managed-external coding/model component can be installed, checked,
updated, rolled back and removed without corrupting the core.

---

## 20. Research Broker

**Status: NOT STARTED**  
**Priority: P2 after stable platform**

Provider-adapter research layer for sources such as GitHub, arXiv, Crossref,
OpenAlex, Semantic Scholar, IMSLP and MusicBrainz.

Results should preserve provider/source URL, title/authors/identifier,
retrieval time, query/research run, agent, evidence reference and review status
where available.

### Acceptance

Research runs are reproducible and provenance-aware; unreviewed claims are not
silently promoted into verified domain data.

---

## 21. Secure File and Workspace Functions

**Status: NOT STARTED AS USER-FACING PLATFORM FEATURE**  
**Priority: P2**

Forge workspace lifecycle already exists, but this package refers to safe
platform/user file functions: constrained roots, upload/download, preview, diff,
versions, export, approvals and separation between user files and agent
workspaces. Large/binary files should remain outside Git.

---

## 22. Domain-Specific Workers

**Status: NOT STARTED**  
**Priority: P2**

Planned classes include Music Analysis, Corpus, Metadata, Source and Music
Research workers for harmony, cadence, form, counterpoint, motif, key, corpus
comparison, source research and metadata workflows.

Verified domain data must not be overwritten without provenance/review policy.

---

## 23. ScoreSymphony Application Integration

**Status: NOT STARTED**  
**Priority: P2**

Connect the ScoreSymphony music application through versioned APIs/jobs rather
than primary direct database coupling. Agent-generated domain information must
preserve provenance and explicit proposal/review/verified state.

### Release gate: Research / Domain Ready

Reached when provenance-aware research, secure file/workspace features and at
least one useful domain worker operate end to end through the platform.

---

## 24. Optional Deployment Topologies and Scale-Out

**Status: NOT STARTED / OPTIONAL**  
**Priority: P2 after stable reference deployment**

Possible profiles: local development, single node, multi-node, separate worker,
monitoring/backup/staging host, remote worker, specialized CPU/RAM/GPU node.

Before splitting, measure CPU, RAM, storage, I/O, network, queue latency, worker
throughput and failure impact.

Any selected profile must preserve one canonical lifecycle authority,
authenticated minimal networking, defined failure domains and no split-brain.

---

## 25. Production Hardening

**Status: NOT COMPLETE**  
**Priority: P0/P1 before Production Candidate**

Final matrix must cover:

- authentication/authorization/policies/secrets/egress/TLS;
- dependency/license/path/command/privilege checks;
- process/worker/runtime/host failures;
- replay/backup/restore/migration/rollback;
- task/worker/queue/load/RAM/disk pressure;
- external component failure;
- forbidden path/command/network/merge/deployment/privilege actions;
- Forge/Hermes/ScoreSymphony/component upgrades and rollback.

---

## 26. Documentation and Operational Readiness

**Status: ONGOING / PARTIAL**  
**Priority: continuous; complete before Production Candidate**

Developer documentation must ultimately cover architecture, ADRs, V1 contracts,
public APIs, worker/agent interfaces, component registry, security model and test
strategy.

Operator documentation must cover installation, bootstrap, start/stop, update,
backup, restore, rollback, recovery, diagnosis and runbooks.

The clone-ready baseline cleanup is part of this work package, not evidence that
all final operator documentation is finished.

---

# Release gates

## Gate A - Integrated Kernel

**Current status: IN PROGRESS**

Close Work Packages 3-7 for the complete process-level vertical slice, including
live event recovery, Forge-owned worker dispatch and durable idempotency.

## Gate B - Recoverable Runtime

**Status: NOT REACHED**

Work Package 8 proves restart/replay/idempotency/orphan/lease recovery.

## Gate C - Operable Deployment

**Status: NOT REACHED**

Work Packages 9-10 provide production security baseline and reproducible
reference deployment.

## Gate D - Controlled Multi-Agent

**Status: NOT REACHED**

Work Packages 11-15 provide observability, registry, resource controls,
additional workers and independent review.

## Gate E - Extensible Platform

**Status: NOT REACHED**

Work Packages 16-19 provide backend adapters, Control Plane, terminal/graph and
safe component management.

## Gate F - Research / Domain Ready

**Status: NOT REACHED**

Work Packages 20-23 provide provenance-aware research, secure files/workspaces,
domain workers and ScoreSymphony application integration.

## Gate G - Production Candidate

**Status: NOT REACHED**

Work Packages 24-26 plus all preceding gates pass final security, recovery,
load, agent-safety, upgrade and documentation acceptance.

---

# Fresh-repository starting backlog

The new GitHub repository should **not** copy the old issue list wholesale. Start
with only the work that is actually active and near-term.

## Milestone: Integrated Kernel

Recommended initial issues:

1. **Live Forge SSE projection into canonical V1 events**
2. **Reconnect and Historical Recovery handoff**
3. **Forge-owned deterministic Shell Worker dispatch**
4. **Durable Command Idempotency and ambiguous-submit recovery**
5. **Process-level Hermes -> Gateway -> Forge acceptance**
6. **Integrated Kernel full E2E release-gate test**
7. **Runtime Security ingress binding for authenticated principal / V1 actor**
8. **Forge authentication bootstrap and secret injection design**
9. **CI / fresh-repository required-check recreation**

Only after the Integrated Kernel gate is nearly complete should detailed issues
for later milestones be expanded. This avoids recreating the current repository's
problem of dozens of overlapping future tracking issues.

## Milestones to create now

Create real GitHub milestones, in this order:

1. Integrated Kernel
2. Recoverable Runtime
3. Operable Deployment
4. Controlled Multi-Agent
5. Extensible Platform
6. Research / Domain Ready
7. Production Candidate

Do not create parallel normal issues titled `Milestone: ...` unless a specific
release-gate tracker has a distinct purpose.

---

# Definition of Done for the clone-ready baseline

Before the current repository is archived and its working tree is used to
initialize a fresh Git repository:

- `README.md`, `ARCHITECTURE.md`, `CURRENT_STATE.md` and this roadmap describe the
  same architecture and implementation state;
- no document claims Historical Event Recovery or Shell Worker acceptance is
  still unimplemented;
- no current architecture document uses obsolete `run_id`, `start_worker`,
  `create_worktree`, `run_tests`, `merge_task`, `retry_run` or `cancel_run` as V1
  commands;
- licensing/provenance files remain intact;
- source-controlled CI/workflow files remain intact;
- repository validation is green for the baseline commit;
- the exact source commit used for the fresh repository is recorded in the new
  repository README/history note;
- old GitHub issues/PRs/branches remain in the archived repository instead of
  being imported as active planning truth.

Migration mechanics and post-create GitHub setup are defined in
`BASELINE_HANDOFF.md`.