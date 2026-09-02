# Reproducible Reference Deployment

This runbook defines the supported single-node reference deployment for the ScoreSymphony Agent Platform.

The reference profile is intentionally **loopback-only** until the production Security/Policy/Approval baseline is complete. Do not bind Forge or the ScoreSymphony Gateway to a public interface and do not add a reverse proxy/TLS exposure as a workaround. External exposure belongs after the security release gate.

## Scope

The current reference profile provides:

- Forge as the canonical execution/lifecycle authority;
- the ScoreSymphony HTTP Gateway as the integration boundary;
- persistent Forge state in a Docker named volume;
- health/readiness checks;
- bounded container logging;
- restart policies;
- CPU, memory and PID limits;
- a read-only, non-root Gateway container with dropped Linux capabilities;
- preflight validation;
- start/stop/status/diagnosis helpers;
- consistent Forge-state backup and destructive restore;
- an explicit upgrade and rollback procedure.

Hermes is not yet part of the reference profile because the complete process-level Integrated Kernel is still a separate release-gate dependency. The existing `hermes-upstream` service remains an upstream smoke-test service. The reference deployment must not claim the full end-to-end acceptance gate until the Integrated Kernel work is complete.

## Supported host baseline

A supported host needs:

- a current Linux distribution or another Docker Engine host supported by Docker Compose;
- Docker Engine and the Docker Compose plugin;
- Git;
- Python 3.11+ for repository validation and the lifecycle helper;
- enough free storage for Forge state, workspaces, container images and backups.

The profile is not tied to a particular VPS provider or machine size. Resource defaults are conservative starting points and can be changed through `.env` after measurement.

## 1. Checkout and configuration

Clone the repository and enter it:

```bash
git clone https://github.com/ScoreSymphony/AI-Agent-VPS.git
cd AI-Agent-VPS
cp .env.example .env
```

Keep `.env` local. It is ignored by Git and must never contain credentials that are committed to the repository.

The reference deployment remains loopback-bound:

```dotenv
SCORESYMPHONY_BIND_HOST=127.0.0.1
```

Do not change this to `0.0.0.0` while the production security baseline is incomplete.

## 2. Bootstrap Forge authentication

The ScoreSymphony Gateway calls authenticated Forge APIs. Forge already exposes local register/login and personal-access-token endpoints, but production identity binding, credential lifecycle and policy enforcement are tracked by the security work package. For the reference profile, bootstrap a local Forge operator/PAT only on the loopback interface.

Start Forge by itself:

```bash
docker compose --profile reference up -d --build forge-upstream
```

Verify liveness:

```bash
curl --fail http://127.0.0.1:8080/healthz
```

Register a local operator if this Forge data volume is new:

```bash
curl --fail-with-body \
  -H 'Content-Type: application/json' \
  -d '{"email":"operator@example.invalid","password":"CHANGE_THIS_PASSWORD","display_name":"Reference Operator"}' \
  http://127.0.0.1:8080/api/v1/auth/register
```

If the user already exists, use `/api/v1/auth/login` instead. Keep the returned access token private.

Create a Forge personal access token with the access token returned by register/login:

```bash
curl --fail-with-body \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer ACCESS_TOKEN_HERE' \
  -d '{"name":"scoresymphony-reference-gateway","expires_at":null}' \
  http://127.0.0.1:8080/api/v1/auth/tokens
```

Copy the returned `fg_...` token into `.env`:

```dotenv
FORGE_BEARER_TOKEN=fg_replace_me
```

Generate a separate high-entropy credential for callers of the ScoreSymphony Gateway, for example:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Store that value in:

```dotenv
SCORESYMPHONY_GATEWAY_BEARER_TOKEN=replace_me
```

The Forge PAT and Gateway bearer token must be different credentials.

## 3. Preflight

Run repository and deployment validation before starting the profile:

```bash
make quality
python scripts/reference_deployment.py preflight
```

Preflight fails when:

- Docker Compose is unavailable;
- `.env` is missing;
- the reference bind host is not loopback;
- the Forge PAT is missing, still a placeholder or not in `fg_...` form;
- the Gateway bearer token is missing/placeholder/obviously too short;
- Compose cannot render the reference profile.

## 4. Start

```bash
python scripts/reference_deployment.py start
```

Expected local endpoints:

- Forge: `http://127.0.0.1:8080`
- ScoreSymphony Gateway: `http://127.0.0.1:8090`

Check Gateway liveness:

```bash
curl --fail http://127.0.0.1:8090/healthz
```

Check dependency-aware readiness:

```bash
curl --fail http://127.0.0.1:8090/readyz
```

`/readyz` is intentionally stronger than liveness: it verifies that the Gateway can reach and authenticate to the Forge historical-event API.

## 5. Status, logs and diagnosis

```bash
python scripts/reference_deployment.py status
python scripts/reference_deployment.py diagnose
```

Useful direct commands:

```bash
docker compose --profile reference ps
docker compose --profile reference logs --tail 200 forge-upstream gateway
```

Interpretation:

- Forge unhealthy: diagnose Forge process/startup, data-volume permissions and host resource pressure.
- Gateway alive but not ready: verify Forge readiness, `FORGE_BEARER_TOKEN`, Forge event-history authentication and container-network reachability.
- Repeated restarts: inspect logs before changing restart policy; do not mask an initialization or migration failure.

## 6. Stop and restart

Stop containers while preserving persistent state:

```bash
python scripts/reference_deployment.py stop
```

Start them again with the same `.env` and named volume:

```bash
python scripts/reference_deployment.py start
```

`docker compose down -v` is intentionally not part of the normal runbook because `-v` deletes persistent state.

## 7. Backup

Backups are taken with Forge and Gateway stopped so the named volume is copied from a quiescent state.

```bash
python scripts/reference_deployment.py backup ./backups
```

The helper creates a timestamped `forge-data-YYYYMMDDTHHMMSSZ.tar`, then starts the reference services again.

Store backups outside the repository and preferably outside the host failure domain. A backup is not considered proven until a restore test has succeeded on a disposable/reference environment.

## 8. Restore

Restore is destructive and replaces the current Forge data volume contents.

1. Stop normal platform activity.
2. Verify the selected backup file and its provenance.
3. Run:

```bash
python scripts/reference_deployment.py restore ./backups/forge-data-YYYYMMDDTHHMMSSZ.tar --yes
```

If restore fails, the helper leaves services stopped instead of automatically continuing with ambiguous state. Diagnose the volume/archive before retrying.

After a successful restore:

```bash
python scripts/reference_deployment.py status
curl --fail http://127.0.0.1:8090/readyz
```

Then execute the currently available integration/recovery tests before treating the restored instance as usable.

## 9. Upgrade procedure

Never update a stateful reference deployment by blindly pulling and restarting.

1. Confirm the target commit/tag and read migration/release notes.
2. Run the current branch quality gates.
3. Create and verify a backup.
4. Record the currently deployed Git commit:

```bash
git rev-parse HEAD
```

5. Fetch and checkout the intended target revision.
6. Re-run:

```bash
make quality
python scripts/reference_deployment.py preflight
```

7. Build without starting:

```bash
docker compose --profile reference build forge-upstream gateway
```

8. Start the target revision:

```bash
python scripts/reference_deployment.py start
```

9. Verify `/healthz`, `/readyz`, logs and the available integration tests.
10. Only then discard the rollback window.

### Database/schema migrations

Forge owns its persistent data model. Any future explicit migration command must be versioned with Forge and added to this runbook before it is required by the reference profile. Until such a migration exists, upgrades must rely only on migration behavior already implemented and tested by the pinned Forge revision. Do not invent out-of-band SQL/schema edits.

## 10. Rollback procedure

If the new revision fails before any incompatible state migration has happened:

1. stop the reference deployment;
2. checkout the previously recorded revision;
3. rebuild and start;
4. verify health/readiness and integration tests.

If the upgrade changed persistent state in a way that is not backward compatible, restore the pre-upgrade backup first, then start the previous revision. Do not run an older binary against a data format known to be newer/incompatible.

## 11. Resource and permission baseline

Defaults are configurable through `.env`:

```dotenv
SCORESYMPHONY_FORGE_CPUS=2.0
SCORESYMPHONY_FORGE_MEMORY=2g
SCORESYMPHONY_GATEWAY_CPUS=1.0
SCORESYMPHONY_GATEWAY_MEMORY=512m
```

Both services have PID limits, bounded Docker JSON logs and restart policies. Gateway additionally runs read-only, with a small `/tmp` tmpfs, all Linux capabilities dropped and `no-new-privileges` enabled. Its image already runs as the dedicated non-root `scoresymphony` user.

Forge currently writes `/data` and still inherits its upstream container user model. Do not force an arbitrary UID/GID without a tested Forge permission migration. A future Forge non-root conversion must include named-volume ownership migration and rollback tests.

## 12. Reverse proxy and TLS

Not part of the current reference profile.

They may be added only after the production authentication/authorization/policy baseline is complete. When that happens, the external profile must preserve:

- Forge remaining private behind the ScoreSymphony integration boundary;
- authenticated/authorized Gateway access;
- explicit TLS termination and trusted-proxy handling;
- secret provisioning/rotation;
- minimal inbound ports;
- auditability and rollback.

## 13. Acceptance gate

The deployment-side acceptance evidence is:

- `make quality` passes;
- `docker compose --profile reference config --quiet` passes;
- preflight passes on a fresh supported host;
- Forge becomes healthy with persistent state;
- Gateway becomes healthy and ready through authenticated Forge recovery access;
- stop/start preserves state;
- backup + restore is tested;
- upgrade + rollback is tested with recorded revisions;
- no source-code edits are needed on the target host.

The **full Operable Deployment release gate remains blocked** until the upstream dependencies are satisfied, especially:

1. the complete Integrated Kernel process-level E2E slice;
2. the production Security/Policy/Approval bootstrap and enforcement needed before external exposure.

Do not close the release gate merely because Compose starts successfully.
