# ScoreSymphony Agent Platform

`AI-Agent-VPS` ist das zentrale Monorepo fuer die ScoreSymphony Agent Platform.
Es kombiniert einen von Forge abgeleiteten Execution-Kern, einen von Hermes
abgeleiteten Orchestrierungs-Kern und die eigene ScoreSymphony-Control-Plane.

## Verbindliches Architekturmodell

- **Hermes** ist die einzige intelligente Orchestrierungsinstanz.
- **Forge** verwaltet deterministisch Tasks, Runs, Worktrees, CI, Review, Merge
  und Audit-Ereignisse.
- **Worker** fuehren klar begrenzte Auftraege aus und orchestrieren nicht selbst.
- **Externe Komponenten** werden getrennt registriert und unter ihrer jeweiligen
  Originallizenz installiert. Nicht-MIT-Code wird nicht in den MIT-Kern kopiert.

Der aktuelle Stand ist eine verifizierbare Monorepo-Baseline mit ausfuehrbarer
V1 Contract Runtime. Forge und Hermes sind als gepinnte, lizenzgepruefte
Upstream-Snapshots enthalten. Dokumentierte nicht-MIT-Unterpfade von Hermes
sind ausgeschlossen. Ein laufender Transport und die funktionale Kopplung sind
bewusst noch nicht als fertig markiert.

## Struktur

```text
core/forge/                 gepinnter Forge-Snapshot
core/hermes/                gepinnter Hermes-Snapshot
platform/contracts/v1/      stabile Integrationsvertraege
platform/components/        Component-Manager-Grundlage
agents/                     ScoreSymphony-Worker
external/                   Adapter und Installer fuer getrennte Komponenten
config/                     Plattformrichtlinien
scripts/                    Validierung und Upstream-Pruefung
tests/                      Baseline- und Contract-Tests
docs/                       Architektur- und Betriebsdokumentation
```

## Lokale Baseline pruefen

Voraussetzungen: Python 3.11 oder neuer.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.lock
python scripts/validate_baseline.py
pytest
```

Optionale unveraenderte Upstream-Container koennen fuer Smoke-Tests gebaut
werden:

```bash
docker compose --profile upstream-smoke build
```

Das ist noch kein integrierter Plattformbetrieb. Der erste funktionale
Meilenstein ist in [CURRENT_STATE.md](CURRENT_STATE.md) festgehalten.

## Upstreams

| Komponente | Quelle | gepinnter Commit | Lizenz |
|---|---|---|---|
| Forge | `ForgeAILab/forge` | `d49fac7ca6b3b1ce310c3e950aaac64a080f60a6` | MIT |
| Hermes Agent | `NousResearch/hermes-agent` | `b81383ec215400cbbc7d9768cf4ce45a19f9092a` | MIT |

Die kanonischen Metadaten stehen in `UPSTREAMS.yaml`. Herkunft und
Lizenzhinweise werden in `THIRD_PARTY_NOTICES.md` erhalten.

## Lizenz

Der ScoreSymphony-Code steht unter der MIT-Lizenz. Eingebundene Upstream-
Snapshots behalten ihre jeweiligen Copyright-Hinweise und Lizenzdateien.
Externe Komponenten sind nicht Teil des MIT-Kerns.
