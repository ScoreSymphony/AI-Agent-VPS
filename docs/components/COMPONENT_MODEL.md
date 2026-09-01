# Component model

`COMPONENTS.yaml` is the canonical catalog. The initial manager is deliberately
read-only: it validates and displays declared state but does not execute
installers.

Installation support will require, per component:

- an immutable version or commit;
- original source and license metadata;
- a checksum or verifiable source commit;
- an isolated target path or container;
- an explicit operator confirmation;
- a health check;
- an adapter contract;
- rollback and removal behavior;
- audit events.

The first cataloged external component is Qwen Code. It is disabled and not
bundled. Its presence in the catalog does not install it.
