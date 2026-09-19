# Operations en troubleshooting

- Exit 0: succes; 3: validatie; 4: providerblokkade/cooldown; 5: parsing/data; 6: lock; 7: integriteit; 130: onderbreking.
- `BROWSER_UNAVAILABLE`: installeer passend Chromium met dezelfde Playwright-packageversie.
- `PUBLIC_ACCESS_BLOCKED`/429: stop; de publieke KVK-check blokkeert vervolgverzoeken
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
  niet als audit-PASS. Vanaf versie 2.0.0 leest de
  audit het nieuwste PARTIAL-manifest en controleert ook de verplichte status,
  alle vijf bijbehorende bestandsregistraties, hashes en relaties. De nog
  gepubliceerde 3.0.0-wheel gebruikt manifest schema 2 met zeven
  bestanden; `audit verify` accepteert ook oudere schema-1-sets.
- `run e2e --limit-kvk-check N` bewaart de vaste cohort en haar hash in de
  run. Gebruik de exacte eerder afgedrukte `--run-dir` en dezelfde
  KVK-limiet/interval bij hervatten. Broncollectors hergebruiken geregistreerde
  voltooide outputs bij gelijke instellingen; de vervolgvalidatie controleert
  ook bron- en evidencebindingen en hashes. Bij ongeldige binding stopt de
  run of haalt een collector de bron opnieuw op. Master en filter blijven
  eveneens hashgebonden. Een
  afgebroken bronstap kan opnieuw moeten downloaden; gedeeltelijke
  downloadbytes zijn niet gegarandeerd hervatbaar. De KVK-zoekfase slaat
  gejournalde kandidaten over, ook `SENT_OUTCOME_UNKNOWN` na een crash:
  controleer deze expliciet en gebruik zo nodig `--allow-partial`. Een
  afgeronde export passeert geen bron- of KVK-fase meer, maar ondergaat
  rapport-/auditcontrole. Een nieuwe run in dezelfde datamap passeert geen
  eerder gejournalde publieke toegangs- of rateblokkade.
- `--export-limit` en `export --limit` zijn vanaf versie 3.0.0 verwijderd.
  Alle actieve rijen worden geleverd. Een oude
  onvoltooide E2E-run met mogelijk bindende exportlimiet wordt niet stil
  gemigreerd; gebruik de oorspronkelijke toolversie of start bewust nieuw.
- `run is vergrendeld`: controleer eigenaar/proces; verwijder een lock niet op alleen ouderdom.
- `audit verify` faalt: publiceer/exporteer niet; behoud de run en onderzoek ontbrekende of gewijzigde bestanden.
- `onbekend KVK-responsveld in lichte export`: de publieke respons bevat een
  veld buiten het gekwalificeerde zakelijke veldcontract. De export is vóór
  publicatie gestopt; inspecteer de lokale responsevidence en kwalificeer
  het veld voordat de code/allowlist wordt aangepast. Verwijder het veld
  niet handmatig uit bewijs en behandel een oude outputset niet als nieuw.
- `companies_delivery_light.xlsx` ontbreekt: controleer `--version`. De
  oudere 2.0.0-wheel heeft dit bestand niet; een nieuwe export met de
  3.0.0-wheel maakt het. Hergebruik de
  `outputset_manifest.json`-map die de run meldt, niet willekeurig de
  oudste tijdgestempelde map. Zie [het outputcontract](../functional/output-files.md).
- Een bestaande ontwikkel-venv kan na wijziging van `pyproject.toml` nog een
  oude distributieversie melden, ook als de broncode bewerkt is. Installeer
  de actuele bron opnieuw in die venv en controleer `company-harvest
  --version` vóór de E2E-run; een 2.0.0- of oudere melding bewijst niet dat
  de nieuwe lichte export geïnstalleerd is.
- Mergeconflicten zijn datawaarschuwingen, geen technisch mislukte run; inspecteer alle conflictbestanden.
