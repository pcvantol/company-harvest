# Gebruikershandleiding

Installeer in een eigen virtual environment en kies `COMPANY_HARVEST_DATA_DIR`. `run init --print-path` maakt uitsluitend een lokale run. Voer daarna de CLI-stappen in de volgorde uit die `company-harvest --help` en subcommand-help tonen. `run execute` gebruikt dezelfde services en checkpoints.

Gebruik voor ontwikkeling bijvoorbeeld:

```bash
export COMPANY_HARVEST_DATA_DIR=/Users/pcvantol/Documents/GitHub/company-harvest
RUN_DIR="$(company-harvest run init --target 10000 --print-path)"
company-harvest sources discover --run-dir "$RUN_DIR"
company-harvest sources measure --run-dir "$RUN_DIR" --wikidata-limit 200
company-harvest sources collect --run-dir "$RUN_DIR"
company-harvest sources gleif --run-dir "$RUN_DIR" --limit 200
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

`sources measure` voert de R2-capabilitymeting uit: de IND-bronpagina wordt volledig
gelezen en Wikidata blijft standaard begrensd tot 200 records. Het commando schrijft een
machineleesbaar en een leesbaar capabilityrapport, ook wanneer een bron met `BLOCKED` of
`FAILED` eindigt. Het meetcommando ververst altijd live en kan oud bronbewijs daardoor
niet als een actuele meting labelen. De meting is geen productieharvest en de
Wikidata-steekproef is geen populatieschatting.

`sources gleif` is een expliciete bulkactie en wordt niet door `sources collect` of `run
execute` gestart. Zonder `--archive` downloadt het commando de officiële huidige Golden
Copy; gebruik `--limit N` voor een capabilitysample van maximaal N Nederlandse records.
Een reeds gecontroleerde lokale ZIP kan zonder nieuw netwerkrequest worden gebruikt:

```bash
company-harvest sources gleif --run-dir "$RUN_DIR" --archive gleif-golden-copy.zip --limit 200
```

Laat `--limit` alleen weg voor een bewust gekozen volledige inname. Controleer vooraf
vrije schijfruimte: de evidence-ZIP wordt volledig in de run gekopieerd. `--refresh`
forceert nieuwe evidence en verwerking; zonder deze optie wordt exact dezelfde input en
limiet hergebruikt. Bekijk na afloop altijd `gleif_ingest_report`, `gleif_rejected` en het
outcome-rapport. GLEIF-status en -rechtsvorm zijn brondata, geen KVK-verificatie.

`report` schrijft een leesbaar runrapport en een `outcome_report.json`. Dat machineleesbare rapport bevat per-broncijfers, identifierdekking, deduplicatie/conflicten, reviewvolume, kandidaatdiversiteit en gemeten overlap, count-closure per beschikbare procesovergang, doorlooptijd, piekgeheugen en lokale opslaggroei. `PARTIAL_CLOSED` betekent dat alle uitgevoerde overgangen sluiten maar latere stappen nog niet zijn uitgevoerd; alleen `COMPLETE_CLOSED` bestrijkt de hele pipeline. Nieuwe runs en rapporten vermelden ook de uitgaande User-Agent `company-lookup/0.1`.
