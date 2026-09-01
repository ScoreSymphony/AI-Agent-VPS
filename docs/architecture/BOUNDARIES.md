# Component boundaries

## Hermes to platform

Hermes emits versioned commands and consumes versioned events. It does not
write Forge state directly and does not import Forge crates.

## Platform to Forge

The platform adapter translates commands into Forge-supported operations and
normalizes Forge results into platform events. Adapter failures are explicit;
they are never reinterpreted as successful task completion.

## Platform to workers

Workers receive a task, workspace, allowed tools, policy, resource budget, and
expected result contract. A worker cannot merge its own work or alter another
worker's worktree.

## Platform to external components

Managed external tools live under runtime-managed storage, not in Git. An
adapter uses a process boundary. Installation, update, health, disablement,
and removal are separate lifecycle operations with audit events.

## Control Plane

The Control Plane is a view and command surface. It cannot mutate lifecycle
state outside the same authenticated contracts used by Hermes.
