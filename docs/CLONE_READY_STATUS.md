# Clone-ready baseline status

Prepared: **2026-09-02**

This document is a compact transfer status for initializing the next active
ScoreSymphony Agent Platform repository from the verified working tree of this
historical repository.

It does not replace `CURRENT_STATE.md`, `ROADMAP.md`, `ARCHITECTURE.md` or
`BASELINE_HANDOFF.md`. Those remain the detailed authorities.

## Transfer decision

The platform is **ready to be transferred as a development baseline**, but it is
**not production-ready** and the **Integrated Kernel release gate is still in
progress**.

The transfer is a Git/project-management reset, not a code rewrite. Use the full
tracked working tree from the final verified `main` commit and initialize a new
Git history without the old `.git` directory.

## Baseline that is already implemented

### Architecture and contracts

- Hermes is the sole intelligent orchestrator.
- Forge is the canonical deterministic lifecycle authority.
- ScoreSymphony V1 uses Forge-aligned task/execution terminology.
- Command submission is separated from terminal command outcome.
- Project scope, task versions, correlation and causation concepts exist.
- Private Forge database/services are not part of the Hermes integration.

### Forge integration

- Authenticated historical Forge Domain Event Read is implemented and tested.
- Historical recovery uses an exclusive sequence cursor and ordered public DTOs.
- Current V1 commands map to verified public Forge HTTP operations.
- ScoreSymphony has an authenticated Forge HTTP transport and recovery adapter.

### ScoreSymphony gateway / Hermes side

- Authenticated ScoreSymphony Gateway exists.
- Command submission and historical event reads exist.
- Liveness/readiness behavior exists.
- Hermes-side Gateway client exists.
- `scoresymphony-hermes` CLI exists.
- In-process Hermes -> Gateway -> Forge integration acceptance exists.

### Worker foundation

- Deterministic Shell Worker acceptance primitive exists.
- Executable allowlisting and workspace confinement exist.
- Timeout, failure, cancellation and explicit retry behavior are covered.
- Declared write-path policy and deterministic changed-path evidence exist.

### Security foundation

- Principal/credential/resource/scope contracts exist.
- Default-deny policy semantics exist.
- Approval operation/policy binding, expiry and consumed-state semantics exist.
- `actor` is explicitly treated as asserted data rather than authentication.

### Repository / provenance / CI

- Forge and Hermes source snapshots are pinned.
- Upstream provenance is recorded in `UPSTREAMS.yaml`.
- Component metadata is recorded in `COMPONENTS.yaml`.
- Third-party notices and nested license files are preserved.
- Python/Pytest, deployment/Compose and Forge Rust CI foundations exist.
- Governance templates and the non-root Gateway image exist.

## What is partially implemented

- Forge Adapter: public command mapping is advanced, but durable idempotency and
  complete live-event behavior are still open.
- HTTP/SSE runtime: authenticated HTTP and historical recovery exist, but live
  SSE/reconnect/resync/catch-up handoff remain open.
- Hermes integration: client/CLI exists, but process-level live/terminal E2E is
  not complete.
- Integrated Kernel: in-process integration exists, but Forge-owned Worker
  dispatch and complete lifecycle E2E are not complete.
- Recovery: historical recovery exists, but durable command deduplication,
  restart/orphan/lease/replay behavior remains incomplete.
- Security: contracts are present, but production principal binding, persistent
  RBAC/policies/approvals/audit and enforcement wiring remain incomplete.
- Deployment: validation and container foundations exist, but production auth,
  secret bootstrap, full Compose wiring, backup/restore and runbooks remain open.
- Observability: baseline exists, but lifecycle metrics, correlation coverage,
  alerts and operator diagnostics need expansion.

## Immediate work after the fresh repository is created

The first active milestone must be **Integrated Kernel**.

Create and execute these issues in dependency order:

1. **IK-1 Live Forge SSE projection into canonical V1 events**
   - authenticated SSE consumption;
   - supported public lifecycle event parsing;
   - V1 projection;
   - sequence/correlation/causation preservation;
   - invalid-upstream tests.

2. **IK-2 Reconnect and Historical Recovery handoff**
   - SSE reconnect;
   - `events.resync_required` handling;
   - historical catch-up;
   - race-safe catch-up -> live transition;
   - overlap deduplication;
   - cursor advance only after successful processing.

3. **IK-3 Forge-owned deterministic Shell Worker dispatch**
   - dispatch only through Forge lifecycle;
   - Forge-created isolated workspace;
   - worker policy/evidence integration;
   - success/failure/timeout/cancel/retry tests;
   - no Hermes/Gateway direct worker bypass.

4. **IK-4 Durable Command Idempotency and ambiguous-submit recovery**
   - Forge-owned durable deduplication identity/state;
   - persisted correlation needed to resolve ambiguous submissions;
   - duplicate-delivery tests;
   - no blind retries on unresolved transport/server ambiguity.

5. **IK-5 Process-level Hermes -> Gateway -> Forge acceptance**
   - real Gateway process boundary;
   - Hermes CLI/client process path;
   - authenticated Forge boundary;
   - command receipt and event recovery validation;
   - process failure diagnostics.

6. **IK-6 Integrated Kernel full E2E release-gate test**
   - Hermes command;
   - Gateway;
   - Forge task/execution/workspace;
   - Forge-owned worker dispatch;
   - fixture change/evidence;
   - review/gates;
   - terminal V1 event back to Hermes;
   - duplicate protection;
   - stale-version rejection;
   - live disconnect + historical resync.

7. **IK-7 Runtime principal binding and security gate integration**
   - bind authenticated principal to `actor` assertion;
   - default-deny authorization;
   - protected operation digest binding;
   - negative enforcement tests.

8. **IK-8 Forge authentication bootstrap and secret injection contract**
   - credential provisioning boundary;
   - Gateway -> Forge secret injection/rotation;
   - no repository/log credential leakage;
   - enough definition for later production Compose wiring.

9. **IK-9 Fresh-repository governance and required checks**
   - recreate `main` protection/ruleset;
   - observe and require actual CI check names;
   - validate workflows/templates;
   - configure available dependency/license/security scanning.

## Release path after Integrated Kernel

After the Integrated Kernel acceptance suite is green, proceed in this order:

1. Recoverable Runtime.
2. Operable Deployment.
3. Controlled Multi-Agent.
4. Extensible Platform.
5. Research / Domain Ready.
6. Production Candidate.

Do not pre-create a second giant issue backlog. Keep later work in `ROADMAP.md`
until the preceding release gate is near completion and the work becomes
concrete enough for actionable issues.

## Files that must survive the history reset

Copy the entire tracked working tree. In particular preserve:

- `core/forge/` and all required upstream notices/licenses;
- `core/hermes/` and all required upstream notices/licenses;
- `platform/`, `agents/`, `contracts/`, `config/`, `scripts/`, `tests/`, `docs/`;
- `.github/` source-controlled workflows/templates;
- build/deployment manifests and Dockerfiles;
- `README.md`;
- `ARCHITECTURE.md`;
- `CURRENT_STATE.md`;
- `ROADMAP.md`;
- `AGENTS.md`;
- `BASELINE_HANDOFF.md`;
- `UPSTREAMS.yaml`;
- `COMPONENTS.yaml`;
- `THIRD_PARTY_NOTICES.md`;
- all top-level and nested license/copyright files.

Do **not** copy the old `.git` directory into the fresh active repository.

## GitHub state that must be recreated instead of copied

- branch protection / repository rulesets;
- required checks;
- Actions permissions/settings;
- repository/environment secrets and variables;
- milestones;
- actionable issues;
- optional Projects/boards;
- security/dependency-scanning settings.

Old branches, issues, pull requests and workflow history remain in the archived
repository as historical evidence.

## Final source-repository acceptance before cloning

The historical repository is ready to serve as the source snapshot only when:

- all reconciliation/handoff changes are merged into `main`;
- repository CI is green on the exact final source commit;
- the final source commit SHA is recorded;
- `README.md`, `ARCHITECTURE.md`, `CURRENT_STATE.md`, `ROADMAP.md`, `AGENTS.md` and
  `BASELINE_HANDOFF.md` agree on the current state;
- upstream pins, component metadata, third-party notices and license files are
  intact;
- no real credentials are present;
- the new repository name is chosen and empty/ready for the baseline push.

The fresh repository's first commit should represent this verified working tree
and should record/link the archived source repository and exact source SHA for
historical provenance.
