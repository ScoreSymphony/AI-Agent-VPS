#![allow(dead_code)]
mod common;

use api::routes::events::HistoricalDomainEventsResponse;
use axum::{
    body::{to_bytes, Body},
    http::{header, Method, Request, StatusCode},
};
use db::{CreateDomainEvent, DomainEventRepo};
use tower::ServiceExt;

async fn append_event(harness: &common::Harness, id: &str, event_type: &str) -> db::DomainEvent {
    DomainEventRepo::append_event(
        &*harness.state.db,
        CreateDomainEvent {
            id: id.to_owned(),
            event_type: event_type.to_owned(),
            entity_type: "task".to_owned(),
            entity_id: format!("task-{id}"),
            actor_type: "system".to_owned(),
            actor_id: None,
            scope_type: "project".to_owned(),
            scope_id: "project-1".to_owned(),
            correlation_id: format!("corr-{id}"),
            causation_id: None,
            causation_depth: 0,
            dedupe_key: Some(format!("dedupe-{id}")),
            payload_json: format!(r#"{{"id":"{id}"}}"#),
            created_at: db::now_rfc3339(),
        },
    )
    .await
    .expect("append domain event")
}

async fn history(
    harness: &common::Harness,
    uri: &str,
) -> HistoricalDomainEventsResponse {
    common::empty_request_with_bearer(
        &harness.app,
        Method::GET,
        uri,
        &common::test_jwt(),
        StatusCode::OK,
    )
    .await
}

#[tokio::test]
async fn historical_read_requires_authentication() {
    let workspace_root = common::TestDir::new("domain-events-auth-ws");
    let harness = common::test_app(workspace_root.path(), "domain-events-auth").await;

    let response = harness
        .app
        .clone()
        .oneshot(
            Request::builder()
                .method(Method::GET)
                .uri("/api/v1/events?after_sequence=0&limit=10")
                .body(Body::empty())
                .expect("build request"),
        )
        .await
        .expect("router response");

    assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn historical_read_supports_beginning_middle_end_and_empty_results() {
    let workspace_root = common::TestDir::new("domain-events-cursors-ws");
    let harness = common::test_app(workspace_root.path(), "domain-events-cursors").await;

    let first = append_event(&harness, "event-1", "task.created").await;
    let second = append_event(&harness, "event-2", "task.updated").await;
    let third = append_event(&harness, "event-3", "task.completed").await;

    let from_start = history(&harness, "/api/v1/events?after_sequence=0&limit=10").await;
    assert_eq!(
        from_start.events.iter().map(|event| event.sequence).collect::<Vec<_>>(),
        vec![first.sequence, second.sequence, third.sequence]
    );
    assert_eq!(from_start.next_after_sequence, third.sequence);

    let from_middle = history(
        &harness,
        &format!("/api/v1/events?after_sequence={}&limit=10", first.sequence),
    )
    .await;
    assert_eq!(
        from_middle
            .events
            .iter()
            .map(|event| event.sequence)
            .collect::<Vec<_>>(),
        vec![second.sequence, third.sequence]
    );

    let from_end = history(
        &harness,
        &format!("/api/v1/events?after_sequence={}&limit=10", third.sequence),
    )
    .await;
    assert!(from_end.events.is_empty());
    assert_eq!(from_end.next_after_sequence, third.sequence);
}

#[tokio::test]
async fn historical_read_is_strictly_ordered_and_respects_limit() {
    let workspace_root = common::TestDir::new("domain-events-limit-ws");
    let harness = common::test_app(workspace_root.path(), "domain-events-limit").await;

    for index in 0..5 {
        append_event(
            &harness,
            &format!("event-{index}"),
            "task.transitioned",
        )
        .await;
    }

    let response = history(&harness, "/api/v1/events?after_sequence=0&limit=2").await;
    assert_eq!(response.events.len(), 2);
    assert!(response
        .events
        .windows(2)
        .all(|pair| pair[0].sequence < pair[1].sequence));
    assert_eq!(response.next_after_sequence, response.events[1].sequence);
}

#[tokio::test]
async fn historical_read_rejects_invalid_cursor_and_limit_values() {
    let workspace_root = common::TestDir::new("domain-events-invalid-ws");
    let harness = common::test_app(workspace_root.path(), "domain-events-invalid").await;
    let token = common::test_jwt();

    for (uri, expected_code) in [
        (
            "/api/v1/events?after_sequence=-1&limit=10",
            "events.invalid_after_sequence",
        ),
        (
            "/api/v1/events?after_sequence=0&limit=0",
            "events.invalid_limit",
        ),
        (
            "/api/v1/events?after_sequence=0&limit=501",
            "events.invalid_limit",
        ),
    ] {
        let response = harness
            .app
            .clone()
            .oneshot(
                Request::builder()
                    .method(Method::GET)
                    .uri(uri)
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .body(Body::empty())
                    .expect("build request"),
            )
            .await
            .expect("router response");
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let bytes = to_bytes(response.into_body(), usize::MAX)
            .await
            .expect("read error body");
        let body: serde_json::Value = serde_json::from_slice(&bytes).expect("parse error body");
        assert_eq!(body.get("code").and_then(serde_json::Value::as_str), Some(expected_code));
    }
}

#[tokio::test]
async fn concurrent_append_and_read_never_break_sequence_order() {
    let workspace_root = common::TestDir::new("domain-events-concurrent-ws");
    let harness = common::test_app(workspace_root.path(), "domain-events-concurrent").await;

    append_event(&harness, "event-before", "task.created").await;

    let writer = append_event(&harness, "event-concurrent", "task.updated");
    let reader = history(&harness, "/api/v1/events?after_sequence=0&limit=10");
    let (written, observed) = tokio::join!(writer, reader);

    assert!(observed
        .events
        .windows(2)
        .all(|pair| pair[0].sequence < pair[1].sequence));

    let caught_up = history(&harness, "/api/v1/events?after_sequence=0&limit=10").await;
    assert!(caught_up
        .events
        .windows(2)
        .all(|pair| pair[0].sequence < pair[1].sequence));
    assert!(caught_up.events.iter().any(|event| event.id == written.id));
}
