# License policy

This file is an engineering policy, not legal advice.

## Repository source

- New ScoreSymphony source: MIT.
- Imported or vendored source: MIT only, with original license and provenance.
- Model weights and mutable external installations: never committed.

## External components

External open-source tools may use other licenses when all of the following are
true:

1. They are classified as `managed_external` or `remote_external`.
2. Their source is not copied into the ScoreSymphony repository.
3. Their original license is displayed and retained during installation.
4. Communication uses a documented process boundary such as CLI, MCP, HTTP, or
   another IPC mechanism.
5. Redistribution requirements are reviewed before ScoreSymphony distributes
   images or archives containing the component.

## Default dependency allowlist

Permissive dependency licenses may be approved when recorded by the dependency
audit: MIT, ISC, BSD-2-Clause, BSD-3-Clause, and Apache-2.0.

Copyleft or source-available dependencies are not automatically forbidden as
separate external programs, but they require an explicit boundary and
distribution review. They must not be silently linked into or vendored within
the MIT core.

## CI rule

`scripts/validate_baseline.py` rejects a bundled component whose declared
license is not MIT. A future dependency scanner will extend this check to
transitive package locks.
