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
| CH-KVK-SMOKE-001 | Een expliciete kleine publieke frontendmeting mag niet ongemerkt tot bulk of een productprovider uitgroeien | RD-001; geïsoleerde lokale runner buiten wheel | [tien-GET-meting](../measurements/20260919-kvk-frontend-batch10.md), onafhankelijke pre-/postreview; R7 blijft `PARKED` |
| CH-RES-001 | Unieke run, SQLite, lock, snapshots | ADR-003, `core.py` | recoverytests |
| CH-RES-002 | Resume/requestjournal/cooldown | `kvk.py` | resumetests |
| CH-SEC-001 | Bounds, allowlists, redactie | `sources.py`, `core.redact` | securitytests |
| CH-MERGE-001 | CSV/TSV/XLSX + aliases/overrides | `merge_lists.py` | mergetests |
| CH-MERGE-002 | Conflictpolicies exact | ADR-002, `merge_lists.merge_lists` | policytests |
| CH-MERGE-003 | Geen netwerk/filter/limiet | `merge_lists.py` | offline E2E |
| CH-TEST-001 | >80% per file | ADR-004, `tools/check_coverage.py` | qualityrapport |
| CH-TEST-002 | Onafhankelijke subagentreview | `docs/reviews/` | reviewdocument |
| CH-DIST-001 | Wheel/sdist/bundle uit broncommit | `tools/release.py` | manifest/installtest |
| CH-DIST-002 | Publieke GitHub Release-asset | ADR-004 | `v1.0.0` gepubliceerd; [anonieme byte-identieke herdownload](../releases/20260919-v1.0.0-evidence.md) |
| CH-DIST-003 | Cross-platform wrappers/preflight | `scripts/`, `preflight.py` | wrapper/CI-smokes |

## Roadmapbesluiten en outcome-gates

| ID | Besluit/requirement | Canonieke bron | Bewijsstatus |
|---|---|---|---|
| CH-RM-001 | KVK-routemigratie, providerbulk en volledige bulkverificatie blijven geparkeerd tot expliciete activatie | `ROADMAP.md` RD-001/R7 | documentatiebesluit |
| CH-RM-002 | Outbound User-Agent blijft `company-lookup/0.1` zonder persoonlijke verwijzing | `ROADMAP.md` RD-002, `core.HTTP_USER_AGENT` | tests + toepasselijke CI |
| CH-RM-003 | Outcome-gates en bronopbrengst gaan vóór volgende release | `ROADMAP.md` RD-003/R1-R8 | R1-R6 en R8 uitgevoerd; R10-toolrelease gepubliceerd, R7/R9-productgates open |
| CH-RM-004 | Een brede set goede bronfamilies wordt vroeg verzameld; registratienummers bepalen routing, niet vroege toelating | `ROADMAP.md` RD-006/R3-R6 | vijf actieve families; R5/R6 `DONE` |
| CH-RM-005 | Geen productieharvest vóór representatieve pilot-, sample- en schaalpoorten | `ROADMAP.md` RD-004/R8-R9 | eigenaar-go/no-go vereist |
| CH-RM-006 | Verkleining gebeurt expliciet tussen raw-, candidate- en verified-lagen; onzekerheid veroorzaakt geen stil dataverlies | `ROADMAP.md` RD-006/R6/R8-R9 | R6/R8 bewezen; R9 geblokkeerd |
| CH-RM-007 | Kandidaten zonder initieel KVK-nummer blijven waardevol en mogen regulier, bewijsbaar worden gematcht/verrijkt | `ROADMAP.md` RD-007/R6/R8 | 50-recordpilot en behoud bij iedere outcome bewezen |
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
| CH-R6-001 | De 500-recordsample is deterministisch verdeeld over alle actieve bronfamilies en beschikbare identifierstrata | `sampling.py`, CLI `companies sample` | samplingfixtures + `docs/measurements/20260918-r6-stratified-sample.md` |
| CH-R6-002 | Iedere sample-input eindigt aantoonbaar in een kandidaatbeslissing of conflict zonder stil verlies | R6 count-closure | 500 = 500 decision-/conflictinputs; regressietests |
| CH-R6-003 | Een gestratificeerde handmatige beslissingsreview is exact gekoppeld aan de actuele queue en sluit zonder onverklaarde false merge | CLI `companies sample-review` | 25/25 `CONFIRMED`, reviewstatus `PASS` |
| CH-R6-004 | R8 krijgt vóór uitvoering een reproduceerbare kleine pilotpool en vast metriekcontract, zonder KVK-call in R6 | `r8_pilot_selection`, R6-rapport schema 1 | 50 kandidaten zonder direct KVK; terminale uitkomsten en capaciteitsmetrics vastgelegd |
| CH-R8-001 | Iedere pilotkandidaat krijgt exact één terminale uitkomst zonder verlies van no-match, ambigu of technische kandidaten | `matching.py`, R8-rapport schema 1 | 50/50 closure; regressietests + R8-meting |
| CH-R8-002 | Automatische KVK-koppeling vereist exacte naam plus onafhankelijk exact bronveld; naam/domein/score alleen is nooit voldoende | `_offline_match`, `_public_match` | unit-/branchtests; 15 voorlopige sterke-veldenmatches |
| CH-R8-003 | Meerdere KVK-kandidaten en bronconflicten worden niet gemerged; rechtsvorm/status blijven bronobservaties | terminale outcomecontract en verificatiestatus | ambigu-/conflicttests + 6 lokale ambigu-uitkomsten |
| CH-R8-004 | Review is gestratificeerd, exact aan de actuele queue gebonden en bepaalt thresholds pas na succesvolle kwaliteitscontrole | `kvk pilot-review`, reviewrapport schema 1 | 20/20 `CONFIRMED`; nul false/uncertain; R9-metriekgrenzen vastgelegd |
| CH-R8-005 | R8 publiceert atomisch, hervat alleen exact gebonden outcomes en stopt veilig op providerblokkades | requestjournal, providerlock, publication helpers | resume-, rollback-, live-limit- en blokkadetests |
| CH-GOV-001 | Doorlopende CI draait alleen op Python 3.14 voor macOS en Windows; overige combinaties zijn voor nieuwe wijzigingen `NOT_TESTED` | `.github/workflows/ci.yml`, `ROADMAP.md` RD-005 | workflowvalidatie + twee CI-jobs |
| CH-PREKVK-001 | Historisch vijfbronnencontract CH-2026-09-19-009, later vervangen door vierbronnenselectie | ADR-005, ADR-006 | historische geblokkeerde preview; geen vijfbronnenmaster |
| CH-PREKVK-002 | Conservatieve dedup bewaart iedere bronpayload precies één keer, conflicten zichtbaar en input→lijst sluit | `pre_kvk._write_group`, SQLite-spool | 292.666→289.916 preview; onafhankelijke volledige payload-/relatiecontrole |
| CH-PREKVK-003 | Een deelresultaat is apart gemarkeerd en voor KVK geblokkeerd; providerblokkade stopt live requests | `build_blocked_pre_kvk_preview`, lokale runner, ADR-005 | alle 289.916 previewregels `BLOCKED_SOURCE_INCOMPLETE`, nul KVK-requests; [meting](../measurements/20260919-pre-kvk-source-snapshot.md) |
| CH-PREKVK-004 | Zelfstandige vierbronnenvoorbereiding downloadt/hergebruikt IND, GLEIF, ANBI en DUO zonder Wikidata | `prepare.py`, `cli.py`, RD-008, ADR-006 | geïsoleerde tooltests en bestaande volledige lokale vierbronnenartefacten |
| CH-PREKVK-005 | Nieuwe vierbronnenmaster is full-scope, evidence- en hashgebonden met gesloten verliesvrije dedup | `pre_kvk.py`, ADR-006 | 292.666 inputregels → 289.916 masterregels, 2.750 merges; regressietests |
| CH-PREKVK-006 | Alleen expliciete KVK-Web-API-batches van maximaal tien, met journal/cooldown/evidence en partiële output | `pre_kvk_kvk.py`, ADR-006, RD-001/008 | offline provider-/stop-/resume-/gatingtests; full-list-verificatie niet vrijgegeven |
| CH-PREKVK-007 | Brede master blijft intact; expliciete, herzienbare filter vóór KVK met school/ANBI/no-hint/holding/stichting/bank/fonds/kerk/partijcriteria | `pre_kvk_filter.py`, ADR-007, RD-009 | [offline volledige meting](../measurements/20260919-pre-kvk-filter.md), criterium- en regressietests |
| CH-PREKVK-008 | Iedere uitsluiting is op ID met alle redenen terug te vinden; hashes, versie en count-closure zijn gebonden; KVK weigert ontbrekende/stale filter | `pre_kvk_filter.py`, `pre_kvk_kvk.py`, ADR-007 | 289.916 = 119.801 + 170.115; fail-closed/journaltests; onafhankelijke review |
| CH-PREKVK-009 | Expliciete publieke frontenddoorloop is minimaal 2s gepaced, hervat zonder stil opnieuw versturen, bewaart per-kandidaatvoortgang en publiceert COMPLETE pas bij gesloten kandidaatpartitie zonder actieve blokkade | `pre_kvk_kvk.py`, CLI, ADR-008, RD-001 | synthetische stop-/resume-/block-/CLI-tests, per-file coverage, onafhankelijke review; volledige live doorloop `NOT_TESTED` |
