# Lokale 3.0.1-wheel: begrensde E2E-herhaling

Status: **PASS voor een proefcohort van tien; geen productie- of schaalbewijs**.
Execution-ID: CH-2026-09-19-040. Datum: 19 september 2026.

De publieke 3.0.0-wheel en de vijf bronbestanden zijn niet gewijzigd. De
eerder op de CSV-veldgrens gestopte lokale run is met een nieuw gebouwde,
apart geïnstalleerde 3.0.1-wheel hervat. De definitieve wheel komt uit
broncommit `dca27d540682fde0547b6cfff6a24975f43cc85c` en heeft SHA-256
`e4a3c8e6db537dd02d8a41bad191837e5789c94e55c4a0f1a50af17e3c2c1047`.
De geïsoleerde installatietest en distributieverificatie waren `PASS`; er
is geen tag, GitHub Release of publicatie gemaakt. Tussentijdse lokale
builds van dezelfde versienaam gelden niet als distributieasset. Een
byte-identieke kopie van de definitieve build en zijn manifest staat lokaal
onder `.local/release-candidates/20260919T194539Z_dca27d540682/`;
`tools/release.py verify` op die kopie was opnieuw `PASS`. Deze map is
Git-genegeerd en is geen publieke release.

De vijf bestaande downloads zijn hergebruikt. De gecorrigeerde CSV-reader
las de master volledig: 317.806 unieke masterrijen, waarvan 191.425 na het
pre-KVK-filter overbleven en 126.381 auditbaar werden uitgesloten. De
vaste proefscope bevatte precies tien kandidaten; 191.415 kandidaten zijn
in deze proef niet bij KVK gecontroleerd. Het bestaande journal bevat
precies tien `SUCCEEDED`-verzoeken. Bij latere hervattingen zijn geen nieuwe
KVK-verzoeken verzonden.

Na de KVK-consolidatie waren er tien kandidaten: negen gingen door het
rechtsvormfilter en één ging naar rechtsvormreview. Van die negen was één
niet actief; acht vormden de eindlijst. De definitieve wheel schreef zelf
een nieuwe outputset met zeven databestanden en een manifest. `run e2e`
meldde `PARTIAL_EXPORTED`, `delivery_rows=8` en `audit_valid=true`; de
eindaudit controleerde 83 geregistreerde artefacten. `PARTIAL` betekent
hier dat de overige 191.415 kandidaten buiten de gekozen tiennummercohort
vallen, niet dat één van de tien verzoeken mislukte.

De minimale, lichte en volledige XLSX zijn onafhankelijk read-only geopend.
Elk heeft exact acht datarijen en dezelfde kolommen en celwaarden als zijn
TSV-tegenhanger. Alle KVK-nummers zijn tekstcellen; er staan geen formules
in deze bestanden. De lichte Excel bevat geen `response_json`,
`source_relations`, `candidate_id`, `provider` of `checked_at`. De zeven
bestanden, hun hashes en de partiële status sluiten in de eindaudit.

De kwaliteitsgate op de definitieve broncommit: 259 tests, alle eigen
uitvoerbare Pythonbestanden strikt boven 80% statementcoverage, lint,
typecontrole en publicatiescan `PASS`. Een onafhankelijke read-only review
van de parser, gerichte KVK-veldallowlist en auditprojectie vond geen
resterende codeblokkade. MacOS/Windows-CI voor deze commit, langdurige
verwerking en publieke distributie zijn **niet getest/niet uitgevoerd**.
De echte run, bronrijen, responsbewijs en Excelbestanden blijven uitsluitend
lokaal buiten Git.
