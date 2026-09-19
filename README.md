# Company Harvest

Company Harvest is een lokale, auditbare Python-CLI voor twee workflows:

1. **HARVEST** — publieke bronnen verzamelen, voorzichtig dedupliceren, via de gewone publieke KVK-zoekfunctie verifiëren, rechtsvorm/status filteren en Excel/TSV exporteren.
2. **MERGE_LISTS** — twee bestaande CSV/XLSX-lijsten offline samenvoegen op een geldig KVK-nummer, met volledige conflictregistratie.

De tool voert bij installatie of starten nooit automatisch een harvest uit. Echte runtimegegevens blijven onder de gekozen datamap en vallen buiten Git. De publieke KVK-provider gebruikt geen betaalde API en omzeilt geen blokkades, CAPTCHA's of rate limits.

De actuele voorbereidingsopdracht verwerkt IND, GLEIF, ANBI en DUO tot één
volledige gededupliceerde master en een afzonderlijk gefilterde KVK-wachtrij
met een herleidbare uitsluitingsledger; Wikidata valt buiten deze workflow. De
publieke KVK-frontend-Web-API kan via een expliciete kleine batch of een
hervatbare langlopende opdracht worden geraadpleegd. Die opdracht doet niets
automatisch bij installatie of starten. Een gesloten kandidatenlijst is nog
geen bewijs voor 10.000 actieve, geverifieerde bedrijven.

## Snel starten

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
export COMPANY_HARVEST_DATA_DIR="$PWD"
.venv/bin/company-harvest doctor
RUN_DIR="$(.venv/bin/company-harvest run init --target 10000 --print-path)"
```

Zie de [korte functionele snelstart](docs/functional/snelstart-v1.0.0.md),
[de uitgebreide gebruikershandleiding](docs/functional/user-guide.md),
[technische documentatie](docs/README.md) en
[releaseverificatie](docs/technical/release-and-download-verification.md).

De canonieke prioriteiten, parkeerbesluiten en uitvoeringsincrements staan in de [roadmap](ROADMAP.md).

De [publieke release v1.0.0](https://github.com/pcvantol/company-harvest/releases/tag/v1.0.0)
bevat de gekwalificeerde wheel en checksums; zie ook de [lokale releasenotities](docs/releases/v1.0.0.md)
en het [publicatiebewijs](docs/releases/20260919-v1.0.0-evidence.md). Het historische
release-object `v0.1.0` en zijn assets zijn verwijderd; de tag bleef behouden.

## Status van externe toegang

Bron- en KVK-livecapabilities worden per run gemeten. Een succesvolle offline test is geen bewijs dat een externe route live beschikbaar is. Grootschalig gebruik van Handelsregistergegevens kent aanvullende voorwaarden; beoordeel die vóór een productierun.
