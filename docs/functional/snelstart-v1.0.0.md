# Snelstart: van bronnen tot levering (v1.0.0)

> Archief, niet meer uitvoerbaar vanaf een schone pc: de v1.0.0-release,
> assets en tag zijn verwijderd. Het onderstaande downloadcommando werkt
> niet meer. Gebruik de [actuele v2.0.0-E2E-handleiding](e2e-command.md).

**Voor wie:** iemand die de gepubliceerde tool op macOS met Python 3.14 wil
gebruiken, zonder checkout of GitHub-login. Voer de opdrachten in volgorde uit in
Terminal. De tool verwerkt IND, GLEIF, ANBI en DUO; **Wikidata blijft buiten
deze workflow**. Bronbestanden en bedrijfsgegevens blijven in uw eigen datamap.
Een doel van 10.000 is een bovengrens, geen opbrengstgarantie.

## 1. Eenmalig installeren

```sh
TOOL_DIR="$HOME/company-harvest-tool"
DATA_DIR="$HOME/Documents/company-harvest-data"
mkdir -p "$TOOL_DIR" "$DATA_DIR"
cd "$TOOL_DIR"
export COMPANY_HARVEST_DATA_DIR="$DATA_DIR"
curl -fL -o company_harvest-1.0.0-py3-none-any.whl 'https://github.com/pcvantol/company-harvest/releases/download/v1.0.0/company_harvest-1.0.0-py3-none-any.whl'
printf '%s  %s\n' 'c8847f5cd0f6b03f0829b93f8ecaf3a569c1bcc1392250f0713b03538ac8552c' 'company_harvest-1.0.0-py3-none-any.whl' | shasum -a 256 -c - || exit 1
python3.14 -m venv .venv
.venv/bin/python -m pip install ./company_harvest-1.0.0-py3-none-any.whl
CH="$TOOL_DIR/.venv/bin/company-harvest"
"$CH" --version
"$CH" doctor
```

De checksumcontrole stopt de Terminal-sessie bij een afwijkende download.
`--version` moet `1.0.0` tonen en `doctor` moet
`ready=true` melden. Zorg vooraf voor voldoende opslag voor de volledige
bronarchieven.

## 2. Bronnen voorbereiden en controleren

```sh
RUN_DIR="$("$CH" run init --target 10000 --print-path)"
printf '%s\n' "$RUN_DIR"
"$CH" run preflight --run-dir "$RUN_DIR"
"$CH" run prepare-pre-kvk --run-dir "$RUN_DIR"
"$CH" audit verify --run-dir "$RUN_DIR"
"$CH" kvk preflight --run-dir "$RUN_DIR" --provider public-http
```

**Bewaar het geprinte absolute `RUN_DIR`-pad.** `prepare-pre-kvk` downloadt de
vier bronnen, voegt ze voorzichtig samen en dedupliceert ze. In
`$RUN_DIR/artifacts/` staan de volledige `*_03_pre_kvk_master.tsv`, de voor KVK
toegelaten `*_03_pre_kvk_eligible.tsv`, de uitgesloten
`*_03_pre_kvk_excluded.tsv` en `*_03_pre_kvk_filter_metadata.json` met
filterregels, aantallen en hashes. Een ontbrekende KVK-hint is geen bewijs dat
een organisatie niet geregistreerd is. `audit verify` moet `valid=true`
melden. De KVK-preflight controleert alleen lokale configuratie; hij test de
live bereikbaarheid niet.

## 3. Publieke KVK-controle, rustig en hervatbaar

```sh
"$CH" kvk pre-kvk-run --run-dir "$RUN_DIR" --max-requests 100 --interval 2
python3.14 -m json.tool "$RUN_DIR/pre_kvk_kvk_progress.json"
```

Herhaal dezelfde `pre-kvk-run`-opdracht met **dezelfde runmap** voor volgende
groepen van maximaal 100. Per verzoekstart geldt minimaal twee seconden
afstand; de hele lijst kan dus dagen duren. Na een nieuwe Terminal-sessie:

```sh
CH="$HOME/company-harvest-tool/.venv/bin/company-harvest"
RUN_DIR="<eerder geprint absoluut runpad>"
"$CH" kvk pre-kvk-run --run-dir "$RUN_DIR" --max-requests 100 --interval 2
```

`state.sqlite3` bewaart de aanvraaggeschiedenis;
`pre_kvk_kvk_progress.json`, `pre_kvk_kvk_matches.tsv` en
`pre_kvk_kvk_unresolved.tsv` tonen de voortgang. Ga pas verder bij
`status=COMPLETE`, `remaining=0` en geen actieve blokkade. `COMPLETE` betekent
dat alle kandidaten een uitkomst hebben, niet dat ze allemaal een KVK-match
hebben. Een onderbroken lopend verzoek blijft onzeker en wordt niet stil
opnieuw verstuurd. Stop bij 401/403/429; omzeil die blokkade niet.

## 4. Eindlijst maken

```sh
"$CH" audit verify --run-dir "$RUN_DIR"
"$CH" kvk consolidate --run-dir "$RUN_DIR"
"$CH" companies exclude-sole-proprietorships --run-dir "$RUN_DIR"
"$CH" companies active-only --run-dir "$RUN_DIR"
```

Kies **één** exportroute. Voor een volledig gevalideerde levering:

```sh
"$CH" export --run-dir "$RUN_DIR" --limit 10000 || exit 1
"$CH" report --run-dir "$RUN_DIR"
"$CH" audit verify --run-dir "$RUN_DIR"
open "$RUN_DIR/artifacts"
```

**Strikte export stopt bij onopgeloste KVK-uitkomsten.** Als u bewust een
onvolledige levering accepteert, gebruik dan **in plaats van het gehele
strikte exportblok** alleen dit blok:

```sh
"$CH" export --run-dir "$RUN_DIR" --limit 10000 --allow-partial || exit 1
"$CH" report --run-dir "$RUN_DIR"
open "$RUN_DIR/artifacts"
```

`|| exit 1` stopt het blok bij exportfout. `*_08_delivery_outputset/` bevat
`companies_delivery.csv` en `.xlsx` (naam + KVK),
`companies_delivery_full.csv` en `.xlsx` (meer velden),
`companies_reserve.csv` en `outputset_manifest.json`. `*_08_run_report.md`
is het leesbare rapport. Een partiële levering is niet volledig gevalideerd:
de v1.0.0-eindaudit meldt daarvoor ten onrechte
`MISSING_REQUIRED:outputset_manifest`. Claim dus geen audit-PASS.

De volledige live KVK-doorloop en de opbrengst van 10.000 actieve,
geverifieerde bedrijven zijn voor v1.0.0 **niet bewezen**. Meer details en
alle bestandsnamen: [volledige commandotabel](v1-end-to-end-commands.md).
