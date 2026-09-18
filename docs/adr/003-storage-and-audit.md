# ADR-003 — Opslag, timestamps en audit

Status: Accepted. Requirements: CH-RES-001..006, CH-DATA-006.

SQLite/WAL beheert state en journals; bestanden bevatten immutable snapshots en exports. Iedere runtimeoutput krijgt een eigen nanoseconde/UTC/suffix-prefix; vaste projectbestanden en packagingstandaardnamen zijn uitzonderingen. Atomische swaps plus reconciliërende audit zijn gekozen boven een onmogelijke cross-filesystem/database-transactie.

