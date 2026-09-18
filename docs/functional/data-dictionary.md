# Datadictionary

| Veld | Betekenis |
|---|---|
| Bedrijfsnaam | Canonieke of expliciet gekozen weergavenaam; tekst. |
| KVK-nummer | Exact acht ASCII-cijfers; tekst. Mag bewijsbaar worden gematcht/verrijkt en wordt pas na verificatie de definitieve ondernemingssleutel. |
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
| response_json | Verliesvrije lokaal bewaarde relevante providerresponse. |
| raw_legal_form/raw_status | Ongewijzigde publieke providerwaarden. |
| checked_at | Werkelijk verificatiemoment; cachegebruik verandert dit niet. |
| verification_status | Bij merge altijd `UNCONFIRMED_IMPORTED`, tenzij bestaand bewijs apart herleidbaar is. |

CSV-uitvoer is UTF-8, tabgescheiden en correct gequote. Leeg betekent onbekend. Logbestanden bevatten IDs, geen volledige responses. De minimale spreadsheet heeft exact de kolommen `Bedrijfsnaam`, `KVK-nummer`.

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
