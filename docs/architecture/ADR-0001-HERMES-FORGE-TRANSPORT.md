# ADR-0001: First Hermes-Forge transport

- Status: Accepted
- Date: 2026-09-01
- Scope: First local integration slice only

## Context

Hermes must remain the sole intelligent orchestrator while Forge remains the
authoritative execution and lifecycle engine. Their first integration needs a
stable ScoreSymphony-owned boundary that does not expose either upstream's
internal types. `ARCHITECTURE.md` and `ROADMAP.md` prefer local HTTP/JSON with
an event-based return path unless repository evidence shows a technical block.

The pinned upstream snapshots provide the required building blocks:

- Forge already exposes an Axum HTTP API and an authenticated SSE endpoint at
  `/api/v1/events` in `core/forge/crates/api/src/lib.rs` and
  `core/forge/crates/api/src/routes/events.rs`.
- Forge stores ordered domain events, correlation and causation identifiers,
  deduplication keys, consumer cursors, leases, and projection receipts in
  `core/forge/crates/db/src/sqlite/domain_event.rs`.
- Hermes already exposes an HTTP API bound to `127.0.0.1` by default and has
  structured SSE run-event handling in
  `core/hermes/gateway/platforms/api_server.py` and
  `core/hermes/gateway/platforms/api_server_runs.py`.
- Hermes also has explicit transport protocols in `core/hermes/tui_gateway`,
  so an adapter can remain outside its orchestration core.

Forge's current SSE payload is an upstream event-bus representation, not the
ScoreSymphony V1 contract. A future adapter must project persistent Forge-owned
domain events into V1 events and support cursor-based resynchronization. This
is an adapter requirement, not a transport blocker.

## Decision

The first Hermes-Forge transport will use HTTP/JSON over an IPv4 loopback
listener. The return path will be an SSE event stream backed by Forge-owned
durable events and a monotonic cursor. Both directions carry only validated
ScoreSymphony V1 messages.

The executable contract runtime remains transport-independent:

- JSON Schema and semantic validation happen before dispatch or consumption.
- `IntegrationContractPort` defines typed command submission and event reads.
- HTTP status codes and SSE framing do not alter command or event semantics.
- Forge adapters translate validated commands to stable Forge operations and
  translate Forge-owned outcomes to V1 events.
- Hermes adapters emit commands and consume events without importing Forge
  crates, database models, routes, or event-bus types.

The concrete HTTP server, authentication, durable cursor implementation, and
both upstream adapters are intentionally outside this work package.

## Security boundary

The initial listener must bind only to `127.0.0.1`. Moving beyond loopback
requires a separate decision covering service identity, authentication,
authorization, replay protection, TLS, rate limits, and secret redaction.
Loopback placement is not treated as authentication.

## Alternatives considered

### MCP first

Both components have MCP-related code, but MCP would add protocol negotiation
and tool discovery before the lifecycle contract is proven. It remains a
possible later adapter over the same V1 models.

### Direct Python or Rust imports

Rejected because they would couple Hermes to unstable Forge internals and
erase the process and license boundary.

### Stdio JSON-RPC

Rejected for the first slice because Forge already has an HTTP service and SSE
surface. Stdio would require additional process supervision and a separate
event fan-out mechanism without improving contract semantics.

### Polling only

Rejected as the primary return path because it increases latency and load.
Cursor-based reads remain the required recovery path after disconnects or SSE
overflow.

## Consequences

- The transport choice is compatible with both pinned upstreams and follows
  the documented preferred architecture.
- The V1 runtime can be tested without starting either upstream.
- No second task, run, worktree, review, merge, or orchestration state is
  introduced by the integration layer.
- Production exposure, adapter mappings, durable delivery, and recovery remain
  explicit follow-up work and must not be described as operational yet.
