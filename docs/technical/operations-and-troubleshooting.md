# Operations en troubleshooting

- Exit 0: succes; 3: validatie; 4: providerblokkade/cooldown; 5: parsing/data; 6: lock; 7: integriteit; 130: onderbreking.
- `BROWSER_UNAVAILABLE`: installeer passend Chromium met dezelfde Playwright-packageversie.
- `PUBLIC_ACCESS_BLOCKED`/429: stop en hervat later; wissel niet naar browser om de blokkade te omzeilen.
- `run is vergrendeld`: controleer eigenaar/proces; verwijder een lock niet op alleen ouderdom.
- `audit verify` faalt: publiceer/exporteer niet; behoud de run en onderzoek ontbrekende of gewijzigde bestanden.
- Mergeconflicten zijn datawaarschuwingen, geen technisch mislukte run; inspecteer alle conflictbestanden.

