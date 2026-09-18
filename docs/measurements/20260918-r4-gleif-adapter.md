# R4-capabilitymeting — GLEIF-adapter

Datum: 2026-09-18  
Status: `PASS`  
User-Agent bij HTTP-bronrequests: `company-lookup/0.1`

## Scope en bewijs

De verticale slice is uitgevoerd in een lokale, niet-gepubliceerde run met ID
`1789740162353845000_20260918T140242.353792Z_eb463e`. De GLEIF-input was de officiële
Level 1 Golden Copy-snapshot die eerder dezelfde dag tijdens R3 via de officiële route was
opgehaald. R4 maakte daarvan een byte-identieke immutable evidencekopie. Er staan geen
echte bedrijfsrecords, runbestanden of lokale paden in Git.

| Eigenschap | Waarde |
|---|---:|
| Evidence SHA-256 | `ac6f162d8240bf3a4778ff8c7c00e4702ba3eb6585b21abb15c11ee9ba6bb8c6` |
| ZIP | 504.128.840 bytes |
| CSV volgens ZIP-index | 4.987.509.988 bytes |
| GLEIF-limiet | 200 Nederlandse records |
| Records gelezen tot de limiet | 41.018 |
| Niet-Nederlandse records gepasseerd | 40.818 |
| Parserduur | 0,567925 seconde |

De lokale GLEIF-inname deed geen HTTP-request en rapporteert daarom terecht geen
User-Agent in haar acquisitieblok. De gecombineerde outcome-run deed wel kleine,
sequentiële requests voor de bestaande IND- en Wikidata-adapters met de centrale
`company-lookup/0.1`. De eerste Wikidata-poging met limiet 200 eindigde in een read-timeout;
een afzonderlijke herhaling met limiet 50 slaagde. Dit is geen productieharvest.

## GLEIF-uitkomst

| Metriek | Aantal |
|---|---:|
| Nederlandse records | 200 |
| Kandidaten | 200 |
| Ontbrekende juridische naam | 0 |
| Geldige KVK-hints | 172 |
| Unieke geldige KVK-hints | 172 |
| Ontbrekende/niet-KVK hints | 28 |
| Ongeldige KVK-hints | 0 |
| Identifier-reviewrecords | 28 |
| Ontbrekende legal-formcode | 0 |
| Ontbrekende statuscombinatie | 0 |

Zowel `NL = kandidaat + ontbrekende naam` als `NL = geldig + ontbrekend + ongeldig`
sloot exact. De 28 records zonder bruikbare KVK-hint bleven kandidaat en behielden hun
bronidentifier. GLEIF-legal-form- en statuswaarden zijn uitsluitend brondata.

## Gecombineerde verticale slice

Na toevoeging van 200 begrensde IND-records en 50 begrensde Wikidata-records bevatte de
ruwe kandidaatlaag 450 records uit drie onafhankelijke bronfamilies. Daarvan hadden 418
een syntactisch geldige registratiehint, 28 geen KVK-hint en 4 een ongeldige hint. De
dedupovergang sloot `450 → 450`; latere KVK-/filterovergangen waren bewust
`NOT_AVAILABLE`, zodat de totale status correct `PARTIAL_CLOSED` bleef.

De largest-family-share was 44,44%. Voor elk van de drie bronparen staat kandidaat- en
geldige-KVK-overlap expliciet in het outcome-rapport, ook wanneer die nul is. De drie
naam/kandidaatoverlappen waren 0. Exacte geldige-KVK-overlap was 1 voor
GLEIF–Wikidata en 0 voor GLEIF–IND en IND–Wikidata. Dit zijn sample-uitkomsten, geen
populatieschattingen.

## Veiligheid en kwaliteit

- 50 tests slagen op Python 3.14; lint en strict typecheck slagen.
- `gleif.py` behaalt 283/294 statements coverage (96,26%); ieder eigen uitvoerbaar
  Pythonbestand blijft boven 80%.
- Fixtures dekken schemafouten, onveilige/meervoudige ZIP-inhoud, grootte-, ratio- en
  ruimtegates, redirect-host, HTTP 429 zonder fallback, neutrale User-Agent, identifier-
  behoud, count-closure, hergebruik, refresh en downstream-invalidatie.
- De publicatiescan houdt de lokale 504 MB evidence en alle echte records buiten Git.

## Conclusie

R4 voldoet aan zijn exitcriteria. De eerste brede bulkadapter levert aantoonbaar volume,
behoudt onzekerheid zonder vroeg dataverlies en sluit aan op de bestaande kandidaat-,
dedup- en outcomerapportage. R5 kan nu als volgende increment meerdere bronfamilies via
dezelfde contracten kwalificeren en toevoegen. KVK-routemigratie en bulkverificatie
blijven geparkeerd.
