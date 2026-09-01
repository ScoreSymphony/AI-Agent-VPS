# Component Manager

This directory owns ScoreSymphony integration contracts for core and external
components. Runtime installers do not belong here. The canonical registry is
the root `COMPONENTS.yaml`; executable external adapters and installers live
under `external/`.

The current implementation supports listing, inspecting, and validating the
registry. Installation is intentionally deferred until install, health,
rollback, license-display, and audit contracts are implemented.
