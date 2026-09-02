# ScoreSymphony V1 contract runtime

The JSON Schemas in this directory are the canonical wire contracts. The
executable Python models and central validators live in
`src/scoresymphony_contracts`.

## Command plane

Every command carries a UUID `command_id`, a UUID `correlation_id`, a timezone-
aware `issued_at` timestamp, explicit idempotency metadata, and nullable
`task_id` / `execution_id` references whose presence depends on the command.

The V1 command vocabulary follows Forge-owned lifecycle intents rather than
exposing implementation mechanics:

- `create_task` maps to Forge project-scoped task creation and therefore
  requires `payload.project_id`;
- `update_task` maps to the Forge task update route and requires the expected
  task `version` plus at least one mutation;
- `start_task`, `submit_task`, `request_changes_task`, `approve_task`, and
  `cancel_task` map to Forge task actions and require the expected task
  `version` so stale intents fail deterministically;
- `retry_execution` and `cancel_execution` target a concrete Forge
  `execution_id`.

Commands such as `create_worktree`, `run_tests`, `request_review`, and
`merge_task` are intentionally absent. Forge owns workspace creation, workflow
transitions, review execution, gates, and merging. Workspace inspection and
other status reads belong to the query/read plane.

Submitting a command returns only an immediate `CommandReceipt` describing
ingress acceptance, duplicate detection, or pre-dispatch rejection. The receipt
is not a terminal execution result.

## Event plane

Normalized events use Forge terminology for task, workspace, and execution
state. Execution events carry `execution_id`; task/workspace/review/merge events
carry only `task_id`. Terminal `command.*` events require `causation_id` to
identify the command they complete.

The live Forge SSE feed can be projected into these event types, but the public
SSE endpoint is a broadcast stream and is not itself durable historical replay.
The separate authenticated Forge historical read is consumed by
`ForgeEventAdapter`; callers persist its returned page cursor, including across
Forge-internal events that have no V1 projection.

## Runtime rules

Callers use `parse_command` and `parse_event` before dispatching or consuming
messages. These functions return either a frozen V1 envelope or a deterministic
`ContractRejection`; they do not raise for invalid external messages.

Parsed payloads, event data, and outcome details are recursively read-only:
objects become read-only mappings and arrays become tuples.

`CommandSubmissionPort` and `EventReadPort` keep command ingress and read/
recovery semantics separate. `IntegrationContractPort` composes both without
transferring lifecycle authority away from Forge.
