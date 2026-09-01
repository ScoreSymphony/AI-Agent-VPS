# ADR-0001: First Hermes-Forge transport

- Status: Accepted
- Date: 2026-09-01
- Last evidence review: 2026-09-02
- Scope: First local integration slice only

## Context

Hermes must remain the sole intelligent orchestrator while Forge remains the
authoritative execution and lifecycle engine. Their first integration needs a
stable ScoreSymphony-owned boundary that does not expose either upstream's
internal types.

The pinned upstream snapshots provide the required live transport building
blocks:

- Forge exposes an Axum HTTP API and an authenticated SSE endpoint at
  `/api/v1/events`.
- Hermes exposes an HTTP API bound to `127.0.0.1` by default and has structured
  SSE run-event handling.
- Hermes has explicit transport protocols, so an adapter can remain outside its
  orchestration core.

Forge also stores ordered durable domain events, correlation/causation ids,
consumer cursors, processing leases, and projection receipts in its database
layer.

### Evidence correction after public-surface audit

The durable database facilities are not the same thing as the public Forge SSE
surface. The current `/api/v1/events` route is backed by a broadcast event bus.
When a consumer lags, it emits `events.resync_required`; it does not itself
offer historical sequence replay.

Therefore this ADR selects HTTP/JSON plus SSE as the **live transport**, but it
does not claim that the current public SSE endpoint already satisfies durable
cursor recovery. ADR-0002 records the mapping/recovery gap that must be resolved
before the production adapter is described as reliable.

## Decision

The first Hermes-Forge transport uses HTTP/JSON over an IPv4 loopback listener.
The live return path uses SSE. Both directions carry only validated
ScoreSymphony V1 messages at the ScoreSymphony boundary.

The command plane and read/event plane are intentionally distinct:

- V1 commands represent state-changing or execution-request operations.
- Query/read concerns are not encoded as generic `get_*` command kinds.
- Command submission returns an immediate receipt for acceptance, duplicate
  detection, or pre-dispatch rejection.
- A submission receipt is never a terminal execution result.
- Terminal command events identify their originating command via
  `causation_id`.

The executable contract runtime remains transport-independent:

- JSON Schema and semantic validation happen before dispatch or consumption.
- `CommandSubmissionPort` defines typed command submission.
- `EventReadPort` defines the read/recovery seam.
- `IntegrationContractPort` composes both without merging their semantics.
- HTTP status codes and SSE framing do not alter command or event semantics.
- Forge adapters translate only to documented Forge lifecycle operations.
- Hermes adapters do not import Forge crates, database models, routes, or
  event-bus types.
- Parsed V1 payload/data structures are recursively read-only after validation.

The exact durable recovery implementation is intentionally deferred to
ADR-0002. A current-state REST resynchronization can be used in a limited
vertical-slice spike, but it must not be described as durable event replay.

## Security boundary

The initial ScoreSymphony listener must bind only to `127.0.0.1`. Forge's own
non-exempt API routes require authentication. Moving either service beyond
loopback requires a separate decision covering service identity,
authentication, authorization, replay protection, TLS, rate limits, and secret
redaction. Loopback placement is not treated as authentication.

## Alternatives considered

### MCP first

MCP would add protocol negotiation and tool discovery before the lifecycle
contract is proven. It remains a possible later adapter over the same V1
models.

### Direct Python or Rust imports

Rejected for the Hermes/ScoreSymphony integration boundary because they would
couple orchestration to Forge internals and erase the intended process
boundary.

### Stdio JSON-RPC

Rejected for the first slice because Forge already has an HTTP service and SSE
surface. Stdio adds process supervision and event fan-out without improving
contract semantics.

### Polling only

Rejected as the primary live path because it increases latency and load.
Explicit read/snapshot operations remain valid recovery tools after disconnect
or SSE overflow.

## Consequences

- Loopback HTTP/JSON plus SSE remains the chosen live transport.
- A successful HTTP submission does not imply successful command execution.
- Current Forge SSE is suitable for live notification, not by itself for
  durable historical replay.
- Durable recovery must be implemented through a verified public Forge surface
  or explicitly downgraded to snapshot resynchronization for the first spike.
- No second task, execution, worktree, review, gate, merge, or orchestration
  state may be introduced by the integration layer.
- Production exposure, adapter mappings, durable delivery, and recovery remain
  explicit follow-up work and must not be described as operational yet.
