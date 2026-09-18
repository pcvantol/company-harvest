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
```

Stop bij een providerblokkade en hervat later met dezelfde run en `--resume`. Een browserfallback vereist apart geïnstalleerd Chromium. Merge gebruikt `companies merge-lists --left … --right …`; standaard worden naamconflicten uitgesloten. Bekijk altijd reports, conflicts, rejected en reviewbestanden.

