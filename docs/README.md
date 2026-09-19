# Documentatie

De huidige broncode is **3.0.1 (nog niet gepubliceerd)**; de publieke wheel
blijft **3.0.0**. Beide bevatten
TenderNed als vijfde bron en een afzonderlijke lichte KVK-/bronexport.
Versie 2.0.0 was de vorige release zonder die functies, maar de publieke
release en tag zijn inmiddels ingetrokken; gebruik voor nieuwe installaties
alleen 3.0.0.
Handleidingen hieronder beschrijven het publieke 3.0.0-contract en
markeren de 3.0.1-parsercorrectie en gerichte lichte-veldtoelating
afzonderlijk; 3.0.0 stopte in een
[live E2E-proef](measurements/20260919-v3-live-wheel-e2e-10-blocked.md)
vóór KVK. Zie ook
[versies en migraties](technical/versioning-and-migrations.md).

- Canonieke koers en uitvoeringsvolgorde: [roadmap](../ROADMAP.md).
- Functioneel: [E2E-handleiding (release 3.0.0)](functional/e2e-command.md),
  [eindbestanden en veldherkomst](functional/output-files.md),
  [gebruikershandleiding](functional/user-guide.md),
  [datadictionary](functional/data-dictionary.md),
  [workflow](functional/workflow-and-business-rules.md),
  [scope en requirements](functional/scope-and-requirements.md),
  [acceptatie](functional/acceptance-criteria.md) en
  [consolevoortgang](functional/console-logging.md).
- Historisch, niet geschikt als installatieroute vanaf een schone pc:
  [v1.0.0-snelstart](functional/snelstart-v1.0.0.md) en
  [v1.0.0-commandotabel](functional/v1-end-to-end-commands.md).
- Technisch: [architectuur](technical/architecture.md), [persistence](technical/persistence-and-recovery.md), [providers](technical/source-and-kvk-providers.md), [pre-KVK-lijst](technical/pre-kvk-list.md), [gestratificeerde sampling](technical/stratified-sampling.md), [logging/audit](technical/logging-and-audit.md), [security](technical/configuration-and-security.md), [kwaliteit](technical/testing-and-quality-gates.md), [installatie](technical/packaging-and-installation.md), [versies](technical/versioning-and-migrations.md), [operations](technical/operations-and-troubleshooting.md), [releaseverificatie](technical/release-and-download-verification.md).
- Besluiten: [ADR-register](adr/README.md). Traceerbaarheid: [matrix](traceability/requirements-matrix.md).
- Metingen: [R2-broncapability IND en Wikidata](measurements/20260918-r2-source-capability.md), [R3 GLEIF-feasibility](measurements/20260918-r3-gleif-feasibility.md), [R4 GLEIF-adapter](measurements/20260918-r4-gleif-adapter.md), [R5-bronportfolio](measurements/20260918-r5-source-portfolio.md), [R6-sample](measurements/20260918-r6-stratified-sample.md), [geblokkeerde pre-KVK-momentopname](measurements/20260919-pre-kvk-source-snapshot.md).
- Uitvoeringen: [prompts](prompts/INDEX.md), [reviews](reviews/README.md), [releases](releases/README.md).
