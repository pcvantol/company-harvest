# Changelog

## Unreleased

- Eenmalige brede pre-KVK-bronmomentopname met full-scope/evidence-gates,
  verliesvrije conservatieve disk-dedup en aparte geblokkeerde preview bij
  onvolledige bron; Wikidata HTTP 429 verhindert de vijfbronnenmaster.
- Bron-HTTP leest begrensd als stream en valideert ook redirectdoelen;
  Wikidata-paginering pauzeert tussen publieke requests.
- Geïsoleerde, niet-gepubliceerde tien-GET-capabilitymeting via de publieke
  KVK-frontend-Web-API; R7 en bulkgebruik blijven geparkeerd.
- GitHub Release-object `v0.1.0` en de vijf assets op eigenaarsverzoek verwijderd; de Git-tag en historische kwalificatie-evidence blijven behouden.
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
