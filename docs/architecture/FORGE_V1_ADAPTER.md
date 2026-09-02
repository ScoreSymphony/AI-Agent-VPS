# Forge V1 adapter

The `scoresymphony_forge` package is the ScoreSymphony-owned boundary between
Hermes-facing V1 contracts and Forge's public HTTP API. It imports no Forge
database or service internals and owns no lifecycle state.

## Command path

`ForgeCommandAdapter` maps validated `CommandV1` objects to public Forge task
and execution operations. A 2xx response produces only an accepted
`CommandReceipt`; it never claims terminal success. Deterministic 4xx responses
become rejected receipts. A 5xx response or connection failure is uncertain and
must not be retried blindly without durable idempotency evidence.

## Recovery path

`ForgeEventAdapter` reads `GET /api/v1/events` in authenticated historical JSON
mode. It verifies strict sequence ordering and response cursor consistency,
decodes `payload_json`, projects supported Forge lifecycle events through the V1
validator, and returns an immutable `ForgeEventPage`.

Forge persists more internal events than V1 exposes. Unsupported events are
counted as skipped, while `next_after_sequence` still advances across them. A
recovery loop must persist that page cursor rather than deriving its cursor from
the last projected event. This prevents an internal-only tail event from being
read forever.

Malformed public DTOs, invalid UUIDs, invalid payload JSON, backwards cursors,
and unordered pages fail closed with `ForgeEventProjectionError`. An HTTP error
is never presented as an empty history page.

## Concrete transport

`UrllibForgeHttpTransport` supplies bearer authentication, bounded timeouts,
JSON encoding, and origin-relative path enforcement using only the Python
standard library. Tokens are retained in memory and excluded from transport
error messages. Deployment must provide the token through runtime secret
configuration; it must not be committed.

`ForgeIntegrationAdapter` composes the command and recovery ports over one
transport. `scoresymphony_gateway` exposes that boundary through authenticated
HTTP with bounded request bodies and explicit liveness/readiness. Live SSE
projection, durable command idempotency, and the Hermes-side tool surface remain
separate follow-up work.

The opposite side of this boundary is documented in
`docs/architecture/HERMES_GATEWAY_ADAPTER.md`.
