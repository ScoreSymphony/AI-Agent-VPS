# Integration gateway operations

The `scoresymphony-gateway` command starts the ScoreSymphony-owned HTTP boundary
in front of Forge. It is deliberately bound to `127.0.0.1:8080` by default.

## Required configuration

- `FORGE_BASE_URL`: Forge base URL; defaults to `http://127.0.0.1:3000`.
- `FORGE_BEARER_TOKEN`: credential used only for gateway-to-Forge requests.
- `SCORESYMPHONY_GATEWAY_BEARER_TOKEN`: credential required from Hermes or any
  other gateway client. Use a different secret from the Forge credential.
- `SCORESYMPHONY_FORGE_TIMEOUT_SECONDS`: bounded Forge timeout; default `10`.
- `SCORESYMPHONY_EVENT_PAGE_LIMIT`: historical page size from `1` to `500`;
  default `100`.
- `SCORESYMPHONY_GATEWAY_HOST` and `SCORESYMPHONY_GATEWAY_PORT`: listener;
  defaults `127.0.0.1:8080`.

Do not put real tokens in `.env.example`, Compose files, images, or Git. The
gateway compares inbound bearer credentials in constant time and does not
include either credential in error responses.

## Endpoints

- `GET /healthz`: process liveness; does not contact Forge.
- `GET /readyz`: verifies the authenticated durable Forge recovery path.
- `POST /v1/commands`: validates a V1 command and returns an ingress receipt.
- `GET /v1/events?after_sequence=N`: returns a validated V1 recovery page and
  the authoritative next cursor.

The command endpoint returns HTTP 202 only for an ingress receipt. It does not
mean that execution, review, or merge succeeded. A Forge 5xx result is reported
as `forge.dispatch_uncertain`, because retrying before durable command
idempotency exists could duplicate an effect.

## Historical Forge recovery dependency

The gateway recovery path depends only on Forge's authenticated public event
surface. Forge historical mode is selected by supplying `after_sequence` or
`limit` to `GET /api/v1/events`; parameterless `GET /api/v1/events` remains the
live SSE stream.

The persisted read contract is complete for the current Integrated Kernel
scope: `after_sequence` is an exclusive non-negative sequence cursor, `limit`
defaults to `100` and is bounded to `1..=500`, results are strictly ordered by
persisted sequence, and empty pages preserve the supplied cursor. Invalid cursor
or limit values fail deterministically instead of being coerced.

Consumers must advance the durable cursor only after successfully processing a
validated page. Live reconnect and race-safe catch-up-to-SSE transition remain
separate Integrated Kernel work; historical recovery itself is no longer a
blocker.

## Container image

`Dockerfile.gateway` builds a non-root Python 3.12 image. The image contains no
credential and exposes port `8080`. It is not yet included in the shared Compose
topology because Forge authentication bootstrap and secret injection have not
been defined there; adding a placeholder token would produce a misleading
deployment that starts but cannot authenticate.

TLS and public exposure belong at a separately hardened reverse proxy. Until
that deployment work is complete, keep the listener on loopback or an isolated
container network.
