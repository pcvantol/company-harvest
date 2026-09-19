# Company Harvest

Company Harvest is een lokale, auditbare Python-CLI voor twee workflows:

1. **HARVEST** — publieke bronnen verzamelen, voorzichtig dedupliceren, via de gewone publieke KVK-zoekfunctie verifiëren, rechtsvorm/status filteren en Excel/TSV exporteren.
2. **MERGE_LISTS** — twee bestaande CSV/XLSX-lijsten offline samenvoegen op een geldig KVK-nummer, met volledige conflictregistratie.

De tool voert bij installatie of starten nooit automatisch een harvest uit. Echte runtimegegevens blijven onder de gekozen datamap en vallen buiten Git. De publieke KVK-provider gebruikt geen betaalde API en omzeilt geen blokkades, CAPTCHA's of rate limits.

Versie 2.0.0 vereist uitsluitend Python 3.14.x. De oudere v1.0.0-wheel
behoudt haar eigen historische compatibiliteitscontract.

Nieuwe runs en bestanden vanaf 2.0.0 krijgen
een leesbare UTC-prefix, bijvoorbeeld `2026.09.19_103917_ab12cd34ef56`.
Bestaande runmappen worden niet hernoemd; de gepubliceerde 1.0.0-wheel houdt
zijn oorspronkelijke naamformaat.

De actuele voorbereidingsopdracht verwerkt IND, GLEIF, ANBI en DUO tot één
volledige gededupliceerde master en een afzonderlijk gefilterde KVK-wachtrij
met een herleidbare uitsluitingsledger; Wikidata valt buiten deze workflow. De
publieke KVK-frontend-Web-API kan via een expliciete kleine batch of een
hervatbare langlopende opdracht worden geraadpleegd. Die opdracht doet niets
automatisch bij installatie of starten. Een gesloten kandidatenlijst is nog
geen bewijs voor 10.000 actieve, geverifieerde bedrijven.

Versie 2.0.0 bevat `run e2e` voor een
expliciete verwerking van downloads tot geaudite eindlijst. Met
`--limit-kvk-check 50` wordt vóór de eerste KVK-aanroep een vaste cohort
gebonden: ook na hervatten maximaal 50 KVK-kandidaten en maximaal 50
eindrecords. Deze proeflevering is PARTIAL ten opzichte van de volledige
bronlijst. Zie de [E2E-gebruikshandleiding](docs/functional/e2e-command.md).

De 2.0.0-CLI toont bij ieder commando gekleurde,
recordvrije voortgang op stderr; de bestaande stdout-uitvoer blijft geschikt
voor scripts. Zie [consolevoortgang](docs/functional/console-logging.md).

## Snel starten

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
export COMPANY_HARVEST_DATA_DIR="$PWD"
.venv/bin/company-harvest doctor
RUN_DIR="$(.venv/bin/company-harvest run init --target 10000 --print-path)"
```

Zie de [geïntegreerde 2.0.0-gebruikshandleiding](docs/functional/e2e-command.md),
[de historische 1.0.0-snelstart](docs/functional/snelstart-v1.0.0.md),
[de uitgebreide gebruikershandleiding](docs/functional/user-guide.md),
[technische documentatie](docs/README.md) en
[releaseverificatie](docs/technical/release-and-download-verification.md).

De canonieke prioriteiten, parkeerbesluiten en uitvoeringsincrements staan in de [roadmap](ROADMAP.md).

De [publieke release v2.0.0](https://github.com/pcvantol/company-harvest/releases/tag/v2.0.0)
bevat de [direct downloadbare wheel](https://github.com/pcvantol/company-harvest/releases/download/v2.0.0/company_harvest-2.0.0-py3-none-any.whl),
checksums en het [publicatiebewijs](docs/releases/20260919-v2.0.0-evidence.md).
Zie de [releasenotities voor 2.0.0](docs/releases/v2.0.0.md) voor de actuele
compatibiliteit en grenzen. De oudere [publieke release v1.0.0](https://github.com/pcvantol/company-harvest/releases/tag/v1.0.0)
bevat haar eigen gekwalificeerde wheel en checksums; zie ook de [historische releasenotities](docs/releases/v1.0.0.md)
en het [publicatiebewijs](docs/releases/20260919-v1.0.0-evidence.md). Het historische
release-object `v0.1.0` en zijn assets zijn verwijderd; de historische Git-tag
`v0.1.0` is op 19 september 2026 eveneens lokaal en op `origin` verwijderd.

## Status van externe toegang

Bron- en KVK-livecapabilities worden per run gemeten. Een succesvolle offline test is geen bewijs dat een externe route live beschikbaar is. Grootschalig gebruik van Handelsregistergegevens kent aanvullende voorwaarden; beoordeel die vóór een productierun.
