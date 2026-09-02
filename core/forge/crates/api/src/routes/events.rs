use std::convert::Infallible;

use axum::{
    extract::{Query, State},
    response::{
        sse::{Event, KeepAlive, Sse},
        IntoResponse, Response,
    },
    Json,
};
use db::{DomainEvent, DomainEventRepo};
use serde::{Deserialize, Serialize};
use serde_json::json;
use tokio_stream::{wrappers::BroadcastStream, StreamExt};

use crate::{
    errors::{ApiError, ApiResult},
    state::AppState,
};

const DEFAULT_HISTORY_LIMIT: i64 = 100;
const MAX_HISTORY_LIMIT: i64 = 500;

#[derive(Debug, Clone, Default, Deserialize)]
pub struct EventsQuery {
    pub after_sequence: Option<i64>,
    pub limit: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HistoricalDomainEvent {
    pub sequence: i64,
    pub id: String,
    pub event_type: String,
    pub entity_type: String,
    pub entity_id: String,
    pub actor_type: String,
    pub actor_id: Option<String>,
    pub scope_type: String,
    pub scope_id: String,
    pub correlation_id: String,
    pub causation_id: Option<String>,
    pub causation_depth: i64,
    pub dedupe_key: Option<String>,
    pub payload_json: String,
    pub created_at: String,
}

impl From<DomainEvent> for HistoricalDomainEvent {
    fn from(event: DomainEvent) -> Self {
        Self {
            sequence: event.sequence,
            id: event.id,
            event_type: event.event_type,
            entity_type: event.entity_type,
            entity_id: event.entity_id,
            actor_type: event.actor_type,
            actor_id: event.actor_id,
            scope_type: event.scope_type,
            scope_id: event.scope_id,
            correlation_id: event.correlation_id,
            causation_id: event.causation_id,
            causation_depth: event.causation_depth,
            dedupe_key: event.dedupe_key,
            payload_json: event.payload_json,
            created_at: event.created_at,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HistoricalDomainEventsResponse {
    pub after_sequence: i64,
    pub limit: i64,
    pub next_after_sequence: i64,
    pub events: Vec<HistoricalDomainEvent>,
}

pub async fn stream_events(
    State(state): State<AppState>,
    Query(query): Query<EventsQuery>,
) -> Response {
    if query.after_sequence.is_some() || query.limit.is_some() {
        return match historical_events(&state, query).await {
            Ok(response) => response.into_response(),
            Err(error) => error.into_response(),
        };
    }

    let mut shutdown = state.shutdown_signal.subscribe();
    let shutdown_requested = async move {
        if *shutdown.borrow_and_update() {
            return;
        }

        while shutdown.changed().await.is_ok() {
            if *shutdown.borrow_and_update() {
                return;
            }
        }
    };

    let stream =
        BroadcastStream::new(state.event_bus.subscribe()).filter_map(|event| match event {
            Ok(event) => {
                let event_type = event.event_type.clone();
                let entity_id = event.entity_id.clone();
                // EventContext is flattened and Serialize-derived, so review/cleanup/merge
                // contexts pass through SSE without variant-specific routing here.
                let data = serde_json::to_string(&event).ok()?;
                Some(Ok::<Event, Infallible>(
                    Event::default()
                        .event(event_type)
                        .id(entity_id)
                        .data(data),
                ))
            }
            Err(error) => {
                let event_type = "events.resync_required";
                let data = json!({
                    "event_type": event_type,
                    "entity_id": event_type,
                    "timestamp": events::event_timestamp(),
                    "reason": error.to_string(),
                });
                Some(Ok::<Event, Infallible>(
                    Event::default()
                        .event(event_type)
                        .id(event_type)
                        .data(data.to_string()),
                ))
            }
        });
    Sse::new(futures_util::StreamExt::take_until(
        stream,
        shutdown_requested,
    ))
    .keep_alive(KeepAlive::default())
    .into_response()
}

async fn historical_events(
    state: &AppState,
    query: EventsQuery,
) -> ApiResult<Json<HistoricalDomainEventsResponse>> {
    let after_sequence = query.after_sequence.unwrap_or(0);
    if after_sequence < 0 {
        return Err(ApiError::bad_request_with_code(
            "events.invalid_after_sequence",
            "after_sequence must be zero or greater",
        ));
    }

    let limit = query.limit.unwrap_or(DEFAULT_HISTORY_LIMIT);
    if !(1..=MAX_HISTORY_LIMIT).contains(&limit) {
        return Err(ApiError::bad_request_with_code(
            "events.invalid_limit",
            format!("limit must be between 1 and {MAX_HISTORY_LIMIT}"),
        ));
    }

    let events = DomainEventRepo::list_events_after(&*state.db, after_sequence, limit).await?;
    let next_after_sequence = events
        .last()
        .map(|event| event.sequence)
        .unwrap_or(after_sequence);

    Ok(Json(HistoricalDomainEventsResponse {
        after_sequence,
        limit,
        next_after_sequence,
        events: events.into_iter().map(HistoricalDomainEvent::from).collect(),
    }))
}
