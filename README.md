# ScoreSymphony Agent Platform

`AI-Agent-VPS` ist das zentrale Monorepo für die ScoreSymphony Agent Platform.
Es verbindet einen von Forge abgeleiteten deterministischen Execution-Kern, einen
von Hermes abgeleiteten Orchestrierungs-Kern und ScoreSymphony-eigene Verträge,
Adapter, Gateway-, Worker-, Security- und Betriebsbausteine.

Stand dieser Baseline: **2026-09-02**.

> **Status:** Die Plattform besitzt bereits einen belastbaren Integrationskern,
> ist aber noch **kein Production Candidate**. Historical Event Recovery,
> Forge-Command-Mapping, ein authentifiziertes ScoreSymphony Gateway, ein
> Hermes-seitiger Gateway-Client/CLI, der deterministische Shell-Worker und
> gemeinsame Security Contracts sind vorhanden. Live-SSE-Projektion,
> Forge-eigene Worker-Dispatch-Integration, dauerhafte Command-Idempotenz und der
> vollständige prozessübergreifende End-to-End-Slice fehlen noch.

## Verbindliches Architekturmodell

- **Hermes ist der einzige intelligente Orchestrator.**
- **Forge ist die kanonische deterministische Authority** für Projekte, Tasks,
  Task-Versionen, Executions, Workspaces, Worker-Dispatch, Tests/Belege, Reviews,
  Gates, Merge und Lifecycle-Events.
- **Worker führen begrenzte Aufträge aus** und besitzen keine konkurrierende
  Orchestrierung, Review-, Merge- oder Lifecycle-Authority.
- **ScoreSymphony besitzt die Integrationsgrenze**: versionierte V1-Verträge,
  Adapter, Gateway und projektspezifische Policy-/Security-Integration.
- **Command-Submission ist nicht gleich Command-Erfolg.** `CommandReceipt`
  bestätigt nur die Annahme beziehungsweise Ablehnung der Submission; terminale
  Wahrheit kommt über versionierte `command.*`-Events.
- Hermes importiert keine privaten Forge-Datenbankmodelle oder internen Services.
- Das V1-Feld `actor` ist behauptete Command-Daten und **kein Authentifizierungs-
  nachweis**. Runtime-Ingress muss es an eine authentifizierte Identität binden.
- Nicht kompatibler Fremdcode wird nicht in den MIT-Kern kopiert. Externe
  Komponenten werden mit Herkunft, Version, Lizenz und Integrationsgrenze
  getrennt behandelt.

## Was bereits implementiert ist

### Verträge und Forge-Grenze

- Forge-konformes V1-Command-/Event-Vokabular mit `execution_id` statt `run_id`.
- Projektgebundenes `create_task` und Task-Versionen für optimistic concurrency.
- Öffentliche Forge-Operationen für alle aktuellen V1-Commands.
- Authentifizierter historischer Domain-Event-Read auf `/api/v1/events` mit
  exklusivem Sequence-Cursor, begrenztem `limit`, stabilen DTOs, geordneten
  Ergebnissen und Tests.
- Parameterloses Forge `/api/v1/events` bleibt der bestehende Live-SSE-Pfad.
- Forge-Recovery-Adapter mit Cursor-/Reihenfolgevalidierung und V1-Projektion
  unterstützter Lifecycle-Events.

### ScoreSymphony Integration

- Authentifizierter HTTP-Transport zu Forge mit begrenzten Timeouts und
  fail-closed Fehlerbehandlung.
- ScoreSymphony Gateway mit Command-Ingress, Historical Recovery, Health und
  Readiness.
- Getrennte Credentials für Hermes → Gateway und Gateway → Forge.
- Hermes-seitiger Gateway-Client und `scoresymphony-hermes` CLI.
- In-Process-Integrationstest über Hermes-Serialisierung → Gateway →
  Forge-Adapter → Historical Recovery → Hermes-V1-Validierung.

### Worker und Security Foundation

- Deterministischer Shell-Worker mit executable allowlisting,
  Workspace-Confinement, deterministischer Umgebung, Timeouts, Cancellation,
  expliziten Retry-Versuchen und Write-Path-Policy/Evidence.
- Security Contracts für Principals, Credentials, Scopes, Authorization,
  Policies und Approvals.
- Referenz-Policy ist default-deny mit `DENY > REQUIRE_APPROVAL > ALLOW`.
- Approval-Bindung an konkrete Operation/Policy, Ablaufzeit, standardmäßig kein
  Self-Approval und konsumierter Zustand gegen Replay.

### Repository und Betrieb

- Gepinnte Forge- und Hermes-Upstream-Snapshots mit Provenienz und Lizenzhinweisen.
- Python-, Contract-, Deployment-, Compose- und Forge-Rust-Validierung in CI.
- Governance-/PR-/Issue-Vorlagen.
- Nicht-root Gateway-Container und Runtime-Konfigurationsvertrag.

Die genaue Abgrenzung zwischen **fertig**, **teilweise implementiert** und
**nicht implementiert** steht in [CURRENT_STATE.md](CURRENT_STATE.md).

## Was als Nächstes fehlt

Der aktuelle kritische Pfad zum Release-Gate **Integrated Kernel** ist:

1. Live Forge SSE konsumieren und unterstützte Lifecycle-Events in kanonische
   V1-Events projizieren.
2. Reconnect und `events.resync_required` über den bereits vorhandenen
   Historical-Read race-sicher abfangen.
3. Den deterministischen Shell-Worker ausschließlich über Forge-eigenen
   Dispatch/Lifecycle anbinden.
4. Dauerhafte Command-Idempotenz beziehungsweise sichere Recovery für
   mehrdeutige Submission-Fehler in Forge-eigenem State/Event-Log lösen.
5. Einen prozessübergreifenden Hermes → Gateway → Forge → Worker →
   Review/Gate/terminales Event End-to-End-Test automatisieren.
6. Erst danach das Release-Gate **Integrated Kernel** schließen und mit
   Recoverable Runtime, Production Security und reproduzierbarem Deployment
   fortfahren.

Die vollständige Reihenfolge bis zum Production Candidate steht in
[ROADMAP.md](ROADMAP.md).

## Repository-Struktur

```text
core/forge/                 gepinnter Forge-Upstream-Snapshot
core/hermes/                gepinnter Hermes-Upstream-Snapshot
platform/                   ScoreSymphony Contracts, Adapter und Runtime
agents/                     begrenzte ScoreSymphony Worker
contracts/                  zusätzliche gemeinsame Verträge/Schemas
config/                     Plattform- und Runtime-Konfiguration
scripts/                    Validierung, Deployment- und Upstream-Werkzeuge
tests/                      Contract-, Runtime-, Security- und Integrationstests
docs/                       ADRs, Architektur-, Security- und Betriebsdokumente
compose.yaml                 aktuelle Referenz-/Smoke-Deployment-Basis
Dockerfile.gateway          ScoreSymphony Gateway Container
UPSTREAMS.yaml              kanonische Upstream-Pins und Update-Policy
THIRD_PARTY_NOTICES.md      Herkunft und Lizenzhinweise
```

## Baseline lokal prüfen

Voraussetzungen sind die im Repository dokumentierten Python-, Docker-/Compose-
und Rust-Abhängigkeiten für die jeweils ausgeführten Gates.

```bash
make quality
make compose-check
```

Die CI bleibt für den vollständigen Repository-Check maßgeblich, insbesondere
für die Forge-Rust-Prüfungen.

## Frischer Repository-Start

Dieses Repository wird als historische Entwicklungsquelle vorbereitet. Für einen
frischen GitHub-Start soll **der geprüfte Working Tree von `main`, nicht die alte
`.git`-Historie**, übernommen werden. Dadurch bleiben Code, Tests, Lizenzen und
Provenienz erhalten, während alte Branches, PRs, Issues und experimentelle
Zwischenstände im archivierten Repository verbleiben.

Die exakte Übergabeprozedur, die zu erhaltenden Dateien, die neu einzurichtenden
GitHub-Regeln und ein sauberes Issue-/Milestone-Backlog stehen in
[BASELINE_HANDOFF.md](BASELINE_HANDOFF.md).

## Upstreams und Lizenz

`UPSTREAMS.yaml` ist die kanonische Quelle für Upstream-Repository, Pin,
Integrationsart und Lizenzstatus. `THIRD_PARTY_NOTICES.md` dokumentiert die
übernommenen Snapshots und ihre Herkunft.

Der ScoreSymphony-eigene Code steht unter der MIT-Lizenz. Eingebundene
Upstream-Snapshots behalten ihre jeweiligen Copyright- und Lizenzhinweise.
Bei einem frischen Repository-Start dürfen `LICENSE`, Upstream-Lizenzen,
`UPSTREAMS.yaml` und `THIRD_PARTY_NOTICES.md` nicht entfernt oder durch die neue
Git-Historie ersetzt werden.