# Gebruikershandleiding

Installeer in een eigen virtual environment en kies `COMPANY_HARVEST_DATA_DIR`. `run init --print-path` maakt uitsluitend een lokale run. Voer daarna de CLI-stappen in de volgorde uit die `company-harvest --help` en subcommand-help tonen. `run execute` gebruikt dezelfde services en checkpoints.

Gebruik voor ontwikkeling bijvoorbeeld:

```bash
export COMPANY_HARVEST_DATA_DIR=/Users/pcvantol/Documents/GitHub/company-harvest
RUN_DIR="$(company-harvest run init --target 10000 --print-path)"
company-harvest sources discover --run-dir "$RUN_DIR"
company-harvest sources collect --run-dir "$RUN_DIR"
company-harvest companies merge --run-dir "$RUN_DIR"
company-harvest kvk preflight --run-dir "$RUN_DIR" --provider auto
company-harvest kvk resolve --run-dir "$RUN_DIR" --provider auto --limit 1
company-harvest report --run-dir "$RUN_DIR"
```

Stop bij een providerblokkade en hervat later met dezelfde run en `--resume`. Een browserfallback vereist apart geïnstalleerd Chromium. Merge gebruikt `companies merge-lists --left … --right …`; standaard worden naamconflicten uitgesloten. Bekijk altijd reports, conflicts, rejected en reviewbestanden.

Een lokale bron hoeft nog geen KVK-nummer te bevatten. Importeer bijvoorbeeld alleen namen met:

```bash
company-harvest sources import --run-dir "$RUN_DIR" --input organisaties.csv --source-id eigen_lijst --name-column Naam
```

Geef `--kvk-column KVK` mee wanneer zo'n kolom bestaat. Geldige nummers worden als hint behouden; ontbrekende en ongeldige waarden blijven respectievelijk `MISSING` en `INVALID` en verwijderen het bronrecord niet.

`report` schrijft een leesbaar runrapport en een `outcome_report.json`. Dat machineleesbare rapport bevat per-broncijfers, identifierdekking, deduplicatie/conflicten, reviewvolume, kandidaatdiversiteit en gemeten overlap, count-closure per beschikbare procesovergang, doorlooptijd, piekgeheugen en lokale opslaggroei. `PARTIAL_CLOSED` betekent dat alle uitgevoerde overgangen sluiten maar latere stappen nog niet zijn uitgevoerd; alleen `COMPLETE_CLOSED` bestrijkt de hele pipeline. Nieuwe runs en rapporten vermelden ook de uitgaande User-Agent `company-lookup/0.1`.
