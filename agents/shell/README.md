# Shell worker

The shell worker is the first deterministic fixture worker used to prove the complete
Hermes-to-Forge lifecycle. It is deliberately a bounded reference process runner, not a
general unrestricted shell agent and not a security sandbox.

## Current implementation

The transport-neutral worker core lives in `src/scoresymphony_workers/shell.py`.
It can be developed and tested independently from the Forge event/recovery API.

The worker currently guarantees:

- explicit argv execution with `shell=False`; command strings and shell expansion are not used,
- absolute, explicitly allowlisted executable paths,
- a working directory that must remain inside the configured workspace root,
- a deterministic baseline process environment (`UTC`, fixed locale, Python hash seed and UTF-8),
- a configured maximum timeout per invocation,
- normalized UTF-8 stdout/stderr and structured success/failure/timeout evidence,
- no Forge event publication, approval decisions, merge operations, or deployment actions.

The runtime/Forge integration layer remains responsible for orchestration lifecycle events,
approvals, durable state, retries/recovery, stronger process isolation, and policy enforcement.
Keeping those responsibilities outside this worker prevents the parallel worker track from
coupling itself to an unfinished Forge recovery interface.

## Fixture repository

`tests/fixtures/shell_worker_repository/` is a small deterministic repository-shaped workspace.
Tests copy it into a temporary workspace before execution. Its fixture command covers stable
rendering, literal argument handling, non-zero exits, timeouts, and deterministic environment
inspection.

## Acceptance tests

`tests/test_shell_worker.py` verifies that:

1. the same command in two clean copies of the fixture repository produces the same result and
   output bytes,
2. shell metacharacters are passed literally rather than interpreted,
3. non-zero exits and timeouts produce structured results,
4. the deterministic environment is present,
5. workspace traversal is rejected,
6. non-allowlisted and relative executable names are rejected, and
7. a command cannot exceed the worker's configured timeout ceiling.

This completes the independent reference-worker slice. Wiring it into Hermes/Forge belongs to
the later integration wave once the runtime boundary is stable.
