# Upstream update policy

Forge and Hermes are reviewed snapshots, not live dependencies.

## Check

Run:

```bash
python scripts/upstream/check_updates.py
```

The command is read-only. It reports whether each upstream default branch has
moved beyond the commit pinned in `UPSTREAMS.yaml`.

## Review before import

For every candidate update:

1. Read upstream changelog, security notes, and license changes.
2. Compare the pinned commit to the candidate commit.
3. Classify changes as relevant, irrelevant, conflicting, or security-critical.
4. Run upstream's own test suite before modifying ScoreSymphony integration.
5. Import one component at a time on a dedicated branch.
6. Preserve its `LICENSE` and update `UPSTREAMS.yaml`, `COMPONENTS.yaml`, and
   `THIRD_PARTY_NOTICES.md` in the same commit.
7. Reapply and review every `excluded_paths` entry. Do not reintroduce a
   non-MIT path merely because the upstream snapshot changed.
8. Run baseline, contract, upstream, integration, and end-to-end tests.
9. Merge only after review.

Never overwrite `core/forge` or `core/hermes` from a moving branch without an
explicit commit SHA and reviewed diff.
