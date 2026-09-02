# ScoreSymphony Agent Platform - Baseline Handoff

Prepared: **2026-09-02**

## 1. Purpose

This document defines how to turn the verified final `main` working tree of the
historical `ScoreSymphony/AI-Agent-VPS` repository into a **fresh GitHub
repository with a new Git history**, while preserving all working code, tests,
documentation, licenses and upstream provenance.

The historical repository should remain available as an archived development
record. Its old branches, pull requests, issues, experiments and intermediate
fixes are intentionally **not** the active planning truth of the new repository.

This is a history/project-management reset, **not a rewrite of the platform**.

## 2. What the baseline contains

The snapshot being handed off already contains these major foundations:

- pinned Forge and Hermes upstream snapshots;
- Forge-aligned ScoreSymphony V1 contracts;
- authenticated Historical Forge Domain Event Read;
- ScoreSymphony Forge command/recovery adapter foundation;
- authenticated ScoreSymphony Gateway;
- Hermes-side Gateway client and `scoresymphony-hermes` CLI;
- deterministic Shell Worker acceptance primitive;
- shared Security Contracts and reference policy/approval semantics;
- in-process Hermes/Gateway/Forge historical integration acceptance;
- CI/governance/deployment-validation foundations;
- source-controlled upstream/license provenance.

It does **not** yet constitute the complete Integrated Kernel or a production
system. The exact status is in `CURRENT_STATE.md`; the remaining path is in
`ROADMAP.md`.

## 3. What must be copied into the fresh repository

Use the complete tracked **working tree** from the final verified `main` commit.
Do not manually cherry-pick only selected directories unless a later audit finds
a concrete reason to exclude something.

In particular, preserve:

- ScoreSymphony source code;
- `core/forge/` snapshot and its required notices/licenses;
- `core/hermes/` snapshot and its required notices/licenses;
- `platform/`, `agents/`, `contracts/`, `config/`, `scripts/`, `tests/`, `docs/`;
- Dockerfiles and `compose.yaml`;
- `.github/` workflow/template source files;
- `pyproject.toml` and other build/config manifests;
- `README.md`;
- `ARCHITECTURE.md`;
- `CURRENT_STATE.md`;
- `ROADMAP.md`;
- `AGENTS.md`;
- `UPSTREAMS.yaml`;
- `THIRD_PARTY_NOTICES.md`;
- top-level and nested `LICENSE`/copyright files;
- this `BASELINE_HANDOFF.md`.

Do not delete a file merely because Git history is being reset. Git history and
license/provenance obligations are separate concerns.

## 4. What must NOT be copied as active repository state

The fresh repository should not inherit the old `.git` directory.

Therefore the following historical Git/GitHub state stays with the archived
repository:

- old commit graph as the active history;
- old feature/Qwen/cleanup/superseded branches;
- old pull requests;
- old issue numbering and overlapping tracking issues;
- old workflow-run history;
- old review conversations;
- obsolete release-gate tracker issues;
- experimental intermediate repository states.

The archived repository remains the evidence source when old history needs to be
consulted.

## 5. Pre-handoff acceptance checklist

Before taking the final snapshot from the historical repository:

1. Merge the clone-ready documentation/reconciliation PR into `main`.
2. Confirm `main` has no unintended uncommitted state (when working locally).
3. Run the repository quality gates.
4. Confirm upstream/license/provenance files exist unchanged unless deliberately
   updated.
5. Record the exact final historical source commit SHA.
6. Confirm `README.md`, `ARCHITECTURE.md`, `CURRENT_STATE.md` and `ROADMAP.md`
   agree about what is implemented and what remains.
7. Confirm obsolete V1 command vocabulary is not presented as current
   architecture.
8. Confirm no real secrets/credentials are present in tracked files.

Recommended validation commands:

```bash
make quality
make compose-check
```

Use the repository CI as the authoritative full check, including Forge Rust
validation.

## 6. Recommended fresh-history procedure

Choose the final new repository name first. The commands below intentionally
remove only Git history, not project files.

```bash
git clone https://github.com/ScoreSymphony/AI-Agent-VPS.git scoresymphony-platform-baseline
cd scoresymphony-platform-baseline

git switch main
git pull --ff-only

make quality
make compose-check

# Record this value before deleting .git.
git rev-parse HEAD

rm -rf .git
git init -b main

git add .
git commit -m "chore: establish ScoreSymphony Agent Platform baseline"

git remote add origin https://github.com/ScoreSymphony/<NEW-REPOSITORY>.git
git push -u origin main
```

On Windows PowerShell, replace the `.git` removal command with the appropriate
PowerShell removal command, for example:

```powershell
Remove-Item -Recurse -Force .git
```

Do not run the destructive `.git` removal inside the only copy of the historical
repository unless the archived GitHub remote has already been verified.

## 7. Required provenance note in the new repository

After the new repository exists, add the exact archived source SHA to its README
or a dedicated provenance section. Use wording equivalent to:

```text
Repository history note

This repository was initialized on 2026-09-02 from the verified working tree of
ScoreSymphony/AI-Agent-VPS at archived source commit <SOURCE_SHA>.
The complete pre-baseline development history remains available in the archived
source repository. Upstream provenance and licenses are preserved in
UPSTREAMS.yaml, THIRD_PARTY_NOTICES.md and the corresponding license files.
```

Replace `<SOURCE_SHA>` with the actual final `main` commit after the baseline
reconciliation PR is merged.

## 8. GitHub configuration that must be recreated

Copying files does **not** copy GitHub-hosted repository configuration. Configure
these explicitly in the new repository.

### Branch / merge governance

- protect `main` or apply the chosen repository ruleset;
- require pull requests for productive changes;
- require the relevant quality checks before merge;
- prevent accidental force-push/deletion of protected refs as appropriate;
- choose allowed merge methods deliberately;
- keep architecture/security changes reviewable and traceable.

### Actions / CI

- enable the required Actions permissions;
- verify all source-controlled workflows run in the new repository;
- restore required-check names only after observing the actual workflow checks;
- verify Python, Compose/deployment and Forge Rust gates;
- configure dependency/security scanning features available to the repository.

### Secrets / variables

Do not copy secrets through Git.

Recreate required repository/environment secrets and variables through GitHub or
the intended deployment secret mechanism. Production credentials must not be
created merely to make the fresh repository look complete; Forge auth bootstrap
and production secret injection remain open roadmap work.

## 9. Fresh GitHub milestone structure

Use **real GitHub milestones**, not duplicate normal issues whose titles start
with `Milestone:`.

Create these milestones in dependency order:

1. **Integrated Kernel**
2. **Recoverable Runtime**
3. **Operable Deployment**
4. **Controlled Multi-Agent**
5. **Extensible Platform**
6. **Research / Domain Ready**
7. **Production Candidate**

Later milestones may exist from day one, but detailed future issues should be
created only when they are actionable. This keeps GitHub aligned with real
implementation progress.

## 10. Initial issue backlog for the fresh repository

### Milestone: Integrated Kernel

Create the following actionable issues first.

#### IK-1 - Live Forge SSE projection into canonical V1 events

Scope:

- authenticated public Forge SSE consumption;
- supported lifecycle event parsing;
- canonical V1 projection;
- sequence/correlation/causation preservation;
- explicit invalid-upstream failure behavior;
- focused unit/integration tests.

#### IK-2 - Reconnect and Historical Recovery handoff

Scope:

- reconnect after SSE disconnect;
- `events.resync_required` handling;
- Historical Read catch-up using the existing API;
- race-safe catch-up -> live handoff;
- overlap deduplication;
- cursor advancement only after successful processing;
- gap/duplicate regression tests.

#### IK-3 - Forge-owned deterministic Shell Worker dispatch

Scope:

- Forge lifecycle owns dispatch;
- Forge-created isolated workspace;
- allowed executable/path policies;
- success/failure/timeout/cancel/retry behavior;
- worker evidence/changed-path return into Forge-owned state;
- no Hermes/Gateway direct worker bypass.

#### IK-4 - Durable Command Idempotency and ambiguous-submit recovery

Scope:

- Forge-owned durable deduplication identity;
- persisted correlation needed to resolve ambiguous submissions;
- duplicate delivery acceptance tests;
- network/server timeout ambiguity handling;
- explicit rule preventing blind retry until prior outcome is resolved.

#### IK-5 - Process-level Hermes -> Gateway -> Forge acceptance

Scope:

- launch/use real Gateway process;
- use Hermes-side CLI/client process boundary;
- authenticated Forge boundary;
- command receipt validation;
- event recovery validation;
- process failure diagnostics.

#### IK-6 - Integrated Kernel full E2E release-gate test

Scope:

- Hermes command;
- Gateway;
- Forge task/execution/workspace;
- Forge-owned worker dispatch;
- fixture change/evidence;
- review/gate behavior;
- terminal event to Hermes;
- duplicate command protection;
- stale version rejection;
- live disconnect + historical resync.

#### IK-7 - Runtime principal binding and security gate integration

Scope:

- bind authenticated principal to asserted V1 `actor`;
- operation digest binding;
- default-deny authorization before protected adapter/dispatch actions;
- negative tests proving denied requests never reach Forge/worker paths.

#### IK-8 - Forge authentication bootstrap and secret injection contract

Scope:

- define how Forge credentials are provisioned at bootstrap;
- define Gateway -> Forge secret injection/rotation boundary;
- prohibit credentials in repository/logs;
- make the result sufficient for later production Compose wiring.

#### IK-9 - Fresh-repository governance and required checks

Scope:

- validate Actions workflows after history reset;
- configure `main` rules/protection;
- establish required check names;
- verify issue/PR templates;
- verify dependency/license/security scanning behavior;
- document any repository-setting differences from the archive.

### Do not pre-create a duplicate mega-backlog

The complete future work exists in `ROADMAP.md`. Detailed issues for Recoverable
Runtime and later gates should be expanded when the preceding gate is close
enough that those issues are actionable and technically grounded.

## 11. What should be considered done at handoff

The baseline handoff itself is complete when:

- the reconciliation changes are merged to historical `main`;
- CI/quality gates are green for that source commit;
- the exact source SHA is recorded;
- a fresh repository is initialized from the working tree without `.git`;
- the fresh repo's initial baseline commit is pushed;
- GitHub branch/check/security settings are recreated;
- real milestones are created;
- only the actionable Integrated Kernel backlog is populated;
- the old repository is archived and points to the new active repository;
- the new repository links back to the archive for historical development
  context;
- upstream provenance and all required license/copyright notices remain intact.

## 12. What should happen immediately after handoff

Do not spend the first fresh-repo work cycle reorganizing architecture again.
Start with the current critical path:

1. live Forge SSE projection;
2. reconnect + historical resynchronization;
3. Forge-owned Shell Worker dispatch;
4. durable Command Idempotency;
5. process-level/full Integrated Kernel E2E.

Security persistence/enforcement and repository/deployment hygiene can proceed in
parallel when they do not create conflicting edits to the same runtime boundary.

The next architectural redesign should occur only if implementation evidence
shows a concrete contract, ownership, security or operability defect.