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
- `run is vergrendeld`: controleer eigenaar/proces; verwijder een lock niet op alleen ouderdom.
- `audit verify` faalt: publiceer/exporteer niet; behoud de run en onderzoek ontbrekende of gewijzigde bestanden.
- Mergeconflicten zijn datawaarschuwingen, geen technisch mislukte run; inspecteer alle conflictbestanden.
