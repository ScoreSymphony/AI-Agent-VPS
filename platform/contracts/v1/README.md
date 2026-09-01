# ScoreSymphony V1 contract runtime

The JSON Schemas in this directory are the canonical wire contracts. The
executable Python models and central validators live in
`src/scoresymphony_contracts`.

## Command plane

Every command carries a UUID `command_id`, a UUID `correlation_id`, a timezone-
aware `issued_at` timestamp, and explicit idempotency metadata. `task_id` and
`run_id` are UUID references whose required or forbidden presence depends on
the command. In particular, `create_task` does not pre-allocate a Forge-owned
task or run identifier.

The V1 command plane contains state-changing or execution-request operations
only. Event reads and resource/status reads are query concerns and are not
encoded as `CommandKind` values.

Submitting a command returns only an immediate `CommandReceipt` describing
ingress acceptance, duplicate detection, or pre-dispatch rejection. That
receipt is not a terminal execution result.

## Event plane

Every event carries ordered sequence information, correlation and causation
identifiers, timezone-aware occurrence time, and nullable task/run references.
Terminal command events use one of three structured outcomes:

- `success`: the command completed;
- `rejected`: the command was understood but deterministically refused;
- `failed`: execution failed, with an explicit retryability flag.

`command.succeeded`, `command.rejected`, and `command.failed` require a
`causation_id` that identifies the command they complete. The durable event
stream is the authoritative channel for terminal command outcomes.

## Runtime rules

Callers must use `parse_command` and `parse_event` before dispatching or
consuming messages. These functions return either a frozen V1 envelope or a
deterministic `ContractRejection`; they do not raise for invalid external
messages.

Parsed payloads, event data, and outcome details are recursively read-only:
objects become read-only mappings and arrays become tuples. This prevents
nested mutation after validation.

`CommandSubmissionPort` and `EventReadPort` keep write and read semantics
separate. `IntegrationContractPort` is their composite convenience boundary.

The runtime does not implement HTTP, persistence, Forge lifecycle operations,
Hermes tools, retries, resource queries, or event replay. Those responsibilities
belong to later adapters and to Forge's authoritative state.
