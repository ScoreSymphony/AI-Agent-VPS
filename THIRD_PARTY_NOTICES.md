# Third-party notices

This repository contains source snapshots of the following MIT-licensed
projects. Their original license files remain in their respective directories.

## Forge

- Original project: <https://github.com/ForgeAILab/forge>
- Imported commit: `d49fac7ca6b3b1ce310c3e950aaac64a080f60a6`
- Imported path: `core/forge`
- License: MIT
- Original copyright: Copyright (c) 2026 Mai
- License file: `core/forge/LICENSE`

## Hermes Agent

- Original project: <https://github.com/NousResearch/hermes-agent>
- Imported commit: `b81383ec215400cbbc7d9768cf4ce45a19f9092a`
- Imported path: `core/hermes`
- License: MIT
- Original copyright: Copyright (c) 2025 Nous Research
- License file: `core/hermes/LICENSE`

The following upstream paths are intentionally not imported into the MIT-only
vendored core:

- `plugins/security-guidance/` (contains Apache-2.0 source)
- `tests/agent/test_restore_primary_pool_reselect.py` (Apache-2.0 header)
- `optional-skills/research/darwinian-evolver/` (contains code explicitly
  identified upstream as vendored AGPL material)
- the generated English and Chinese Darwinian Evolver skill documentation
  derived from that excluded skill

These exclusions are also machine-readable in `UPSTREAMS.yaml`.

## Managed external components

Components classified as `managed_external` are not bundled with this
repository. They retain their own licenses and are installed from their
original source only after explicit enablement. Their metadata in
`COMPONENTS.yaml` is informational and does not relicense them.
