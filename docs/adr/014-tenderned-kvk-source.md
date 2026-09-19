# ADR-014 — TenderNed als directe KVK-bronhint

Datum: 2026-09-19 · Status: **IMPLEMENTED LOCALLY, LIVE FULL RUN NOT TESTED**
Execution IDs: CH-2026-09-19-030 (kwalificatie), CH-2026-09-19-031 (adapter)

## Context

R5 zag in de TenderNed-JSON achtcijferige leveranciers-ID's, maar kon de
veldsemantiek niet bewijzen. De officiële XLSX-leeswijzer definieert
`ON kvknummer` als KVK-nummer en de OCDS-mapping koppelt dit aan
`awards/suppliers/id`. De [vervolgmeting](../measurements/20260919-tenderned-qualification.md)
vindt substantieel nieuwe directe nummerhints buiten de huidige vierbronnenmaster.

## Besluit

TenderNed is de **vijfde bron voor nieuwe runs** via een begrensde, lokale
bronadapter. Bestaande vierbronnenruns behouden hun scope. De adapter gebruikt de officiële publieke
datasetdownloads, niet de credentialed XML-API. De JSON-awardleveranciers
zijn de dataroute voor het nieuwste jaar; de XLSX levert de eerdere jaren en
documenteert de veldsemantiek. Zo worden de twee representaties van het
laatste jaar niet dubbel geteld. Een achtcijferig ID mag als
`source_kvk_hint` worden opgeslagen met TenderNed-herkomst, nooit zonder meer
als actueel KVK-gevalideerde identiteit of onderneming.
De lokale `--xlsx/--json`-invoer is expliciet `LOCAL_UNVERIFIED` en mag geen
full-archive-master vrijgeven; alleen de officieel gedownloade, op jaarbereik
gecontroleerde snapshot passeert die poort.

Alleen een Nederlandse leveranciersrol mag naar de Nederlandse kandidaatlaag;
foreign referentienummers mogen niet op vorm alleen als KVK worden gepromoveerd.
Houd ontbrekende en ongeldige IDs, bronconflicten en originele herkomst lokaal
herleidbaar. De bestaande pre-KVK-filter en KVK-verificatie blijven ongewijzigd.
Een expliciete `run prepare-pre-kvk` of `run e2e` op een nieuwe run downloadt
de vijf bronnen; installatie of een gewone CLI-start doet dat niet. Geen
productie-run op grond van dit ADR.

## Voorwaarden vóór implementatie/activatie

1. Reconciliatie van alle 967 JSON-only-IDs met XLSX-publicaties is uitgevoerd:
   958 publicaties hebben daar een andere leveranciers-ID, negen geen geldig
   nummer. De JSON-rij moet een daadwerkelijke `awards[].suppliers[]`-relatie
   en Nederlandse land-evidence hebben; dit bewijst geen actuele KVK-identiteit.
2. Leg JSON-schema, bronversie, allowlist, grootte-/redirect-/timeoutgrenzen,
   voortgang en herstel vast; houd snapshotbytes en persoonsgegevens buiten Git.
3. Documenteer hergebruik en attributie voor lokale verwerking; beoordeel
   distributie/publicatie van afgeleide bedrijfsrecords afzonderlijk.
4. De adapter rapporteert kandidaten, KVK-hints, uitgesloten en reviewrijen
   met sluiting. Netto opbrengst na volledige identiteitsdedup en filter is
   **NOT_TESTED** zolang de nieuwe vijfbronnenrun niet compleet is.
5. Adapter-, security-, branch- en offline E2E-tests en de per-file-coverage-
   en reviewpoort zijn releasevoorwaarden voor de nieuwe broncode.

## Gevolgen

De bron is inhoudelijk aantrekkelijk voor directe KVK-hints en bredere
dekking, maar selectief voor aanbestedingswinnaars en niet onafhankelijk
geverifieerd. De gepubliceerde v2.0.0-wheel blijft ongewijzigd en gebruikt vier
bronnen; een nieuwe bronversie is nog niet gepubliceerd.
