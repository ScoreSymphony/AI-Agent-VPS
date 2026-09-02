from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from scoresymphony_contracts.models import JsonObject


@dataclass(frozen=True, slots=True)
class ForgeHttpResponse:
    """Minimal response surface required by the V1-to-Forge adapter."""

    status: int
    body: JsonObject | None = None


class ForgeHttpTransport(Protocol):
    """Transport boundary for public Forge HTTP operations.

    Implementations own authentication, connection management and wire encoding.
    The command adapter deliberately knows only public HTTP method/path/body
    semantics and never imports Forge database or service internals.
    """

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: JsonObject | None = None,
    ) -> ForgeHttpResponse: ...


class ForgeTransportError(RuntimeError):
    """Raised when no trustworthy Forge HTTP response is available."""


class ForgeDispatchUncertainError(ForgeTransportError):
    """Raised for upstream server failures where dispatch outcome is uncertain."""

    def __init__(self, status: int, body: JsonObject | None = None) -> None:
        self.status = status
        self.body = body
        super().__init__(f"Forge returned HTTP {status}; command outcome is uncertain")
