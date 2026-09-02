# Deployment and observability baseline

This document defines the platform-quality baseline for the current upstream smoke deployment. It intentionally does not make assumptions about unfinished Forge recovery/history APIs or future Hermes runtime contracts.

## Scope

`compose.yaml` currently provides the `upstream-smoke` profile for validating the vendored Forge and Hermes components together with platform-owned deployment conventions. It is not yet a production topology.

## Safe network defaults

Forge binds to `127.0.0.1` by default through `SCORESYMPHONY_BIND_HOST`. Set a different bind address explicitly only when the surrounding firewall/reverse-proxy policy is ready.

The externally mapped Forge port is controlled by `SCORESYMPHONY_FORGE_PORT` and defaults to `8080`.

## Health model

Forge has a container liveness probe that checks whether its local TCP listener on port `8080` accepts connections. This is deliberately a transport-level liveness check only.

It must not call historical-event, recovery, SSE, or other domain APIs. Those interfaces are owned by the runtime/integration workstreams and may receive readiness checks only after their contracts are stable.

Hermes does not yet have a semantic container healthcheck in the platform compose file. Docker still observes process exit, while a real Hermes readiness probe is deferred until the gateway exposes a stable health contract that the platform can depend on without guessing.

## Logging baseline

Both upstream services use Docker's `json-file` logging driver with bounded rotation:

- `SCORESYMPHONY_LOG_MAX_SIZE` defaults to `10m`.
- `SCORESYMPHONY_LOG_MAX_FILES` defaults to `3`.
- Forge log verbosity is controlled by `SCORESYMPHONY_FORGE_LOG_LEVEL` and defaults to `info`.

Compose labels identify the component and architectural role so later log collection and metrics tooling can select containers deterministically.

This baseline does not claim structured domain telemetry, metrics, or distributed traces yet. Those should be added only when the runtime has stable event/task/run identifiers and exporters can be wired without changing domain behavior.

## Local validation

Run the platform-owned checks before opening a PR:

```bash
make quality
make compose-check
```

Equivalent direct commands are:

```bash
python scripts/validate_baseline.py
python scripts/validate_deployment.py
pytest -q
docker compose --profile upstream-smoke config --quiet
```

## CI gates

The root quality workflow validates Python 3.11 and 3.12, dependency consistency, byte compilation, repository baseline invariants, deployment invariants, tests, and Compose syntax. CI deliberately avoids requiring the unfinished recovery API.

## Next observability step

Once Forge adapter/runtime contracts are stable, add correlation fields for command, task, execution, run, and event identifiers, followed by metrics/tracing exporters. Until then, container lifecycle, bounded logs, deterministic labels, and transport liveness are the supported observability baseline.
