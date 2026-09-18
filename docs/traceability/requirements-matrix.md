# Requirements en traceability

| ID | Requirement | Ontwerp/code | Test/bewijs |
|---|---|---|---|
| CH-FUN-001 | HARVEST-stappen 1–8 via gedeelde services | `cli.py`, `sources.py`, `workflow.py` | CLI/E2E-tests |
| CH-FUN-002 | Exacte minimale export en stabiele selectie | `workflow.export` | exporttests |
| CH-DATA-001 | Voorzichtige normalisatie/dedup | ADR-002, `workflow.merge_candidates` | deduptests |
| CH-DATA-002 | Canoniek uniek KVK + unresolved | `kvk.py`, `workflow.consolidate` | provider/matchtests |
| CH-DATA-003 | Rechtsvorm/status UNKNOWN apart | `workflow.py` | filtertests |
| CH-DATA-004 | Lokale data buiten publicatie | `.gitignore`, `quality.scan` | publicatiescan |
| CH-KVK-001 | Publieke HTTP alleen na observatie | ADR-001, `PublicHttpProvider` | preflighttests |
| CH-KVK-002 | Playwright gewone frontendfallback | `PublicBrowserProvider` | gemockte/browser smoke |
| CH-KVK-003 | Geen fallback bij blokkade/rate limit | `kvk.resolve`, cooldowns | foutpadtests |
| CH-RES-001 | Unieke run, SQLite, lock, snapshots | ADR-003, `core.py` | recoverytests |
| CH-RES-002 | Resume/requestjournal/cooldown | `kvk.py` | resumetests |
| CH-SEC-001 | Bounds, allowlists, redactie | `sources.py`, `core.redact` | securitytests |
| CH-MERGE-001 | CSV/TSV/XLSX + aliases/overrides | `merge_lists.py` | mergetests |
| CH-MERGE-002 | Conflictpolicies exact | ADR-002, `merge_lists.merge_lists` | policytests |
| CH-MERGE-003 | Geen netwerk/filter/limiet | `merge_lists.py` | offline E2E |
| CH-TEST-001 | >80% per file | ADR-004, `tools/check_coverage.py` | qualityrapport |
| CH-TEST-002 | Onafhankelijke subagentreview | `docs/reviews/` | reviewdocument |
| CH-DIST-001 | Wheel/sdist/bundle uit broncommit | `tools/release.py` | manifest/installtest |
| CH-DIST-002 | Publieke GitHub Release-asset | ADR-004 | release/downloadbewijs |
| CH-DIST-003 | Cross-platform wrappers/preflight | `scripts/`, `preflight.py` | wrapper/CI-smokes |

