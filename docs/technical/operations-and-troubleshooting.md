# Operations en troubleshooting

- Exit 0: succes; 3: validatie; 4: providerblokkade/cooldown; 5: parsing/data; 6: lock; 7: integriteit; 130: onderbreking.
- `BROWSER_UNAVAILABLE`: installeer passend Chromium met dezelfde Playwright-packageversie.
- `PUBLIC_ACCESS_BLOCKED`/429: stop; de vierbronnen-KVK-batch blokkeert vervolgverzoeken
  op deze run tot een afzonderlijk toegang-/gebruiksbesluit. Wissel niet naar
  browser of een nieuw journal om de blokkade te omzeilen.
- `run prepare-pre-kvk` kan lang duren en veel lokale schijfruimte gebruiken:
  inspecteer eerst de bron- en evidencegates; dezelfde run hergebruikt afgeronde
  downloadartefacten en een identieke master.
- `kvk pre-kvk-batch` produceert alleen `PARTIAL`-uitkomsten; voer geen
  `kvk consolidate`/export op basis hiervan uit.
- `kvk pre-kvk-run` bewaart journal, voortgangs-JSON en tussentijdse TSV's
  lokaal. Hervat met dezelfde `--run-dir` zonder filterwijziging. Bestaande
  verzoeken worden niet herhaald. `SENT_OUTCOME_UNKNOWN` of `FAILED` blijft
  als niet-geverifieerde unresolved zichtbaar; gesloten input kan toch
  COMPLETE-artefacten krijgen, maar export vergt `--allow-partial`.
  Een 401/403/429 blokkeert verder gebruik tot een afzonderlijk besluit.
- In v1.0.0 registreert `export --allow-partial` ook het outputmanifest als
  `PARTIAL`, terwijl `audit verify` dit manifest alleen als `COMPLETE` opzoekt.
  Daardoor geeft de eindaudit dan ten onrechte
  `MISSING_REQUIRED:outputset_manifest`. Beschouw een partiële v1.0.0-levering
  niet als audit-PASS. In de nog niet gepubliceerde 1.1.0-broncode leest de
  audit het nieuwste PARTIAL-manifest en controleert alle hashes en relaties.
- `run e2e --limit-kvk-check N` bewaart de vaste cohort en haar hash in de
  run. Gebruik dezelfde `--run-dir` en dezelfde limiet/interval/exportlimiet
  bij hervatten. Een nieuwe run in dezelfde datamap passeert geen eerder
  gejournalde publieke toegangs- of rateblokkade.
- `run is vergrendeld`: controleer eigenaar/proces; verwijder een lock niet op alleen ouderdom.
- `audit verify` faalt: publiceer/exporteer niet; behoud de run en onderzoek ontbrekende of gewijzigde bestanden.
- Mergeconflicten zijn datawaarschuwingen, geen technisch mislukte run; inspecteer alle conflictbestanden.
