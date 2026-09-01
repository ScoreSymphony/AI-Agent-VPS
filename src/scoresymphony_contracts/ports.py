from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import CommandOutcome, CommandV1, EventV1


@runtime_checkable
class IntegrationContractPort(Protocol):
    """Transport-independent boundary implemented by future runtime adapters."""

    def submit(self, command: CommandV1) -> CommandOutcome:
        """Submit one validated command without assuming a wire transport."""
        ...

    def get_events(self, after_sequence: int | None = None) -> tuple[EventV1, ...]:
        """Read validated events after an optional transport cursor."""
        ...
