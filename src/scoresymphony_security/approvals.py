from __future__ import annotations

from datetime import datetime, timezone

from .contracts import (
    ApprovalRecord,
    ApprovalRequirement,
    ApprovalStatus,
    AuthorizationRequest,
)


def approval_satisfies(
    record: ApprovalRecord,
    authorization: AuthorizationRequest,
    requirement: ApprovalRequirement,
    *,
    now: datetime | None = None,
) -> bool:
    """Return whether an approval releases this exact authorization request.

    An approval never expands permissions: it must reference one of the policy
    ids that caused REQUIRE_APPROVAL and the same immutable authorization input.
    Production dispatch must atomically consume the approval before sending the
    authorized operation downstream.
    """

    current = now or datetime.now(timezone.utc)
    request = record.request

    if record.status is not ApprovalStatus.APPROVED:
        return False
    if request.policy_id not in requirement.policy_ids:
        return False
    if record.approver_id is None or record.decided_at is None:
        return False
    if not requirement.allow_self_approval:
        if record.approver_id == request.authorization.principal.principal_id:
            return False
    if current >= request.expires_at:
        return False
    return request.authorization == authorization
