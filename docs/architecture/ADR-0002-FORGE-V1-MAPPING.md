# ADR-0002: V1-to-Forge command and recovery mapping

- Status: Proposed
- Date: 2026-09-02
- Scope: Preconditions for the first Forge adapter

## Context

The executable V1 contract was designed before a command-by-command mapping was
checked against the pinned Forge public REST surface. The mapping must be proven
before the adapter is implemented because the platform may not bypass Forge
lifecycle rules or depend on private Rust/database types.

The pinned Forge public API currently exposes task lifecycle actions under
`/api/v1/tasks/{id}/...`, execution actions under `/api/v1/executions/{id}/...`,
and live events at `/api/v1/events`.

Forge also persists ordered domain events and consumer cursors in its database,
but those repository operations are not currently exposed by the public REST
surface.

## Verified mapping

| V1 command | Forge public operation | Status | Required follow-up |
| --- | --- | --- | --- |
| `create_task` | `POST /api/v1/projects/{project_id}/tasks` | Partial | V1 currently has no project binding; decide whether project scope is explicit in the contract or fixed adapter configuration. |
| `update_task` | `PATCH /api/v1/tasks/{task_id}` | Partial | Forge requires optimistic-concurrency `version`; V1 must require or deterministically obtain it. |
| `start_worker` | `POST /api/v1/tasks/{task_id}/start` | Semantic mismatch | Forge starts task work and owns worker selection/execution. Prefer a task-level intent such as `start_task` rather than implying Hermes starts a worker directly. |
| `create_worktree` | no equivalent public command | Unsupported | Forge owns workspace/worktree lifecycle. Do not add a bypass merely to preserve this command name. |
| `inspect_worktree` | read surfaces such as task workspace/diff | Wrong plane | This is a query/read concern, not a state-changing command. |
| `run_tests` | `POST /api/v1/tasks/{task_id}/review` only reruns review CI while the task is already in review | Semantic mismatch | Do not model generic test execution as this endpoint. Tests belong to the Forge workflow/worker/review lifecycle. |
| `request_review` | task lifecycle actions such as `submit` may advance into review depending on the workflow | Ambiguous | Use a Forge lifecycle intent rather than assuming a fixed transition. |
| `retry_run` | `POST /api/v1/executions/{run_id}/re-execute` | Mappable | Treat V1 `run_id` as the Forge execution id if this naming remains. |
| `cancel_run` | `POST /api/v1/executions/{run_id}/cancel` | Mappable | Treat V1 `run_id` as the Forge execution id if this naming remains. |
| `merge_task` | no direct public merge command | Unsupported by design | Forge workflow and approval gates must decide when merge is allowed. A direct merge mapping would risk bypassing lifecycle controls. |

## Event and recovery evidence

`GET /api/v1/events` is a live broadcast SSE stream. If the broadcast receiver
lags, Forge emits `events.resync_required`; the route does not expose a durable
sequence cursor or historical replay.

Forge's database layer does contain durable `domain_event` rows,
`list_events_after`, consumer cursors, processing leases, and projection
receipts. Those are internal repository APIs today.

Therefore the first adapter cannot honestly claim durable cursor
resynchronization using only the current public Forge REST/SSE surface.

## Decision required before adapter implementation

Choose and document one durable recovery strategy:

1. **Preferred for the long-term ScoreSymphony fork:** expose the minimum
   authenticated Forge HTTP read surface needed to project ordered durable
   domain events without exposing database details. This is a Forge public-API
   change and must follow the nested Forge repository rules, docs, tests, and
   changelog requirements.
2. **Limited first-slice alternative:** consume live SSE and recover current
   state from public REST snapshots after `events.resync_required`. This can
   prove the vertical flow but must not be described as durable event replay.
3. **Rejected:** read Forge SQLite directly or import Forge database/service
   internals into Hermes/the Python integration layer.

## Recommended contract correction

Before freezing V1, align command names with the authority boundary and the
public Forge lifecycle:

- prefer task-level lifecycle intents (`start_task`, `submit_task`,
  `approve_task`, `cancel_task`) over commands that imply Hermes owns workers,
  tests, worktrees, or merging;
- move workspace inspection to a read/query interface;
- map execution retry/cancel explicitly to Forge execution ids;
- decide project scoping and optimistic-concurrency versioning explicitly.

This ADR is `Proposed` because changing the V1 vocabulary is a contract-breaking
decision. The adapter should not be implemented beyond a disposable spike until
that decision is accepted.
