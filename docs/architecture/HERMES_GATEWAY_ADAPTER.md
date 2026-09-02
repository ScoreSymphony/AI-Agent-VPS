# Hermes gateway adapter

The `scoresymphony_hermes` package is the Hermes-facing side of the V1
integration boundary. It communicates only with the ScoreSymphony gateway over
authenticated HTTP. It does not import Forge code, access Forge persistence, or
own task and execution lifecycle state.

## Command flow

`HermesGatewayAdapter.submit` serializes an already validated immutable
`CommandV1` and calls `POST /v1/commands`. It accepts only a complete HTTP 202
receipt whose `command_id` matches the submitted command. Receipt status,
details, and identifiers are validated before an immutable `CommandReceipt` is
returned.

An accepted receipt is ingress acknowledgement only. Hermes must determine
terminal results from events and must not report task, execution, review, or
merge success from the receipt.

## Recovery flow

`get_event_page(after_sequence)` calls the gateway recovery endpoint and
validates every event through the canonical V1 parser. It rejects backwards
cursors, negative skip counts, unordered events, and event sequences beyond the
page cursor.

The adapter intentionally persists no cursor. The orchestrator or its durable
consumer stores `next_after_sequence` only after the full page has been handled
successfully. The cursor may advance even when a page has no V1 events because
Forge-internal events can be skipped by the gateway.

## Transport

`UrllibGatewayHttpTransport` supplies bounded timeouts, bearer authentication,
JSON encoding, and origin-relative path enforcement without a new runtime
dependency. Transport errors omit credentials. The gateway client token is not
the Forge bearer credential and the two must be provisioned separately.

This adapter is the stable ScoreSymphony integration seam. A later Hermes
service-gated tool can call it rather than add Forge logic to Hermes core or
expand the permanent model tool schema unnecessarily.

## Minimal Hermes surface

The `scoresymphony-hermes` CLI is the initial low-footprint consumer. Hermes can
invoke it with its existing terminal capability, so the integration adds no
permanent model-tool schema and does not invalidate conversation prompt caches.

```bash
scoresymphony-hermes submit command.json
scoresymphony-hermes events --after-sequence 120
```

Use `-` instead of a file path to read a command from standard input. Output is
one compact JSON document on standard output; validation and transport failures
are JSON on standard error with a non-zero exit status. The CLI requires only
the gateway client credential and never receives the Forge credential.
