from __future__ import annotations

from dataclasses import dataclass

from .contracts import AuthorizationDecision, AuthorizationRequest, PolicyEffect


@dataclass(frozen=True, slots=True)
class PolicyRule:
    policy_id: str
    roles: frozenset[str]
    actions: frozenset[str]
    resource_types: frozenset[str]
    effect: PolicyEffect
    scopes: frozenset[str] = frozenset({"*"})

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be empty")
        object.__setattr__(self, "roles", frozenset(self.roles))
        object.__setattr__(self, "actions", frozenset(self.actions))
        object.__setattr__(self, "resource_types", frozenset(self.resource_types))
        object.__setattr__(self, "scopes", frozenset(self.scopes))
        if not self.roles or not self.actions or not self.resource_types or not self.scopes:
            raise ValueError("roles, actions, resource_types, and scopes must not be empty")

    def matches(self, request: AuthorizationRequest) -> bool:
        return (
            _matches_roles(request.principal.roles, self.roles)
            and _matches_value(request.action, self.actions)
            and _matches_value(request.resource.resource_type, self.resource_types)
            and _matches_scope(request.resource.scope, self.scopes)
        )


class StaticPolicyEngine:
    """Deterministic reference engine for contract tests and adapters.

    It fixes precedence and default-deny semantics. It is intentionally not a
    production identity provider, persistent policy store, or HTTP middleware.
    """

    def __init__(self, rules: tuple[PolicyRule, ...] | list[PolicyRule]) -> None:
        self._rules = tuple(rules)

    def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        matches = tuple(rule for rule in self._rules if rule.matches(request))
        if not matches:
            return AuthorizationDecision(
                effect=PolicyEffect.DENY,
                reason_code="default_deny",
            )

        for effect, reason in (
            (PolicyEffect.DENY, "explicit_deny"),
            (PolicyEffect.REQUIRE_APPROVAL, "approval_required"),
            (PolicyEffect.ALLOW, "allowed"),
        ):
            selected = tuple(
                sorted(rule.policy_id for rule in matches if rule.effect is effect)
            )
            if selected:
                return AuthorizationDecision(
                    effect=effect,
                    reason_code=reason,
                    policy_ids=selected,
                )

        return AuthorizationDecision(
            effect=PolicyEffect.DENY,
            reason_code="default_deny",
        )


def _matches_roles(values: frozenset[str], patterns: frozenset[str]) -> bool:
    return "*" in patterns or bool(values & patterns)


def _matches_value(value: str, patterns: frozenset[str]) -> bool:
    return "*" in patterns or value in patterns


def _matches_scope(scope: str | None, patterns: frozenset[str]) -> bool:
    if "*" in patterns:
        return True
    if scope is None:
        return False
    return scope in patterns
