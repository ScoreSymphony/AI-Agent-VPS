# ADR-0003: Platform authentication, authorization, and approvals

Status: Proposed

Date: 2026-09-02

## Context

The ScoreSymphony Agent Platform has multiple command sources but one execution
lifecycle authority. Human users, the Control Plane, and Hermes may request
operations; Forge remains the deterministic execution, workspace, review, gate,
and merge authority.

The platform therefore needs a security boundary that can authenticate callers,
authorize operations, and require explicit approval for selected high-impact
operations without creating a second lifecycle engine or allowing callers to
bypass Forge.

The current V1 command contract contains an `actor`, but asserted command data is
not authentication evidence. A caller must first be authenticated independently,
and the authenticated principal must be authorized before an adapter invokes a
Forge public API.

## Decision

### 1. Put a platform security gate in front of protected platform operations

Every protected ingress path follows this order:

`credential -> authentication -> principal -> authorization -> optional approval -> adapter -> Forge`

The same authorization port is used by Hermes-facing APIs and the Control Plane.
No UI-only or Hermes-only bypass is permitted.

The security layer gates access to Forge operations. It does not own task,
execution, workspace, review, gate, or merge lifecycle state.

### 2. Keep authentication provider-neutral

The platform exposes an `Authenticator` port that resolves an opaque credential
to a `Principal`. Initial deployments may use locally managed bearer/service
credentials injected through runtime secrets. Later OIDC, mTLS, or another local
identity provider can implement the same port without changing authorization
semantics.

Credentials must never be committed to Git. Credential secret values must not be
logged. Hermes service identity and human identities must remain distinguishable.

The command `actor` field is metadata to validate against the authenticated
principal; it is never trusted as proof of identity.

### 3. Use RBAC for coarse grants and policy rules for context

Authorization evaluates an immutable request containing:

- authenticated principal and roles;
- action;
- resource type and resource id;
- authorization scope, normally a project when available;
- bounded context required by policy.

Rules return exactly one of:

- `deny`;
- `require_approval`;
- `allow`.

If no rule matches, the result is `deny`.

When multiple rules match, precedence is:

`DENY > REQUIRE_APPROVAL > ALLOW`

An `admin` role therefore does not automatically override an explicit deny or an
approval requirement.

### 4. Separate security approval from Forge review approval

A security approval grants permission to issue one exact protected operation.
It is not the same concept as Forge task/review approval and must not mutate Forge
review state directly.

An approval is bound to the exact authorization request and to one of the policy
ids that caused `require_approval`. It has an expiry. Self-approval is denied by
default but may be explicitly enabled for a deliberate single-admin deployment.

Production dispatch must atomically transition an approved record to `consumed`
before the protected operation is sent downstream, preventing approval replay.

### 5. Keep security decisions auditable

Runtime integration must emit audit records for authentication failures,
authorization decisions, approval creation/decision/consumption, role-binding
changes, and policy changes. Audit records may contain principal id, action,
resource, decision, policy ids, command/correlation ids, and timestamps, but must
not contain credential secret values.

## Initial action vocabulary

The platform adapter should map the current V1 commands to authorization actions
before Forge is called:

| V1 command | Security action | Primary resource |
| --- | --- | --- |
| `create_task` | `task.create` | project |
| `update_task` | `task.update` | task |
| `start_task` | `task.start` | task |
| `submit_task` | `task.submit` | task |
| `request_changes_task` | `task.request_changes` | task |
| `approve_task` | `task.approve` | task |
| `cancel_task` | `task.cancel` | task |
| `retry_execution` | `execution.retry` | execution |
| `cancel_execution` | `execution.cancel` | execution |

Historical event reads use `events.read`. Where a read surface cannot yet enforce
a project scope, the corresponding permission must be treated as broader than a
project-scoped read and granted narrowly.

This vocabulary is an adapter mapping, not a new Forge command surface.

## Initial role model

Role names are deployment policy, not protocol constants. The expected starting
shape is:

- `viewer`: read-only views/events within assigned scopes;
- `operator`: normal task/execution operations within assigned scopes;
- `reviewer`: review-related commands within assigned scopes;
- `hermes-service`: orchestration operations required by Hermes, but no security
  administration;
- `security-admin`: role/policy/approval administration.

Deployments may combine roles. Explicit policy effects and scope restrictions
still apply.

## Trust boundaries

### Human / Control Plane -> platform

Authenticate the human session/request, derive a principal, then authorize every
protected API operation. The Control Plane is not privileged merely because it
is the UI.

### Hermes -> platform

Hermes authenticates as a dedicated service/agent principal. Hermes remains the
sole intelligent orchestrator, but orchestration authority does not imply
unrestricted platform authorization.

### Platform -> Forge

The adapter uses Forge's public authenticated surfaces. Platform authorization
must happen before the Forge call, while Forge's own authentication and
lifecycle checks remain in force. Platform security must not weaken or bypass
Forge controls.

### Workers

Workers receive bounded capabilities from the platform. A worker does not gain
security administration rights and cannot use an approval to expand its task,
workspace, tool, or merge authority.

## Consequences

- Security contracts can be implemented and tested independently from the Forge
  adapter and SSE runtime.
- Hermes and the Control Plane share one authorization model.
- Existing Forge auth remains relevant; platform security adds caller identity,
  RBAC/policy, and approvals rather than replacing Forge lifecycle checks.
- Production auth middleware, persistent policy/approval storage, audit storage,
  and endpoint wiring are intentionally not claimed as implemented by this ADR.
- The deterministic reference policy engine in `scoresymphony_security` fixes
  decision precedence for tests and future adapters but is not a production
  policy service.

## Follow-up work

1. Bind authenticated principals to V1 `actor` assertions at HTTP ingress.
2. Implement persistent role/policy configuration and approval storage.
3. Add atomic approval consumption before adapter dispatch.
4. Emit security audit events with secret-safe payloads.
5. Add API middleware and Control Plane endpoints using the shared ports.
6. Add integration tests proving unauthorized or unapproved operations never
   reach the Forge adapter.
