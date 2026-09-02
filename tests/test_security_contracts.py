from datetime import datetime, timedelta, timezone

import pytest

from scoresymphony_security import (
    ApprovalRecord,
    ApprovalRequest,
    ApprovalRequirement,
    ApprovalStatus,
    AuthorizationRequest,
    Credential,
    PolicyEffect,
    PolicyRule,
    Principal,
    PrincipalKind,
    ResourceRef,
    StaticPolicyEngine,
    approval_satisfies,
)


def principal(*roles: str, principal_id: str = "agent-1") -> Principal:
    return Principal(
        principal_id=principal_id,
        kind=PrincipalKind.AGENT,
        roles=frozenset(roles),
    )


def auth_request(
    *,
    roles=("operator",),
    action="task.create",
    scope="project-1",
    operation_digest="sha256:operation-1",
    context=None,
):
    return AuthorizationRequest(
        principal=principal(*roles),
        action=action,
        resource=ResourceRef(resource_type="project", resource_id=scope, scope=scope),
        operation_digest=operation_digest,
        context=context or {},
    )


def rule(
    effect: PolicyEffect,
    *,
    policy_id: str,
    roles=("operator",),
    scopes=("*",),
):
    return PolicyRule(
        policy_id=policy_id,
        roles=frozenset(roles),
        actions=frozenset({"task.create"}),
        resource_types=frozenset({"project"}),
        scopes=frozenset(scopes),
        effect=effect,
    )


def test_credential_secret_is_not_exposed_by_repr() -> None:
    credential = Credential(scheme="bearer", value="super-secret-token")
    assert "super-secret-token" not in repr(credential)


def test_authorization_inputs_are_immutable() -> None:
    request = auth_request(context={"channel": "hermes"})
    with pytest.raises(TypeError):
        request.context["channel"] = "control-plane"


def test_authorization_requires_operation_digest() -> None:
    with pytest.raises(ValueError, match="operation_digest"):
        auth_request(operation_digest=" ")


def test_no_matching_rule_is_default_deny() -> None:
    decision = StaticPolicyEngine([]).authorize(auth_request())
    assert decision.effect is PolicyEffect.DENY
    assert decision.reason_code == "default_deny"
    assert decision.allowed is False


def test_rbac_rule_allows_matching_role_action_resource_and_scope() -> None:
    engine = StaticPolicyEngine([rule(PolicyEffect.ALLOW, policy_id="operator-create")])
    decision = engine.authorize(auth_request())
    assert decision.allowed is True
    assert decision.policy_ids == ("operator-create",)


def test_scope_is_enforced() -> None:
    engine = StaticPolicyEngine(
        [rule(PolicyEffect.ALLOW, policy_id="project-1-only", scopes=("project-1",))]
    )
    decision = engine.authorize(auth_request(scope="project-2"))
    assert decision.effect is PolicyEffect.DENY
    assert decision.reason_code == "default_deny"


def test_explicit_deny_precedes_allow() -> None:
    engine = StaticPolicyEngine(
        [
            rule(PolicyEffect.ALLOW, policy_id="general-allow"),
            rule(PolicyEffect.DENY, policy_id="safety-deny"),
        ]
    )
    decision = engine.authorize(auth_request())
    assert decision.effect is PolicyEffect.DENY
    assert decision.reason_code == "explicit_deny"
    assert decision.policy_ids == ("safety-deny",)


def test_approval_requirement_precedes_allow() -> None:
    engine = StaticPolicyEngine(
        [
            rule(PolicyEffect.ALLOW, policy_id="operator-allow"),
            rule(PolicyEffect.REQUIRE_APPROVAL, policy_id="human-gate"),
        ]
    )
    decision = engine.authorize(auth_request())
    assert decision.effect is PolicyEffect.REQUIRE_APPROVAL
    assert decision.reason_code == "approval_required"


def test_approved_record_only_releases_exact_request_and_required_policy() -> None:
    now = datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)
    authorization = auth_request(context={"channel": "hermes"})
    request = ApprovalRequest(
        approval_id="approval-1",
        authorization=authorization,
        policy_id="human-gate",
        requested_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    approved = ApprovalRecord(
        request=request,
        status=ApprovalStatus.APPROVED,
        approver_id="reviewer-1",
        decided_at=now + timedelta(minutes=1),
    )
    requirement = ApprovalRequirement(frozenset({"human-gate"}))

    assert approval_satisfies(
        approved,
        authorization,
        requirement,
        now=now + timedelta(minutes=2),
    )
    assert not approval_satisfies(
        approved,
        auth_request(action="execution.cancel", context={"channel": "hermes"}),
        requirement,
        now=now + timedelta(minutes=2),
    )
    assert not approval_satisfies(
        approved,
        auth_request(context={"channel": "control-plane"}),
        requirement,
        now=now + timedelta(minutes=2),
    )
    assert not approval_satisfies(
        approved,
        auth_request(
            operation_digest="sha256:different-operation",
            context={"channel": "hermes"},
        ),
        requirement,
        now=now + timedelta(minutes=2),
    )
    assert not approval_satisfies(
        approved,
        authorization,
        ApprovalRequirement(frozenset({"different-policy"})),
        now=now + timedelta(minutes=2),
    )


def test_self_approval_is_denied_by_default_but_can_be_explicitly_enabled() -> None:
    now = datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)
    authorization = auth_request()
    request = ApprovalRequest(
        approval_id="approval-1",
        authorization=authorization,
        policy_id="human-gate",
        requested_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    record = ApprovalRecord(
        request=request,
        status=ApprovalStatus.APPROVED,
        approver_id=authorization.principal.principal_id,
        decided_at=now + timedelta(minutes=1),
    )

    assert not approval_satisfies(
        record,
        authorization,
        ApprovalRequirement(frozenset({"human-gate"})),
        now=now + timedelta(minutes=2),
    )
    assert approval_satisfies(
        record,
        authorization,
        ApprovalRequirement(frozenset({"human-gate"}), allow_self_approval=True),
        now=now + timedelta(minutes=2),
    )


def test_expired_or_consumed_approval_does_not_release_request() -> None:
    now = datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)
    authorization = auth_request()
    request = ApprovalRequest(
        approval_id="approval-1",
        authorization=authorization,
        policy_id="human-gate",
        requested_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    record = ApprovalRecord(
        request=request,
        status=ApprovalStatus.APPROVED,
        approver_id="reviewer-1",
        decided_at=now + timedelta(minutes=1),
    )
    requirement = ApprovalRequirement(frozenset({"human-gate"}))
    assert not approval_satisfies(
        record,
        authorization,
        requirement,
        now=now + timedelta(minutes=5),
    )

    consumed = ApprovalRecord(
        request=request,
        status=ApprovalStatus.CONSUMED,
        approver_id="reviewer-1",
        decided_at=now + timedelta(minutes=1),
    )
    assert not approval_satisfies(
        consumed,
        authorization,
        requirement,
        now=now + timedelta(minutes=2),
    )


def test_invalid_principal_approval_windows_and_naive_times_are_rejected() -> None:
    with pytest.raises(ValueError):
        Principal(principal_id=" ", kind=PrincipalKind.USER)

    now = datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        ApprovalRequest(
            approval_id="approval-1",
            authorization=auth_request(),
            policy_id="human-gate",
            requested_at=now,
            expires_at=now,
        )

    with pytest.raises(ValueError):
        ApprovalRequest(
            approval_id="approval-1",
            authorization=auth_request(),
            policy_id="human-gate",
            requested_at=datetime(2026, 9, 2, 4, 0),
            expires_at=datetime(2026, 9, 2, 5, 0),
        )
