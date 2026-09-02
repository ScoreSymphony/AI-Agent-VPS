from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, Protocol


class PrincipalKind(StrEnum):
    USER = "user"
    SERVICE = "service"
    AGENT = "agent"


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONSUMED = "consumed"


@dataclass(frozen=True, slots=True)
class Credential:
    """Opaque authentication credential.

    The secret value is intentionally excluded from repr/equality so callers do
    not accidentally surface it in logs or use it as identity state.
    """

    scheme: str
    value: str = field(repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        if not self.scheme.strip():
            raise ValueError("credential scheme must not be empty")
        if not self.value:
            raise ValueError("credential value must not be empty")


@dataclass(frozen=True, slots=True)
class Principal:
    principal_id: str
    kind: PrincipalKind
    roles: frozenset[str] = field(default_factory=frozenset)
    attributes: Mapping[str, str] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        if not self.principal_id.strip():
            raise ValueError("principal_id must not be empty")
        object.__setattr__(self, "roles", frozenset(self.roles))
        object.__setattr__(
            self,
            "attributes",
            MappingProxyType(dict(self.attributes)),
        )


@dataclass(frozen=True, slots=True)
class ResourceRef:
    resource_type: str
    resource_id: str | None = None
    scope: str | None = None

    def __post_init__(self) -> None:
        if not self.resource_type.strip():
            raise ValueError("resource_type must not be empty")


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    principal: Principal
    action: str
    resource: ResourceRef
    operation_digest: str
    context: Mapping[str, str] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        if not self.action.strip():
            raise ValueError("action must not be empty")
        if not self.operation_digest.strip():
            raise ValueError("operation_digest must not be empty")
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    effect: PolicyEffect
    reason_code: str
    policy_ids: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.effect is PolicyEffect.ALLOW


@dataclass(frozen=True, slots=True)
class ApprovalRequirement:
    policy_ids: frozenset[str]
    allow_self_approval: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_ids", frozenset(self.policy_ids))
        if not self.policy_ids:
            raise ValueError("approval requirement needs at least one policy id")


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    approval_id: str
    authorization: AuthorizationRequest
    policy_id: str
    requested_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not self.approval_id.strip():
            raise ValueError("approval_id must not be empty")
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be empty")
        _require_aware(self.requested_at, "requested_at")
        _require_aware(self.expires_at, "expires_at")
        if self.expires_at <= self.requested_at:
            raise ValueError("expires_at must be after requested_at")


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    request: ApprovalRequest
    status: ApprovalStatus
    approver_id: str | None = None
    decided_at: datetime | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        decided = self.status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}
        if decided:
            if not self.approver_id or self.decided_at is None:
                raise ValueError("decided approvals require approver_id and decided_at")
            _require_aware(self.decided_at, "decided_at")
        elif self.status in {ApprovalStatus.PENDING, ApprovalStatus.EXPIRED}:
            if self.approver_id is not None or self.decided_at is not None:
                raise ValueError("pending/expired approvals must not carry a decision")
        elif self.status is ApprovalStatus.CONSUMED:
            if not self.approver_id or self.decided_at is None:
                raise ValueError("consumed approvals must retain decision metadata")
            _require_aware(self.decided_at, "decided_at")


class Authenticator(Protocol):
    def authenticate(self, credential: Credential) -> Principal | None:
        """Return an authenticated principal or None for invalid credentials."""


class Authorizer(Protocol):
    def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        """Return a deterministic authorization decision."""


class ApprovalRepository(Protocol):
    def get(self, approval_id: str) -> ApprovalRecord | None:
        """Return an approval record by id."""

    def put(self, record: ApprovalRecord) -> None:
        """Persist an approval record."""

    def transition(
        self,
        approval_id: str,
        expected_status: ApprovalStatus,
        replacement: ApprovalRecord,
    ) -> bool:
        """Atomically replace a record only when its current status matches."""


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
