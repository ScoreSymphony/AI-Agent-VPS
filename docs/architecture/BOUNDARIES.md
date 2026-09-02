# Component boundaries

## Hermes to platform

Hermes emits versioned commands and consumes versioned events. It does not
write Forge state directly and does not import Forge crates.

The stable adapter seam is `scoresymphony_contracts.IntegrationContractPort`.
Its values are parsed by the central V1 validators before an adapter sees
them. The initial transport decision is recorded in
`ADR-0001-HERMES-FORGE-TRANSPORT.md`.

## Platform security gate

Protected ingress is authenticated and authorized before a platform adapter is
allowed to invoke Forge. The authenticated principal, not the V1 command
`actor`, is the source of identity. Actor assertions must be checked against the
authenticated principal rather than treated as credentials.

Hermes and the Control Plane use the same authorization port. Authorization is
default-deny and can return allow, deny, or require-approval. Security approvals
are permission gates for exact operations; they do not replace Forge task/review
approval or transfer lifecycle ownership away from Forge.

The security architecture and contract semantics are defined in
`ADR-0003-SECURITY-AUTHORIZATION.md`.

## Platform to Forge

The platform adapter translates commands into Forge-supported operations and
normalizes Forge results into platform events. Adapter failures are explicit;
they are never reinterpreted as successful task completion.

The platform stores no competing lifecycle state. Idempotency keys,
correlation identifiers, transport cursors, security decisions, and security
approvals identify requests and permission state; they do not transfer ownership
of tasks, executions, worktrees, reviews, or merge gates away from Forge.

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
state outside the same authenticated and authorized contracts used by Hermes.
