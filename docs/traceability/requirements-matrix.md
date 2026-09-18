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
| CH-DIST-002 | Publieke GitHub Release-asset | ADR-004 | `REMOVED`; een volgende release moet opnieuw worden gekwalificeerd |
| CH-DIST-003 | Cross-platform wrappers/preflight | `scripts/`, `preflight.py` | wrapper/CI-smokes |

## Roadmapbesluiten en outcome-gates

| ID | Besluit/requirement | Canonieke bron | Bewijsstatus |
|---|---|---|---|
| CH-RM-001 | KVK-routemigratie, providerbulk en volledige bulkverificatie blijven geparkeerd tot expliciete activatie | `ROADMAP.md` RD-001/R7 | documentatiebesluit |
| CH-RM-002 | Outbound User-Agent blijft `company-lookup/0.1` zonder persoonlijke verwijzing | `ROADMAP.md` RD-002, `core.HTTP_USER_AGENT` | tests + toepasselijke CI |
| CH-RM-003 | Outcome-gates en bronopbrengst gaan vóór volgende release | `ROADMAP.md` RD-003/R1-R6 | roadmap; uitvoering gepland |
| CH-RM-004 | Een brede set goede bronfamilies wordt vroeg verzameld; registratienummers bepalen routing, niet vroege toelating | `ROADMAP.md` RD-006/R3-R6 | portfolio-opbouw gepland |
| CH-RM-005 | Geen productieharvest vóór representatieve pilot-, sample- en schaalpoorten | `ROADMAP.md` RD-004/R8-R9 | eigenaar-go/no-go vereist |
| CH-RM-006 | Verkleining gebeurt expliciet tussen raw-, candidate- en verified-lagen; onzekerheid veroorzaakt geen stil dataverlies | `ROADMAP.md` RD-006/R6/R8-R9 | ontwerpbesluit; implementatie gepland |
| CH-RM-007 | Kandidaten zonder initieel KVK-nummer blijven waardevol en mogen regulier, bewijsbaar worden gematcht/verrijkt | `ROADMAP.md` RD-007/R6/R8 | ontwerpbesluit; pilot gepland |
| CH-R1-001 | Iedere bron heeft catalogusschema 2 met expliciet identifier-, toegang-, meet-, herkomst- en laagprofiel | `sources.Source`, `SOURCE_HEADERS` | catalogus- en migratietests |
| CH-R1-002 | Bronnen zonder KVK-kolom en ontbrekende/ongeldige nummers blijven verliesvrij als kandidaten behouden | `sources.import_source`, `RAW_HEADERS` | import- en parserfixtures |
| CH-R1-003 | Outcome-rapportage meet per bron, dedup/conflict/review, kandidaatdiversiteit/-overlap, resourcegroei en closure per procesovergang | `workflow.outcome_metrics`, `workflow.report` | lege/dubbele/conflict- en volledige-pipelinefixtures |
| CH-R1-004 | `company-lookup/0.1` is zichtbaar in directe en browserrequests, runmetadata en rapportage | `core.HTTP_USER_AGENT`, browsercontext, `initialize_run`, outcome-rapport | bron/KVK-browser/run/rapporttests |
| CH-R2-001 | IND en Wikidata eindigen per capabilitymeting aantoonbaar als `LIVE_MEASURED`, `BLOCKED` of `FAILED` | `sources.measure_sources`, CLI `sources measure` | terminale succes-/foutpadtests + live aggregaatmeting |
| CH-R2-002 | Bronopbrengst, identifierkwaliteit, duplicaten en exacte KVK-overlap sluiten reproduceerbaar | capabilityrapport schema 1 | parser-/paginering-/closuretests + `docs/measurements/20260918-r2-source-capability.md` |
| CH-R2-003 | Actualiteit, voorwaarden, bias, begrenzing en request-/rate-limitobservaties zijn expliciet | broncatalogus + capabilityrapport | catalogusasserties + live meetdocument |
| CH-R3-001 | GLEIF-feasibility verifieert officiële voorwaarden, bulkroute, formaat, actualiteit en omvang vóór adapterbouw | `ROADMAP.md` R3 | `docs/measurements/20260918-r3-gleif-feasibility.md` + lokale hashes |
| CH-R3-002 | Nederlandse identifier-, legal-form- en statusvelden zijn begrensd gemeten zonder GLEIF-status als KVK-verificatie te behandelen | R3 meetcontract | statusgestratificeerde live sample van 200 + onafhankelijk reviewbewijs |
| CH-R3-003 | Adapterbouw start alleen na expliciet, onderbouwd go/no-go | `ROADMAP.md` R3/R4 | `GO`; R4 is `DONE` |
| CH-R4-001 | GLEIF Golden Copy-inname is streaming, expliciet en begrensd op host, redirects, bytes, ZIP-structuur, ratio, CSV-omvang en vrije ruimte | `gleif.py`, CLI `sources gleif` | veiligheids-/downloadtests + R4 live evidence |
| CH-R4-002 | Nederlandse kandidaten blijven behouden bij ontbrekend, ongeldig of niet-KVK registratie-ID, met originele identifier en reden | `gleif._raw_candidate`, kandidaat/rejected-contract | representatieve fixture + count-closure |
| CH-R4-003 | Evidence, bronlegal-form/status, resume/refresh en downstream-invalidatie zijn auditbaar zonder promotie tot KVK-verificatie | `gleif.collect_gleif`, innamerapport schema 1 | regressietests + `docs/measurements/20260918-r4-gleif-adapter.md` |
| CH-R4-004 | Outcome-rapport toont opbrengst en expliciete kandidaat- en geldige-KVK-overlap voor alle actieve bronparen | `workflow.outcome_metrics` | driebron capability-run + overlapfixture |
| CH-R5-001 | Zes kandidaatbronnen hebben een volledige, primair onderbouwde feasibilitykaart met gemeten sample, voorwaarden, bias, overlap, risico en besluit | R5-meetcontract | `docs/measurements/20260918-r5-source-portfolio.md` |
| CH-R5-002 | ANBI en DUO worden expliciet, streaming en begrensd ingenomen zonder impliciete bulkdownload | `public_registers.py`, CLI `sources anbi`/`sources duo` | adapter-, download-, ZIP-, XML-/CSV- en CLI-tests + live evidence |
| CH-R5-003 | Niet-KVK, ontbrekende, ongeldige en historische identifiers blijven herleidbaar als kandidaat of reviewrecord | kandidaat-/rejected-contract, bronrapport schema 1 | representatieve fixtures + volledige count-closure |
| CH-R5-004 | De actieve portfolio bevat minimaal vijf bruikbare bronnen uit minimaal drie onafhankelijke families | broncatalogus + outcome-rapport | vijf bronnen/vijf families in de R5-run |
| CH-GOV-001 | Doorlopende CI draait alleen op Python 3.14 voor macOS en Windows; overige combinaties zijn voor nieuwe wijzigingen `NOT_TESTED` | `.github/workflows/ci.yml`, `ROADMAP.md` RD-005 | workflowvalidatie + twee CI-jobs |
