# Repository rules for agents

These rules apply to the complete repository unless a more specific nested
`AGENTS.md` adds rules for an imported upstream subtree.

## Architecture invariants

- Hermes is the sole intelligent orchestration authority.
- Forge is the deterministic execution and lifecycle engine.
- Workers execute bounded tasks; they do not create competing orchestration
  hierarchies.
- All Hermes-to-Forge interaction must cross a versioned ScoreSymphony
  contract in `platform/contracts`.
- Do not bypass Forge lifecycle, worktree, CI, review, or merge controls.
- Do not describe an unimplemented integration as operational.

## Source and license boundaries

- New ScoreSymphony source code is MIT-licensed.
- Vendored source must be MIT-licensed and retain provenance and license text.
- Non-MIT tools must be `managed_external` or `remote_external` and communicate
  through a process boundary such as CLI, MCP, HTTP, or another documented IPC.
- Do not copy external component source into this repository.
- Preserve `UPSTREAMS.yaml`, `COMPONENTS.yaml`, and
  `THIRD_PARTY_NOTICES.md` together whenever provenance changes.
- Never change an upstream pin silently.

## Change workflow

- Work on a branch and do not merge directly to `main`.
- Add or update tests for contract, policy, registry, and lifecycle changes.
- Keep `CURRENT_STATE.md` factual and current.
- Do not use the discarded phase-number model. Describe work by components,
  dependencies, risks, and acceptance criteria.
- Keep secrets out of Git. Commit only documented placeholders in
  `.env.example`.

## Initial milestone

Until `CURRENT_STATE.md` says otherwise, optimize for one vertical slice:

`user -> Hermes -> ScoreSymphony contract -> Forge -> shell worker -> tests -> review -> merge -> Hermes result`

Additional agents, model providers, research tools, monitoring applications,
and multi-VPS distribution must not block this first slice.
