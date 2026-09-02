# Repository rules for agents

These rules apply to the complete repository unless a more specific nested
`AGENTS.md` adds rules for an imported upstream subtree.

## Architecture invariants

- Hermes is the sole intelligent orchestration authority.
- Forge is the deterministic execution and lifecycle engine and remains the
  canonical owner of task, execution, workspace, worker-dispatch, evidence,
  review, gate and merge state.
- Workers execute bounded tasks; they do not create competing orchestration
  hierarchies or lifecycle state.
- All Hermes-to-Forge interaction must cross a versioned ScoreSymphony
  contract in `platform/contracts` and verified public Forge interfaces.
- Do not bypass Forge lifecycle, workspace, CI, review, gate or merge controls.
- Do not introduce a direct production `Hermes -> Worker` or
  `Gateway -> Worker` path; worker dispatch must remain Forge-owned.
- Command submission is not terminal success. Preserve `CommandReceipt` versus
  terminal `command.*` event semantics.
- The V1 `actor` value is asserted command data, not authentication evidence.
- Do not describe an unimplemented integration as operational.

## Current implementation truth

Use these files as the planning and status authority, in this order:

1. `CURRENT_STATE.md` - factual implemented/partial/not-implemented status.
2. `ROADMAP.md` - dependency-ordered work packages and release gates.
3. `ARCHITECTURE.md` - ownership, contracts and system boundaries.
4. `BASELINE_HANDOFF.md` - fresh-repository migration and initial backlog.

Old GitHub issues, superseded pull requests, experimental branches and discarded
phase numbering are historical evidence only. They must not override the current
files above.

The current release gate is **Integrated Kernel**. Historical Forge event
recovery and the deterministic Shell Worker acceptance primitive are already
implemented foundations. The immediate critical path is:

1. live Forge SSE -> canonical V1 event projection;
2. reconnect / `events.resync_required` / historical resynchronization;
3. Forge-owned deterministic Shell Worker dispatch;
4. durable Forge-owned command idempotency and ambiguous-submit recovery;
5. process-level and full Hermes -> Gateway -> Forge -> Worker E2E acceptance.

Security persistence/enforcement and repository/deployment hygiene may proceed
in parallel when they do not create a competing lifecycle boundary.

## Source and license boundaries

- New ScoreSymphony source code is MIT-licensed.
- Vendored source must be repository-compatible, retain provenance and license
  text, and follow the declared integration class.
- Non-MIT tools must be `managed_external` or `remote_external` and communicate
  through a process boundary such as CLI, MCP, HTTP, or another documented IPC.
- Do not copy external component source into this repository merely to simplify
  integration.
- Preserve `UPSTREAMS.yaml`, `COMPONENTS.yaml`, and
  `THIRD_PARTY_NOTICES.md` together whenever provenance changes.
- Preserve top-level and nested upstream license/copyright notices.
- Never change an upstream pin silently.

## Change workflow

- Work on a branch and do not merge directly to `main`.
- Add or update tests for contract, policy, registry, transport, recovery and
  lifecycle changes.
- Keep `CURRENT_STATE.md` factual and current whenever implementation status
  changes.
- Update `ROADMAP.md` only when dependencies, acceptance criteria or release-gate
  status actually change; do not use it as a changelog.
- Do not use the discarded phase-number model. Describe work by components,
  dependencies, risks and acceptance criteria.
- Keep secrets out of Git. Commit only documented placeholders in
  `.env.example`.
- Ambiguous command submissions must not be blindly retried until durable
  Forge-owned idempotency/recovery is implemented and proven.

## Clone-ready baseline rule

This historical repository is being prepared as the source for a fresh active
GitHub repository. The new repository must be initialized from the verified
`main` working tree **without copying the old `.git` directory**.

When preparing or validating the handoff:

- preserve all tracked source, tests, documentation, CI workflow files,
  licenses, `UPSTREAMS.yaml`, `COMPONENTS.yaml` and
  `THIRD_PARTY_NOTICES.md`;
- do not copy old issues, PRs, feature branches or experimental Git history as
  active planning state;
- recreate GitHub-hosted branch/ruleset/required-check/security settings in the
  fresh repository;
- use real GitHub milestones in the new repository rather than duplicate normal
  issues named `Milestone: ...`;
- populate only the actionable Integrated Kernel backlog initially; later work
  remains documented in `ROADMAP.md` until it becomes actionable;
- record the final archived source commit SHA in the fresh repository as defined
  by `BASELINE_HANDOFF.md`.

## Initial vertical slice

Until `CURRENT_STATE.md` marks **Integrated Kernel** complete, optimize for one
verified vertical slice:

`user -> Hermes -> ScoreSymphony Gateway/V1 -> Forge -> Forge-owned worker dispatch -> shell worker -> evidence/tests -> review/gates -> terminal Forge event -> ScoreSymphony V1 -> Hermes`

Additional agents, model providers, research tools, monitoring applications,
Control Plane work and multi-VPS distribution must not block this first slice.
