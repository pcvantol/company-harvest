# Changelog

## Unreleased

- Broncodeversie 1.1.1: de audit van het nieuwste PARTIAL-outputmanifest eist
  een expliciete, met de run overeenkomende status en vijf bestanden met
  dezelfde registratiestatus. Gerichte regressies bewijzen een geldige
  partiële levering en weigeren ontbrekende status, gewijzigd bestand of een
  manifest dat niet met de afgeronde runstatus overeenkomt.
  v1.0.0 blijft ongewijzigd; 1.1.1 is nog niet gepubliceerd.
- De nog niet gepubliceerde 1.1.0-tool accepteert uitsluitend Python 3.14.x:
  packagingmetadata, runtime, hostpreflight, installers en ontwikkelinstellingen
  wijzen andere minorversies af. De gepubliceerde v1.0.0 blijft ongewijzigd.
- Broncodeversie 1.1.0: expliciet `run e2e`-commando voor volledige
  vierbronnenvoorbereiding, publieke KVK-check, canonisering, filters, export,
  rapport en audit. `--limit-kvk-check N` bindt een onveranderlijke cohort van
  maximaal N kandidaten aan de run; hervatten kan de grens niet verhogen.
  Als kandidaten buiten de cohort vallen, blijft de levering zichtbaar PARTIAL
  ten opzichte van de volledige pre-KVK-lijst; zij bevat altijd maximaal N
  unieke KVK-nummers. Onopgeloste kandidaten binnen de cohort eisen afzonderlijk
  `--allow-partial`.
- Partiële outputsets worden nu door `audit verify` inclusief manifest,
  bestandshashes, cohortbinding en count-closure gevalideerd. De oude
  `MISSING_REQUIRED:outputset_manifest`-valspositieve melding is in de
  broncode opgelost; release v1.0.0 blijft ongewijzigd.
- Nieuwe run-, artefact-, evidence- en snapshotnamen beginnen met een leesbare
  UTC-tijd `yyyy.mm.dd_hhMMss` plus een korte willekeurige suffix, zonder de
  lange nanosecondeprefixed waarde. Bestaande runs en bestandsnamen blijven
  ongewijzigd en leesbaar; de broncode is nog niet als nieuwe release gepubliceerd.
- De historische Git-tag `v0.1.0` is op eigenaarsverzoek uit de lokale
  checkout en van `origin` verwijderd; broncommit en releasebewijs blijven.
- Korte functionele v1.0.0-snelstart met exacte commando's, hervatpad en
  outputgates naast de uitgebreide commandotabel; geen uitvoerbare wijziging.

## 1.0.0 - 2026-09-19

- Sluit het tijdelijke SQLite-spoolbestand van de pre-KVK-master expliciet vóór
  opruimen, zodat de workflow ook op Windows werkt.
- Expliciete hervatbare `kvk pre-kvk-run` voor de publieke frontend-Web-API:
  minimaal twee seconden tussen verzoekstarts, per-kandidaatjournal,
  atomische voortgang, duurzame tussentijdse TSV's en pas na een gesloten
  kandidaatpartitie COMPLETE-artefacten voor de vervolgworkflow.
- Herzienbare offline toelatingsfilter tussen vierbronnenmaster en KVK-batch:
  behoud van de volledige master, afzonderlijke KVK-geschikte lijst en
  uitsluitingsledger met alle redenen, criteria, hashes en gesloten aantallen.
  Ontbrekende/stale filtersets en onverenigbare KVK-journals blokkeren requests.
- Zelfstandige vierbronnenvoorbereiding (IND, GLEIF, ANBI, DUO), zonder
  automatische Wikidata-download, met volledige evidencecontrole en één
  gededupliceerde master; expliciete hervatbare KVK-Web-API-batches van
  maximaal tien kandidaten publiceren uitsluitend partiële uitkomsten.
- Eenmalige brede pre-KVK-bronmomentopname met full-scope/evidence-gates,
  verliesvrije conservatieve disk-dedup en aparte geblokkeerde preview bij
  onvolledige bron; Wikidata HTTP 429 verhindert de vijfbronnenmaster.
- Bron-HTTP leest begrensd als stream en valideert ook redirectdoelen;
  Wikidata-paginering pauzeert tussen publieke requests.
- Geïsoleerde, niet-gepubliceerde tien-GET-capabilitymeting via de publieke
  KVK-frontend-Web-API; ten tijde van die meting bleven R7 en bulkgebruik geparkeerd.
- GitHub Release-object `v0.1.0` en de vijf assets op eigenaarsverzoek verwijderd; op dat moment bleven de Git-tag en historische kwalificatie-evidence behouden.
- Doorlopende CI teruggebracht tot Python 3.14 op macOS en Windows; Ubuntu en Python 3.11–3.13 gelden voor nieuwe wijzigingen als `NOT_TESTED`.
- Broncatalogusschema 2 met expliciete identifier-, toegang-, voorwaarden-, actualiteits-, bronfamilie-, herkomst- en laagprofielen.
- Verliesvrije lokale bronimport zonder verplichte KVK-kolom; ontbrekende en ongeldige nummers blijven meetbare kandidaten.
- Machineleesbaar outcome-rapport met count-closure, per-bronopbrengst, deduplicatie, review, diversiteit en resourcegebruik.
- Uitgaande bron- en KVK-requests, runmetadata en rapportage gebruiken `company-lookup/0.1` zonder persoonlijke verwijzing.
- Begrensde live capabilitymeting voor IND en Wikidata met terminale foutstatussen,
  identifierclosure, duplicaten, exacte overlap, bronactualiteit en request-/rate-limitobservaties.
- GLEIF Level 1 Golden Copy-feasibility met `GO`: officiële CC0-bulkroute, actuele
  omvang en begrensde Nederlandse identifier-/rechtsvorm-/statusmeting vastgelegd.
- Streaming GLEIF Golden Copy-adapter met begrensde download/ZIP-gates, immutable
  evidence, Nederlandse filtering, verliesvrije identifier-review, resume/refresh en
  zichtbare opbrengst plus exacte KVK-overlap in het outcome-rapport.
- Zes aanvullende bronfeasibilitykaarten en een vijf-familiesportfolio; expliciete
  streaming ANBI- en DUO-adapters met veilige ZIP/XML/CSV-verwerking, immutable evidence,
  volledige historie-/identifierclosure en behoud van kandidaten zonder KVK-nummer.
- Beveiligde ANBI XML-verwerking via vastgepinde `defusedxml`; oudere broninventarissen
  worden uitsluitend via expliciete migrerende acties verliesvrij aangevuld; pure reads
  veranderen historische runs niet.
- Deterministische R6-sampling over bronfamilie en identifierstatus met een gesloten
  500-record dedupmeting, expliciete reviewimport, resourcebaseline en reproduceerbare
  50-recordselectie plus metriekcontract voor de R8-matchingpilot.
- Begrensde R8-identiteitsmatching met offline-first sterke-veldenbewijs, sequentiële
  publieke frontendfallback, exact hervatjournal, vijf terminale uitkomsten,
  transactionele reviewlifecycle en reviewgestuurde R9-thresholds zonder naam-onlymerge.

## 0.1.0 - 2026-09-18

- Eerste implementatie van HARVEST-stappen 1–8 en zelfstandige MERGE_LISTS-stap 9.
- Lokale runstate, logging, locks, snapshots, checksums, audit verify/trace en herstelbare KVK-journalering.
- Publieke bronadapters, publieke KVK HTTP-/Playwright-contracten, filtering en veilige CSV/XLSX-export.
- Host/installatie/runwrappers, quality- en releasehulpmiddelen en Nederlandse documentatie.
