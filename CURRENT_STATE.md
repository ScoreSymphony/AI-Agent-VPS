# Current state

Updated: 2026-09-02

## Current objective

Provide an executable, transport-independent V1 contract runtime as the stable
boundary for later Hermes-Forge adapters, and verify that the contract can be
mapped to the pinned Forge public surface without bypassing Forge authority.

## Implemented in this baseline

- The repository boundary is fixed to `ScoreSymphony/AI-Agent-VPS`.
- Forge is imported as a pinned MIT source snapshot.
- Hermes Agent is imported from a pinned source snapshot with documented
  non-MIT paths excluded from the vendored core.
- Upstream provenance and third-party notices are recorded.
- Hermes is defined as the sole intelligent orchestrator.
- Forge is defined as the deterministic execution/lifecycle engine.
- Component classes and the first managed-external registry entry are defined.
- Version 1 command and event schemas are present.
- V1 commands and events have frozen, typed executable Python envelopes.
- Parsed nested JSON data is recursively read-only after validation.
- Central validation returns deterministic structured rejections for unknown
  versions, missing fields, malformed identifiers, invalid timestamps, and
  invalid command/event states.
- Command submission is separated from terminal execution: submission returns
  an ingress `CommandReceipt`, while terminal truth is represented by command
  outcome events.
- Read/query concerns are not encoded as generic `get_*` V1 command kinds.
- Terminal command events require `causation_id` to identify their command.
- Separate command-submission and event-read ports are present, with a
  composite integration protocol for adapters.
- ADR-0001 selects loopback HTTP/JSON with an SSE live return path.
- ADR-0002 records the verified V1-to-Forge mapping gaps before adapter work.
- Baseline validation, tests, and a CI workflow are present.
- A read-only upstream update checker is present.

## Verified integration facts

- Forge task creation requires a `project_id` in the REST path.
- Forge task updates use optimistic concurrency and require `version`.
- Forge owns task start, workspace/worktree lifecycle, review/gates, and merge.
- Forge execution retry/cancel has public execution endpoints.
- Forge `/api/v1/events` is a live broadcast SSE stream.
- Forge has durable ordered domain-event storage internally, but the current
  public REST surface does not expose historical domain-event cursor reads.

## Not implemented yet

- Final V1 command vocabulary aligned to the verified Forge lifecycle surface.
- Explicit project-scoping rule for V1 task creation.
- Version/concurrency rule for V1 task updates and task actions.
- Public durable Forge event-recovery surface or an explicitly weaker snapshot
  resynchronization design.
- Running HTTP/SSE transport and both Hermes/Forge adapters.
- The minimal shell-worker vertical slice.
- Integrated authentication and authorization.
- Production deployment and reverse proxy configuration.
- ScoreSymphony dashboard extensions.
- Managed-external installation and removal.
- Qwen Code installation or model configuration.
- Research, file, infrastructure, monitoring, and deployment agents.
- KVM 4/KVM 8 placement.

## Next work package

Resolve and test the V1-to-Forge mapping decisions in ADR-0002 before writing
the production adapter:

1. align command vocabulary with Forge-owned lifecycle actions;
2. decide project scoping;
3. decide optimistic-concurrency/version handling;
4. select the durable event recovery surface;
5. update schemas, models, fixtures, and negative/compatibility tests together.

Only after those decisions are executable should the loopback Forge adapter be
implemented.

## Acceptance criteria for the following adapter work package

- The HTTP listener binds to loopback and accepts only validated V1 commands.
- Submission receipts only report ingress state and never impersonate terminal
  command completion.
- Every accepted V1 command has one documented stable Forge mapping.
- Forge remains authoritative for task, execution, worktree/workspace, review,
  gate, and merge state.
- No adapter command bypasses the Forge workflow state machine.
- Recovery behavior matches the actually implemented Forge event/read surface
  and is not described as durable unless historical cursor replay is real.
- Adapter acceptance, duplicate detection, rejection, failure, malformed input,
  and reconnect/recovery behavior are covered by automated tests.
- The complete vertical sequence is covered by an automated end-to-end test.

## Blockers

The production Forge adapter is blocked on the ADR-0002 contract-mapping
decisions. In particular, the current V1 vocabulary contains operations with no
unambiguous public Forge equivalent, and the current Forge SSE endpoint alone
cannot provide the durable cursor replay previously assumed.
