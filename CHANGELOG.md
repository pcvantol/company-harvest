# Changelog

## Unreleased

- Doorlopende CI teruggebracht tot Python 3.14 op macOS en Windows; Ubuntu en Python 3.11–3.13 gelden voor nieuwe wijzigingen als `NOT_TESTED`.
- Broncatalogusschema 2 met expliciete identifier-, toegang-, voorwaarden-, actualiteits-, bronfamilie-, herkomst- en laagprofielen.
- Verliesvrije lokale bronimport zonder verplichte KVK-kolom; ontbrekende en ongeldige nummers blijven meetbare kandidaten.
- Machineleesbaar outcome-rapport met count-closure, per-bronopbrengst, deduplicatie, review, diversiteit en resourcegebruik.
- Uitgaande bron- en KVK-requests, runmetadata en rapportage gebruiken `company-lookup/0.1` zonder persoonlijke verwijzing.

## 0.1.0 - 2026-09-18

- Eerste implementatie van HARVEST-stappen 1–8 en zelfstandige MERGE_LISTS-stap 9.
- Lokale runstate, logging, locks, snapshots, checksums, audit verify/trace en herstelbare KVK-journalering.
- Publieke bronadapters, publieke KVK HTTP-/Playwright-contracten, filtering en veilige CSV/XLSX-export.
- Host/installatie/runwrappers, quality- en releasehulpmiddelen en Nederlandse documentatie.
