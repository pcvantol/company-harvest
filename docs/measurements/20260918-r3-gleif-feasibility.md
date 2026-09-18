# R3-feasibility — GLEIF Level 1 Golden Copy

Meetdatum: 2026-09-18  
Status: `GO` voor adapterbouw in R4  
User-Agent: `company-lookup/0.1`

## Primaire documentatie en toegang

- De [GLEIF LEI Data Terms of Use](https://www.gleif.org/en/meta/lei-data-terms-of-use)
  beschrijven gratis toegang tot individuele, gedeeltelijke en volledige LEI-data en
  stellen de data beschikbaar onder CC0.
- De [Golden Copy-downloadpagina](https://www.gleif.org/en/lei-data/gleif-golden-copy/download-the-golden-copy)
  beschrijft complete, technisch gededupliceerde Level 1-bestanden in XML, CSV en JSON,
  met drie publicaties per dag en delta's voor acht uur, dag, week en maand.
- De [GLEIF API](https://www.gleif.org/en/lei-data/gleif-api) is gebaseerd op dezelfde
  Golden Copy en ondersteunt filters. De
  [Registration Authorities List](https://www.gleif.org/en/lei-data/code-lists/gleif-registration-authorities-list)
  identificeert `RA000463` als het Nederlandse Handelsregister van de Kamer van Koophandel.
- De [LEI-CDF 3.1-specificatie](https://www.gleif.org/en/lei-data/access-and-use-lei-data/level-1-data-lei-cdf-3-1-format)
  maakt onderscheid tussen entiteitsstatus en de status van de LEI-registratie.

## Live meting

De officiële API rapporteerde Golden Copy-peildatum `2026-09-18T00:00:00Z` en 197.093
records met Nederlands juridisch adres. Om zowel positieve als negatieve statussemantiek
te zien, zijn twee afzonderlijke eerste pagina's van elk 100 records gemeten: één met
`entity.status=ACTIVE` en één met `entity.status=INACTIVE`. Dit is een
statusgestratificeerde capabilitysample en nadrukkelijk geen schatting van de
statusverdeling.

| Metriek | Uitkomst |
|---|---:|
| Sample totaal | 200 |
| `registeredAs` aanwezig | 200 |
| Exact achtcijferig | 200 |
| Unieke achtcijferige waarden | 200 |
| Registratieautoriteit `RA000463` | 200 |
| Legal-formcode aanwezig | 200 |
| Entiteitsstatus aanwezig | 200 |
| LEI-registratiestatus aanwezig | 200 |
| Onderscheiden legal-formcodes | 5 |

In het actieve stratum waren de 100 entiteitsstatussen `ACTIVE` en de 100
LEI-registratiestatussen `ISSUED`. In het inactieve stratum waren deze respectievelijk
`INACTIVE` en `RETIRED`. Dit toont bruikbare velden, niet dat beide statusparen altijd
samenvallen of dat zij actuele KVK-activiteit bewijzen.

Het officiële endpoint `.../publishes/lei2/latest.csv` verwees om
`2026-09-18T08:00:00+00:00` naar een immutable CSV-ZIP van 504.128.840 bytes en
voltooide met HTTP 200. De twee JSON-sample-responses waren samen 495.190 bytes.

Daarna is de echte CSV-ZIP volledig sequentieel gescand met Python 3.14 op macOS, direct
vanuit het ZIP-member en met alleen Nederlandse unieke nummers in een tijdelijke SQLite-
tabel. Er is geen uitgepakte CSV op schijf en geen volledige recordset in het geheugen
geplaatst. De kwalificatiescan gebruikte `zipfile.ZipFile.open` → `io.TextIOWrapper` →
`csv.DictReader`, filterde exact op `Entity.LegalAddress.Country == "NL"` en accepteerde
een KVK-nummer uitsluitend bij autoriteitscode `RA000463` én regexsemantiek
`^[0-9]{8}$`. Unieke nummers gingen per batches van 5.000 naar een SQLite-tabel met
primaire sleutel; `resource.getrusage(...).ru_maxrss` leverde de macOS-piek-RSS.

| Volledige bulkmeting | Uitkomst |
|---|---:|
| Alle Golden Copy-records | 3.434.330 |
| Nederlandse records | 197.093 |
| Records onder KVK-autoriteit `RA000463` | 194.992 |
| Records onder een andere autoriteit | 2.101 |
| Geldige achtcijferige KVK-records | 194.956 |
| Unieke geldige KVK-nummers | 194.884 |
| Ontbrekende KVK-ID binnen `RA000463` | 10 |
| Ongeldige KVK-ID binnen `RA000463` | 26 |
| Legal-formcode aanwezig | 197.093 |
| Entiteitsstatus aanwezig | 197.093 |
| LEI-registratiestatus aanwezig | 197.093 |
| Gecomprimeerde omvang | 504.128.840 bytes |
| Ongecomprimeerde CSV-omvang | 4.987.509.988 bytes |
| Tijdelijke SQLite-omvang | 2.805.760 bytes |
| Verwerkingstijd | 47,486966 seconden |
| Piek-RSS | 24.150.016 bytes |

De minimale gemeten tijdelijke opslag zonder uitgepakte kopie is daarmee 506.934.600
bytes voor ZIP plus SQLite. R4 moet daarnaast ruimte reserveren voor evidence, rejected-
en kandidaatoutputs en vóór download een vrije-schijfruimtegate uitvoeren. De meting
bewijst dat sequentiële verwerking ruim onder de omvang van de volledige dataset in
geheugen blijft; zij is een kwalificatiemeting, geen productieharvest.

## Semantische grenzen en bias

GLEIF omvat rechtspersonen met een LEI en is daardoor sterk gericht op entiteiten die
aan financiële transacties of andere LEI-gebruikssituaties deelnemen. Het is geen volledig
Nederlands ondernemingsregister. `registeredAs` bij `RA000463` is een sterke,
herleidbare KVK-hint, maar blijft brondata. `entity.status`, `registration.status` en de
ISO-20275 legal-formcode worden verliesvrij bewaard en mogen niet stil als actuele
KVK-verificatie of definitief eenmanszaakfilter worden gebruikt.

## Go/no-go

Alle R3-poorten zijn voldoende positief voor `GO`:

- toegang en hergebruik zijn officieel gedocumenteerd als gratis en CC0;
- de actuele bulkroute is reproduceerbaar en levert een versieerbare CSV-ZIP;
- de Nederlandse indexopbrengst is betekenisvol;
- de volledige scan vindt 194.884 unieke geldige achtcijferige KVK-nummers die expliciet
  onder autoriteitscode `RA000463` vallen en bewaart
  ontbrekende/ongeldige waarden als afzonderlijke meetuitkomsten;
- de volledige Golden Copy is in 47,49 seconden verwerkt met 24.150.016 bytes piek-RSS
  zonder uitgepakte CSV of volledige dataset in geheugen;
- publicatiepeildatum, Golden Copy-model en deltafrequentie geven een duidelijk
  provenance- en refreshmodel.

## Lokaal bewijsanker

Meet-ID: `20260918T133900Z`. Ruwe responses blijven lokaal onder `.local/r3/` en worden
niet gepubliceerd.

- actief stratum SHA-256: `73ec3a6eeae12bc47165f26c360262c68b1042c0d3ba5af40994d5401776a144`;
- inactief stratum SHA-256: `d9b0b706b340b9964c1819e0a75158cc2aae4a134cc290ccbc0c3e1bbd267639`;
- downloadheaderketen SHA-256: `f4690f85182a2dd758d1be5dfc4e4a89bf0addabf7edd1696e259acfab3d8d80`;
- Nederlandse totaalrespons SHA-256: `28969094bfb83526b48c5fded393144e6a6ef7cd5137d1fa05ef77c139c19716`;
- Golden Copy CSV-ZIP SHA-256: `ac6f162d8240bf3a4778ff8c7c00e4702ba3eb6585b21abb15c11ee9ba6bb8c6`;
- resource-/telrapport SHA-256: `e89cb08b7a8a0a33152ab8b28ebe45ac25e2b9f78b6fdf40396417a2db1ccc9a`;
- tijdelijke dedupdatabase SHA-256: `8861dba55ad31a2ee94814fce0991084d6158d9165bf526e50d6c8426d6a3331`.
