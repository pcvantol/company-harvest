# Bron- en KVK-providers

De IND-adapter leest het actuele openbare register Arbeid. De Wikidata-adapter gebruikt
Wikidata-property `P3220` (KvK company ID) met deterministische, begrensde
SPARQL-paginering; de veiligheidslimiet blokkeert een schijnbaar volledig resultaat.
`sources collect` hergebruikt standaard het laatste bronartefact en `--refresh` maakt en
registreert nieuwe evidence.

`sources import` voegt lokale CSV-, TSV-, XLSX- en HTML-tabellen met een expliciete naamkolom en optionele KVK-kolom toe. Iedere input krijgt eerst een unieke evidence-snapshot. Ontbrekende of ongeldige KVK-waarden blijven als kandidaten bewaard en worden afzonderlijk gemeten. Alle bronnen blijven biased en vormen geen gegarandeerd volledige populatie.

De broninventaris gebruikt catalogusschema 2. Legacy inventarissen worden bij lezen naar dit schema genormaliseerd zonder bestaande waarden te verliezen. Live aantallen en overlap blijven leeg of `NOT_MEASURED` totdat een werkelijke meting ze onderbouwt. `sources measure` meet IND volledig en Wikidata begrensd, legt request-/byte-/duur- en rate-limitobservaties vast en schrijft ook bij een blokkade een terminaal capabilityrapport. Een ontbrekende rate-limitheader bewijst niet dat er geen limiet geldt.

KVK gebruikt uitsluitend de functionaliteit achter `https://www.kvk.nl/zoeken/`. Op 2026-09-18 is tijdens een gewone naamzoekactie de publieke GET-route `https://web-api.kvk.nl/zoeken/v3/search` waargenomen, inclusief de door de frontend meegegeven publieke profiel-ID en parameters. Rechtstreekse reproductie en browserflow zijn elk met één kandidaat bewezen. `public-browser` blijft technische fallback. 401/403/429, CAPTCHA, actieve cooldown en toegangseisen veroorzaken stop/pauze, geen transportpendelen. De implementatie vraagt geen KVK-key en bevat geen geldbudget. Response-evidence wordt als gehasht audit-artefact geregistreerd.

Zowel de directe bron-/KVK-clients als de Playwright-browsercontext gebruiken `company-lookup/0.1`. De browsertest controleert de contextoptie expliciet; er wordt geen persoonlijke URL of gebruikersnaam meegestuurd.

Geraadpleegd 2026-09-18: KVK-gebruikersvoorwaarden (bijgewerkt 2026-06-17) vermelden aanvullende voorwaarden voor grootschalig opvragen/hergebruik; de IND-bronpagina meldt maandelijkse actualisatie en op 2026-09-03 bijgewerkte data, terwijl de IND-proclaimer hergebruik met bronvermelding toestaat; Wikidata beschrijft de gestructureerde data als CC0 en verlangt herkenbare, beheerste toegang; Playwright documenteert response-observatie. Live veldsemantiek blijft `UNKNOWN` totdat gemeten.

R4 implementeert GLEIF Level 1 Golden Copy als afzonderlijke bulkadapter via `sources
gleif`. Zonder `--archive` downloadt zij de officiële laatste CSV-ZIP; met `--archive`
neemt zij een lokale, eerder gekwalificeerde ZIP byte-identiek over. De download gebruikt
uitsluitend HTTPS naar `goldencopy.gleif.org`, maximaal drie redirects en
`company-lookup/0.1`. De limieten zijn 600 MiB gecomprimeerd, 6 GiB ongecomprimeerd en
een compressieratio van maximaal 15. De ZIP moet exact één niet-versleutelde CSV op het
hoogste niveau bevatten en de run moet vooraf voldoende vrije ruimte hebben.

De parser streamt de CSV en gebruikt een tijdelijke SQLite-set voor unieke KVK-nummers.
Alleen `Entity.LegalAddress.Country=NL` komt in de kandidaatlaag. Een achtcijferige
`RegistrationAuthorityEntityID` geldt uitsluitend bij autoriteit `RA000463` als geldige
KVK-hint. Ontbrekende, ongeldige en aan een andere autoriteit gekoppelde identifiers
verwijderen de organisatie niet: de kandidaat behoudt de originele identifiertekst en
krijgt `MISSING` of `INVALID`; rejected bevat de reden en het volledige ruwe bronrecord.
Alleen een ontbrekende juridische naam verhindert een kandidaatrecord.

`EntityLegalFormCode` blijft `source_legal_form`; `EntityStatus` en `RegistrationStatus`
blijven als afzonderlijk gelabelde componenten in `source_status` (`entity=…;registration=…`).
Een ontbrekende component telt als ontbrekende statusdekking. Zij vervangen geen actuele KVK-verificatie. Iedere run registreert de
evidencehash, scope, duur, count-closure en identifier-/velddekking. Een identieke invoer
met dezelfde limiet wordt hergebruikt; `--refresh` of een andere input maakt downstream
stappen pas na geslaagde parsing stale. `sources collect` blijft bewust alleen voor IND
en Wikidata, zodat een gewone run niet onverwacht een bulkbestand downloadt.
