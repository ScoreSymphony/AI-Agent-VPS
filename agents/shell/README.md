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
- explicit worker-level write-path allowlists plus per-command declared write paths,
- workspace change evidence through stable `changed_paths` snapshots,
- a deterministic baseline process environment (`UTC`, fixed locale, Python hash seed and UTF-8),
- a configured maximum timeout per invocation,
- cooperative cancellation through a caller-provided `threading.Event`,
- normalized UTF-8 stdout/stderr and structured success/failure/timeout/cancel evidence,
- no Forge event publication, approval decisions, merge operations, or deployment actions.

A command that declares a write path outside the workspace or outside the worker allowlist is
rejected before process start. After execution, workspace changes are compared with the declared
write set; an unexpected workspace change produces `path_policy_violation` evidence. The Forge
workspace remains the outer isolation boundary and should be discarded on failed/policy-violating
attempts.

The runtime/Forge integration layer remains responsible for orchestration lifecycle events,
approvals, durable state, retry decisions/recovery, stronger process isolation, and policy
enforcement. A retry is therefore a new explicit worker invocation rather than an autonomous
worker loop. Keeping those responsibilities outside this worker prevents the parallel worker
track from coupling itself to an unfinished Forge recovery interface.

## Fixture repository

`tests/fixtures/shell_worker_repository/` is a small deterministic repository-shaped workspace.
Tests copy it into a temporary workspace before execution. Its fixture command covers stable
rendering, literal argument handling, non-zero exits, timeouts, cancellation, deterministic
environment inspection, and a stateful fail-once case used to prove an explicit retry attempt.

## Acceptance tests

`tests/test_shell_worker.py` verifies that:

1. the same command in two clean copies of the fixture repository produces the same result and
   output bytes,
2. the predictable render changes only the declared/allowlisted output path,
3. shell metacharacters are passed literally rather than interpreted,
4. non-zero exits, timeouts and cancellation produce structured results,
5. a failed retryable attempt can be invoked again deterministically and succeed,
6. the deterministic environment is present,
7. workspace traversal and disallowed declared write paths are rejected before execution,
8. undeclared workspace changes are surfaced as `path_policy_violation`,
9. non-allowlisted and relative executable names are rejected, and
10. a command cannot exceed the worker's configured timeout ceiling.

This completes the independent reference-worker acceptance surface. Wiring it into Hermes/Forge
belongs to the integrated-kernel work once the runtime boundary is stable.
