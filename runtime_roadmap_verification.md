# Runtime Roadmap Verification Framework

## Overview
This document outlines the verification criteria for the qwen/runtime-roadmap branch implementation.

## Key Areas to Verify

### 1. Command Execution & Orchestration
- [ ] V1 command submission separated from terminal outcomes
- [ ] CommandReceipt pattern implemented
- [ ] Terminal command events require command causation
- [ ] Task mutations carry expected Forge task version

### 2. Forge Integration
- [ ] Forge task creation is project-scoped
- [ ] Forge task updates support optimistic concurrency
- [ ] Forge owns task start/dispatch, workspace creation, review/gates, and merge
- [ ] Forge execution retry/cancel has public execution endpoints
- [ ] Forge `/api/v1/events` SSE stream works correctly
- [ ] Events.resync_required signal handled properly

### 3. Event Recovery & History
- [ ] Authenticated public Forge historical domain-event read endpoint
- [ ] DomainEventRepo implementation
- [ ] Ordered persisted domain events with cursor support
- [ ] Limit and empty-result behavior covered
- [ ] Historical event recovery mechanism implemented

### 4. Authentication & Authorization
- [ ] Production authentication/authorization design
- [ ] Forge auth integration maintained
- [ ] Secure command idempotency against Forge state

### 5. Communication Protocols
- [ ] HTTP/JSON + SSE transport implemented
- [ ] Live SSE stream maintains existing behavior
- [ ] Public API endpoint for historical events

### 6. Adapters & Components
- [ ] ScoreSymphony adapter against corrected V1 contract
- [ ] Hermes-side V1 tools/adapter
- [ ] Shell-worker end-to-end vertical slice
- [ ] Forge adapter implementation

### 7. Reliability & Resilience
- [ ] Restart/reconnect/replay behavior
- [ ] Graceful error handling
- [ ] Idempotency mechanisms
- [ ] Retry logic for transient failures

### 8. Testing & Quality
- [ ] Contract fixtures and compatibility checks
- [ ] Semantic rejection tests
- [ ] Runtime tests
- [ ] Test coverage for all new functionality

### 9. Documentation
- [ ] API docs updated
- [ ] Changelog entries added
- [ ] TypeScript types updated
- [ ] Documentation claims match implementation

## Verification Status Matrix

| Requirement | Status |
|-------------|--------|
| V1 command submission separation | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| Forge task creation scoping | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| CommandReceipt pattern | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| Terminal command causation | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| Task versioning | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| Historical event read endpoint | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| DomainEventRepo implementation | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| Authentication system | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| SSE transport | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| ScoreSymphony adapter | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| Hermes adapter | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| Shell worker | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| Restart/reconnect/replay | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |
| Test coverage | [MISSING/PARTIAL/VERIFIED COMPLETE/BLOCKED EXTERNALLY] |

## Implementation Notes
Based on the current state documentation, several key components appear to be missing or not yet implemented:
- Authenticated public Forge historical domain-event read endpoint
- ScoreSymphony command HTTP endpoint and SSE projection adapter
- Durable command idempotency integration
- Hermes-side V1 tools/adapter
- Minimal shell-worker end-to-end vertical slice
- Production authentication/authorization design
- Deployment, Control Plane, agent registry, managed externals, specialist agents, and KVM placement

## Recommendations
1. Implement missing historical event read endpoint
2. Complete ScoreSymphony adapter implementation
3. Add proper authentication/authorization layer
4. Implement shell worker end-to-end slice
5. Add comprehensive test coverage
6. Update documentation to reflect actual implementation status
