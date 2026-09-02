# Repository governance and required CI policy

This policy defines the repository-level merge, CI, security, and supply-chain rules for the Agent Platform monorepo.

## 1. Protected default branch

`main` is the production/default integration branch.

Repository changes must reach `main` through a traceable pull request. Direct feature work on `main`, force-pushes, and branch deletion must be blocked by the repository ruleset or branch-protection settings.

Emergency changes still require a pull request. A bypass, when administratively unavoidable, must be documented in the related issue/PR and followed by a normal review of the resulting state.

## 2. Required pull-request checks

The following checks are the repository-level merge gates:

- `Platform quality / required-quality-gate`
- `Security and dependency policy / required-security-gate`

The quality gate currently aggregates:

- repository baseline validation (`scripts/validate_baseline.py`),
- deployment/Compose contract validation (`scripts/validate_deployment.py` and Compose syntax),
- Python unit, contract, integration, and regression tests (`pytest -q`),
- Forge Rust compilation and historical domain-event API tests.

The security gate currently aggregates:

- tracked-file secret scanning,
- pull-request dependency vulnerability review,
- dependency license allowlist enforcement for newly introduced dependencies.

A failing required gate must block merge.

### E2E gate rule

No repository-level E2E gate is claimed until a real executable E2E suite exists. When an E2E suite is introduced, its workflow/job must be added to the required merge gates in the same PR that makes the suite authoritative. Documentation must not describe a planned E2E check as already enforced.

## 3. GitHub repository settings

For `main`, configure a ruleset or branch protection rule with at least:

1. require a pull request before merging,
2. require the two status checks listed above,
3. block force pushes,
4. block deletion of `main`,
5. require conversations/reviews to be resolved when review is used,
6. prevent an administrator bypass from becoming the normal development path.

Where the GitHub plan/repository features support them, enable:

- dependency graph,
- Dependency Review,
- Secret Scanning,
- Secret Scanning push protection.

The in-repository secret scanner is a defense-in-depth control; it is not a replacement for GitHub Secret Scanning/push protection.

## 4. Pull-request evidence

Every PR must state:

- the concrete goal and linked issue/work item,
- scope and exclusions,
- architecture impact,
- tests/checks and their evidence,
- license/provenance impact,
- security impact,
- migration/compatibility impact,
- rollback path,
- documentation/current-state impact.

Architecture and upstream changes must be reviewable from the PR history. Silent upstream pin changes are not allowed.

## 5. Issue templates

Use the repository templates according to the work type:

- `implementation.md` for implementation work,
- `adr.md` for architecture decisions,
- `upstream-update.md` for Forge/Hermes/other upstream changes,
- `security.md` for hardening/security work.

Security issues must not contain live credentials, private keys, tokens, or sensitive production data.

## 6. GitHub Actions supply-chain policy

Third-party and GitHub-maintained actions must be pinned to a full commit SHA whenever practical. Keep a human-readable version comment next to the SHA, for example:

```yaml
uses: actions/checkout@<full-commit-sha> # v4
```

Version comments are informational; the commit SHA is the executable pin. Updating an action pin is a normal reviewed dependency change.

## 7. Secrets and CI logs

Real credentials must never be committed to Git, example configuration, fixtures, screenshots, issue bodies, PR bodies, test output, or CI logs.

Local `.env` variants are ignored. `.env.example` may contain names and non-secret placeholders only. CI failures must report the file/finding type without printing the secret value.

## 8. License policy

The repository license boundary remains defined by `LICENSE_POLICY.md`, `COMPONENTS.yaml`, `UPSTREAMS.yaml`, and the third-party notices.

For newly introduced dependencies, the default CI allowlist is:

- MIT
- ISC
- BSD-2-Clause
- BSD-3-Clause
- Apache-2.0

Anything outside the allowlist requires explicit review and an intentional policy/boundary update rather than a silent bypass.

## 9. Rollback

Governance/CI changes are rolled back through a pull request like any other repository change. If a gate itself is broken and blocks all PRs, the repair must be narrowly scoped, documented, and restore enforcement rather than permanently weakening it.
