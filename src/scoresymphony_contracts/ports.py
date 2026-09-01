from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import CommandReceipt, CommandV1, EventV1


@runtime_checkable
class CommandSubmissionPort(Protocol):
    """Command ingress; acceptance is distinct from terminal execution outcome."""

    def submit(self, command: CommandV1) -> CommandReceipt:
        """Accept, deduplicate, or reject one validated command at ingress."""
        ...


@runtime_checkable
class EventReadPort(Protocol):
    """Read-only event recovery path used independently of command submission."""

    def get_events(self, after_sequence: int | None = None) -> tuple[EventV1, ...]:
        """Read validated events after an optional durable cursor."""
        ...


@runtime_checkable
class IntegrationContractPort(CommandSubmissionPort, EventReadPort, Protocol):
    """Composite transport-independent boundary implemented by runtime adapters."""

    pass
