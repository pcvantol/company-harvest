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

## Roadmapbesluiten en outcome-gates

| ID | Besluit/requirement | Canonieke bron | Bewijsstatus |
|---|---|---|---|
| CH-RM-001 | KVK-routemigratie en bulkverrijking blijven geparkeerd tot expliciete activatie | `ROADMAP.md` RD-001/R7 | documentatiebesluit |
| CH-RM-002 | Outbound User-Agent blijft `company-lookup/0.1` zonder persoonlijke verwijzing | `ROADMAP.md` RD-002, `core.HTTP_USER_AGENT` | tests + 12/12 CI |
| CH-RM-003 | Outcome-gates en bronopbrengst gaan vóór volgende release | `ROADMAP.md` RD-003/R1-R6 | roadmap; uitvoering gepland |
| CH-RM-004 | Een brede set goede bronfamilies wordt vroeg verzameld; registratienummers bepalen routing, niet vroege toelating | `ROADMAP.md` RD-006/R3-R6 | portfolio-opbouw gepland |
| CH-RM-005 | Geen productieharvest vóór representatieve pilot-, sample- en schaalpoorten | `ROADMAP.md` RD-004/R8-R9 | eigenaar-go/no-go vereist |
| CH-RM-006 | Verkleining gebeurt expliciet tussen raw-, candidate- en verified-lagen; onzekerheid veroorzaakt geen stil dataverlies | `ROADMAP.md` RD-006/R6/R8-R9 | ontwerpbesluit; implementatie gepland |
