# ADR-0002: V1-to-Forge command and recovery mapping

- Status: Accepted
- Date: 2026-09-02
- Scope: Preconditions for the first Forge adapter

## Context

The first V1 draft predated a command-by-command audit against the pinned Forge
public API. That audit showed several names that implied the wrong ownership or
had no stable public Forge operation. The contract is not yet externally frozen,
so the safer choice is to correct V1 before building adapters or clients on top
of those assumptions.

## Decision: lifecycle-aligned command vocabulary

V1 uses only commands that have a verified Forge lifecycle meaning:

| V1 command | Forge public operation | Contract rule |
| --- | --- | --- |
| `create_task` | `POST /api/v1/projects/{project_id}/tasks` | `payload.project_id` is required; Forge allocates the task id. |
| `update_task` | `PATCH /api/v1/tasks/{task_id}` | `payload.version` is required with at least one mutation. |
| `start_task` | `POST /api/v1/tasks/{task_id}/start` | expected task `version` is required. |
| `submit_task` | `POST /api/v1/tasks/{task_id}/submit` | expected task `version` is required; Forge decides the resulting workflow transition. |
| `request_changes_task` | `POST /api/v1/tasks/{task_id}/request-changes` | expected task `version` and `reason` are required. |
| `approve_task` | `POST /api/v1/tasks/{task_id}/approve` | expected task `version` is required. |
| `cancel_task` | `POST /api/v1/tasks/{task_id}/cancel` | expected task `version` is required. |
| `retry_execution` | `POST /api/v1/executions/{execution_id}/re-execute` | `task_id` and `execution_id` identify the execution context. |
| `cancel_execution` | `POST /api/v1/executions/{execution_id}/cancel` | `task_id` and `execution_id` identify the execution context. |

The envelope field previously named `run_id` is renamed to `execution_id` before
V1 is frozen because Forge's canonical runtime entity is an execution.

The following first-draft commands are removed:

- `start_worker`: Forge starts task work and owns worker/agent dispatch;
- `create_worktree`: workspace/worktree creation is a Forge lifecycle effect;
- `inspect_worktree`: inspection is a query/read operation;
- `run_tests`: tests are executed by Forge workflow/review machinery rather
  than through a generic public test command;
- `request_review`: `submit_task` expresses the intent while Forge decides the
  actual workflow transition;
- `merge_task`: merge is a gated Forge lifecycle result, not an Hermes command;
- `retry_run` / `cancel_run`: replaced by execution terminology;
- generic `get_*` commands: queries remain outside the command plane.

## Decision: optimistic concurrency

ScoreSymphony commands that mutate a pre-existing task carry the expected Forge
task `version` in their payload. The adapter forwards that value rather than
silently fetching a newer version. A stale Hermes intent must therefore fail as
a deterministic conflict instead of being applied to a different state than the
one Hermes observed.

## Decision: events

Normalized V1 event names also use Forge lifecycle terminology:

- task events: `task.created`, `task.updated`, `task.status_changed`;
- workspace event: `workspace.created`;
- execution events: `execution.started`, `execution.completed`,
  `execution.failed`, `execution.cancelled`, `execution.retry_scheduled`;
- review events: `review.started`, `review.completed`;
- merge result: `task.merged`;
- terminal command outcomes remain `command.succeeded`, `command.rejected`, and
  `command.failed`.

Forge may emit more detailed upstream events; adapters normalize only the subset
needed by the ScoreSymphony contract rather than leaking the full upstream event
vocabulary.

## Decision: durable recovery direction

`GET /api/v1/events` is currently a live broadcast SSE stream. If the receiver
lags, Forge emits `events.resync_required`; it does not expose historical
sequence replay.

Forge's database layer already has ordered durable `domain_event` storage,
`list_events_after`, consumer cursors, processing leases, and projection
receipts. The selected long-term direction is therefore to add the smallest
authenticated public Forge read surface required for historical domain-event
recovery in the ScoreSymphony-maintained Forge fork. That change must follow
Forge's nested public-API rules, including API types, docs, tests, generated web
types where applicable, and changelog visibility.

Direct SQLite access and importing Forge DB/service internals into Hermes or the
Python integration layer remain rejected.

## Consequences

- Every retained V1 command now has a concrete public Forge lifecycle mapping.
- Hermes expresses intent; it does not create workspaces, run tests, force
  reviews, dispatch workers directly, or force merges.
- Stale task mutations are rejected through Forge's existing version checks.
- V1 uses `execution_id` consistently instead of inventing a parallel run
  identity.
- The production adapter remains blocked only on implementing and testing the
  selected durable event-recovery read surface and the adapter itself.
