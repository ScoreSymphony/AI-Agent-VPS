# Historical domain-event recovery reads

Forge persists ordered domain events independently of the live in-memory EventBus. Authenticated clients that need deterministic recovery after a disconnect or an `events.resync_required` signal can read that durable history through the existing events resource in historical-read mode.

## Endpoint

```http
GET /api/v1/events?after_sequence={sequence}&limit={limit}
Authorization: Bearer <token>
```

Supplying either `after_sequence` or `limit` selects the JSON historical-read mode. Calling `GET /api/v1/events` without either parameter keeps the existing live Server-Sent Events behavior unchanged.

### Query parameters

- `after_sequence` is an exclusive persisted sequence cursor. The default is `0`; negative values are rejected.
- `limit` defaults to `100`, must be at least `1`, and is capped at `500`.

Events are returned in strictly increasing persisted `sequence` order. An empty page is valid. `next_after_sequence` is the sequence of the last returned event, or the supplied/default `after_sequence` when the page is empty.

## Response

```json
{
  "after_sequence": 120,
  "limit": 100,
  "next_after_sequence": 122,
  "events": [
    {
      "sequence": 121,
      "id": "event-id",
      "event_type": "task.updated",
      "entity_type": "task",
      "entity_id": "task-id",
      "actor_type": "system",
      "actor_id": null,
      "scope_type": "project",
      "scope_id": "project-id",
      "correlation_id": "correlation-id",
      "causation_id": null,
      "causation_depth": 0,
      "dedupe_key": null,
      "payload_json": "{}",
      "created_at": "2026-09-02T00:00:00Z"
    }
  ]
}
```

`payload_json` is the persisted Forge payload serialized as a JSON string. Consumers must not depend on database models or SQLite access; this public DTO is the recovery boundary.

## Errors and authentication

The route is covered by the normal Forge API authentication middleware. Missing or invalid credentials are rejected before the handler runs.

Invalid history parameters return HTTP 400 with stable error codes:

- `events.invalid_after_sequence`
- `events.invalid_limit`

## Recovery flow

A recovery-capable client should retain the last persisted sequence it has fully processed. After reconnect or an `events.resync_required` live notification, it should repeatedly request events after that sequence until caught up, advance only after processing each returned page, and then resume the live SSE subscription.

The historical read does not replace the live EventBus stream and does not introduce a second lifecycle authority. Forge remains the source of truth for persisted lifecycle state and domain events.
