# ScoreSymphony V1 contract runtime

The JSON Schemas in this directory are the canonical wire contracts. The
executable Python models and central validators live in
`src/scoresymphony_contracts`.

Every command carries a UUID `command_id`, a UUID `correlation_id`, a timezone-
aware `issued_at` timestamp, and explicit idempotency metadata. `task_id` and
`run_id` are UUID references whose required or forbidden presence depends on
the command. In particular, `create_task` does not pre-allocate a Forge-owned
task or run identifier.

Every event carries ordered sequence information, correlation and causation
identifiers, timezone-aware occurrence time, and nullable task/run references.
Terminal command events use one of three structured outcomes:

- `success`: the command completed;
- `rejected`: the command was understood but deterministically refused;
- `failed`: execution failed, with an explicit retryability flag.

Callers must use `parse_command` and `parse_event` before dispatching or
consuming messages. These functions return either a frozen V1 envelope or a
deterministic `ContractRejection`; they do not raise for invalid external
messages.

The runtime does not implement HTTP, persistence, Forge lifecycle operations,
Hermes tools, retries, or event replay. Those responsibilities belong to later
adapters and to Forge's authoritative state.
