## Summary

Describe what this PR changes and which platform workstream it belongs to.

## Scope boundaries

- [ ] The PR changes only the intended component/workstream.
- [ ] Cross-component contracts are documented before they are consumed.
- [ ] No unfinished Forge recovery/history interface is treated as stable.
- [ ] Vendored upstream code is changed only when the PR explicitly owns that upstream scope.

## Verification

- [ ] `make quality`
- [ ] `make compose-check` when deployment files changed
- [ ] New behavior has regression tests or a documented reason why a test is not applicable

## Operational impact

Describe changes to ports, volumes, environment variables, healthchecks, logs, resource use, migration, or rollback. Write `none` when there is no operational impact.
