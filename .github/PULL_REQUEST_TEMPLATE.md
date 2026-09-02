## Goal

<!-- What concrete problem or roadmap item does this PR address? -->

Linked issue/work item:

## Scope

<!-- What is intentionally included and excluded? -->

## Architecture impact

- [ ] Hermes remains the sole intelligent orchestrator.
- [ ] Forge remains the lifecycle authority for task/execution/workspace/review/gate/merge state.
- [ ] No new competing lifecycle state or private Forge database dependency is introduced.
- [ ] Versioned ScoreSymphony contracts/public interfaces are preserved or intentionally updated.

Describe any architecture change:

## Validation

Commands/checks run:

- [ ] Relevant unit tests
- [ ] Relevant integration/contract tests
- [ ] Repository validation
- [ ] E2E tests, when an authoritative E2E suite exists and is affected
- [ ] Additional checks listed below

Required repository gates after CI:

- [ ] `Platform quality / required-quality-gate`
- [ ] `Security and dependency policy / required-security-gate`

Results/evidence:

## License and provenance impact

- [ ] No dependency, vendored-source, component, or upstream provenance change.
- [ ] Any provenance change updates the required registry/notices together.
- [ ] No incompatible source has been copied into the repository.

Details if applicable:

## Security impact

- [ ] No secrets or credentials are included.
- [ ] Authentication/authorization and least-privilege implications were considered.
- [ ] Resource bounds, input validation, and failure behavior were considered where applicable.

Details if applicable:

## Migration / compatibility

<!-- Runtime, schema, config, API, deployment, or upgrade implications. Write "None" when not applicable. -->

## Rollback

<!-- How can this change be reverted or disabled safely? -->

## Documentation / current state

- [ ] `CURRENT_STATE.md` remains factual after this change.
- [ ] Roadmap/API/runbook/changelog documentation was updated where behavior changed.
- [ ] No documentation change is required (explain why below).

Notes:
