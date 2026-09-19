# Datadictionary

| Veld | Betekenis |
|---|---|
| Bedrijfsnaam | Canonieke of expliciet gekozen weergavenaam; tekst. |
| KVK-nummer | Exact acht ASCII-cijfers; tekst. De actuele publieke KVK-check vereist een directe bronhint en accepteert alleen een exact gelijk teruggegeven nummer. Pas daarna is het de definitieve ondernemingssleutel. |
| candidate_id | Stabiele hash van bronidentiteit voor requestjournalering. |
| source_registration_raw | Ongewijzigde identifiertekst uit de bron, ook wanneer die ongeldig is. |
| registration_validation_status | `VALID`, `MISSING` of `INVALID`; ontbrekend/ongeldig verwijdert de kandidaat niet. |
| source_legal_form/source_status | Ongewijzigde bronwaarden; niet automatisch KVK-gevalideerd. |
| candidate_layer | Datalaag van het record: `raw`, `candidate` of `verified`. |
| source_lei | GLEIF-LEI uit een rejected record; bronidentiteit, geen KVK-nummer. |
| registration_authority | GLEIF-registratieautoriteit; alleen `RA000463` routeert de bronidentifier als KVK-hint. |
| rejection_reason | Expliciete reden voor identifier- of naamreview, zoals `MISSING_KVK`, `INVALID_KVK`, `NON_KVK_REGISTRATION_AUTHORITY` of `MISSING_LEGAL_NAME`. |
| raw_record_json | Volledig oorspronkelijk GLEIF-record in lokale rejected-uitvoer; wordt niet gepubliceerd als documentatiebewijs. |
| source_relations | JSON-cel met bron-ID, URL en oorspronkelijke rij. |
| source_payloads_json | JSON-cel met alle oorspronkelijke kandidaatrijen die in één pre-KVK-regel vertegenwoordigd zijn; verliesvrije bronlaag, geen verificatie. |
| source_count | Aantal oorspronkelijke kandidaatrijen in die regel; som over de lijst moet het broninputtotaal sluiten. |
| dedup_status | `KEPT_SINGLE`, `MERGED_DIRECT_HINT` of `SOURCE_CONFLICT`; alleen identieke naam plus dezelfde geldige directe hint wordt automatisch samengevoegd. |
| kvk_queue_status | `READY_FOR_KVK_MATCHING`/`READY_FOR_KVK_VERIFICATION` in een complete master, `REVIEW_REQUIRED` bij conflict, of altijd `BLOCKED_SOURCE_INCOMPLETE` in een gedeeltelijke preview. Geen van deze statussen bewijst reeds KVK-verificatie. |
| pre_kvk_eligible | Volledige masterrijen die de actuele toelatingsregels passeren; uitsluitend deze TSV is invoer voor `kvk pre-kvk-batch` en `kvk pre-kvk-run`. |
| pre_kvk_kvk_progress.json | Atomische checkpoint met inputhash, totaal, journalstaten en resterend aantal; `state.sqlite3` is de bron van waarheid. |
| pre_kvk_kvk_matches.tsv / pre_kvk_kvk_unresolved.tsv | Lokale tussentijdse outputs; op hervatten opnieuw uit de journal gereconstrueerd en pas bij gesloten kandidaatpartitie zonder actieve blokkade als COMPLETE geregistreerd. Onzekere uitkomsten blijven unresolved. |
| pre_kvk_excluded | Lokale TSV-ledger van iedere uitgesloten kandidaat: ID, naam, bron-IDs, primaire reden en alle overlappende redenen. Volledige bronpayloads blijven in de master. |
| pre_kvk_filter_metadata | JSON met regelversie, letterlijke criteria, master-/outputhashes, count-closure en primaire/overlappende redenaantallen. |
| NO_DIRECT_KVK_HINT | Er is geen geldig direct KVK-nummer in de verzamelde brondata; dit bewijst niet dat de organisatie geen KVK-inschrijving heeft. |
| response_json | Verliesvrije lokaal bewaarde relevante providerresponse. |
| raw_legal_form/raw_status | Ongewijzigde publieke providerwaarden. |
| Website (bron) / Sector (bron) | Bronwaarde voor dezelfde kandidaat-ID en hetzelfde KVK-nummer; in de geïntegreerde pre-KVK-route de eerste niet-lege waarde uit samengevoegde bronrijen. Niet door KVK bevestigd of geraden. |
| Rechtsvorm (KVK) / Status (KVK) | Leesbare rechtsvorm/status uit de publieke KVK-hit; bij HTTP wordt status van `actief` afgeleid. Alleen bekende niet-eenmanszaakvormen en expliciet actieve statussen komen in de levering. |
| Plaats (KVK) / Land (KVK) | Locatie uit of afgeleid van de publieke zoekhit; land kan als Nederland uit een Nederlandse bezoeklocatie zijn afgeleid. |
| checked_at | Werkelijk verificatiemoment; cachegebruik verandert dit niet. |
| verification_status | Bij merge altijd `UNCONFIRMED_IMPORTED`, tenzij bestaand bewijs apart herleidbaar is. |

CSV-uitvoer is UTF-8, tabgescheiden en correct gequote. Leeg betekent
onbekend, niet een negatieve KVK-bevestiging. Logbestanden bevatten IDs,
geen volledige responses. De minimale spreadsheet heeft exact de kolommen
`Bedrijfsnaam`, `KVK-nummer`. De aparte lichte 3.0.0-spreadsheet heeft vaste
KVK-naam/nummer/rechtsvorm/status/plaats/land- en bronwebsite/-sectorkolommen;
aanwezige overige zakelijke publieke velden (o.a. inschrijving, activiteiten,
handelsnamen en adres) verschijnen als platte tekstkolommen. `response_json`,
`source_relations` en technische metadata staan daar niet in. Zie
[eindbestanden en veldherkomst](output-files.md) voor de complete bestandsrollen
en het variabele kolomcontract. De oudere 2.0.0-wheel heeft deze lichte
spreadsheet niet; versie 3.0.0 wel.

Broncatalogusschema 2 legt per bron onder meer registratie-ID-profiel, bronfamilie, toegangsvorm, voorwaarden, refreshinformatie, meetstatus, gemeten aantal, werkelijk gemeten overlap, inclusiereden, herkomstkwaliteit en kandidaatlaag vast. Ontbrekende optionele velden uit oudere catalogi worden expliciet als leeg/unknown genormaliseerd; bestaande waarden blijven behouden.

Capabilityrapport schema 1 bevat per bron `measurement_status`, `measurement_scope`,
`collection_complete`, bron-/identifieraantallen, duplicaten, parserafwijzingen,
`count_closure`, requestobservaties, voorwaarden en bias. Exacte overlap gebruikt alleen
syntactisch geldige achtcijferige KVK-nummers en is `NOT_AVAILABLE` zodra niet beide
bronmetingen live zijn geslaagd.

GLEIF-innamerapport schema 1 bevat evidenceherkomst en -hash, ingestscope, bestandsgrootten,
duur, kandidaat-/review-/identifier-/velddekking en closure. `source_status` combineert de
twee ongewijzigde bronvelden als `entity=<waarde>;registration=<waarde>`; deze tekst heeft
geen KVK-verificatiestatus.
