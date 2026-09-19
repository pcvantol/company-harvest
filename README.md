# Company Lookup

Company Lookup is een lokale, auditbare Python-CLI voor twee workflows:

1. **HARVEST** — publieke bronnen verzamelen, voorzichtig dedupliceren, via de gewone publieke KVK-zoekfunctie verifiëren, rechtsvorm/status filteren en Excel/TSV exporteren.
2. **MERGE_LISTS** — twee bestaande CSV/XLSX-lijsten offline samenvoegen op een geldig KVK-nummer, met volledige conflictregistratie.

De tool voert bij installatie of starten nooit automatisch een harvest uit. Echte runtimegegevens blijven onder de gekozen datamap en vallen buiten Git. De publieke KVK-provider gebruikt geen betaalde API en omzeilt geen blokkades, CAPTCHA's of rate limits.

De actuele publieke release is nog de vroegere 3.0.0-wheel onder de naam
`company-harvest`; de broncode is de nog niet gepubliceerde, incompatibele
**4.0.0**-versie onder `company-lookup`. Beide vereisen uitsluitend Python 3.14.x. De publieke
3.0.0-wheel heeft een [bekende live parserblokkade](docs/measurements/20260919-v3-live-wheel-e2e-10-blocked.md)
vóór de KVK-check. De lokaal gebouwde 3.0.1-wheel corrigeert die parser en
is met [een begrensde tiennummerproef](docs/measurements/20260919-v301-local-wheel-e2e-10-pass.md)
end-to-end gevalideerd; hij is niet gepubliceerd. De ingetrokken v1.0.0-wheel
had een breder historisch compatibiliteitscontract.

De ongepubliceerde 4.0.0-broncode bevat ook `run pre-kvk`: één opdracht van
brondownload tot de gefilterde KVK-invoer, zonder KVK-verzoeken. De 3.0.1-
parserfix is daarin opgenomen. Zie de [gebruikershandleiding](docs/functional/user-guide.md).
De pakketnaam, Python-import, CLI, configuratievariabele en standaarddatamap
zijn gewijzigd; zie [migratie](docs/technical/versioning-and-migrations.md).

Nieuwe runs en bestanden vanaf 2.0.0 krijgen
een leesbare UTC-prefix, bijvoorbeeld `2026.09.19_103917_ab12cd34ef56`.
Bestaande runmappen worden niet hernoemd; de historische 1.0.0-wheel had
zijn oorspronkelijke naamformaat.

De actuele voorbereidingsopdracht verwerkt IND, GLEIF, ANBI, DUO en TenderNed tot één
volledige gededupliceerde master en een afzonderlijk gefilterde KVK-wachtrij
met een herleidbare uitsluitingsledger; Wikidata valt buiten deze workflow. Bestaande vierbronnenruns blijven hervatbaar met hun oorspronkelijke scope. De
publieke KVK-frontend-Web-API kan via een expliciete kleine batch of een
hervatbare langlopende opdracht worden geraadpleegd. Die opdracht doet niets
automatisch bij installatie of starten. Een gesloten kandidatenlijst is nog
geen bewijs voor 10.000 actieve, geverifieerde bedrijven.

Vanaf versie 3.0.0 behoudt `run e2e` een route voor een
expliciete verwerking van downloads tot geaudite eindlijst. Met
`--limit-kvk-check 50` wordt vóór de eerste KVK-aanroep een vaste cohort
gebonden: ook na hervatten maximaal 50 KVK-kandidaten en maximaal 50
eindrecords. Als er kandidaten buiten de gekozen cohort overblijven, is de
proeflevering `PARTIAL` ten opzichte van de volledige bronlijst. Een tweede
exportlimiet bestaat niet: alle actieve bedrijven uit
de gekozen KVK-cohort worden geleverd. Zie de [E2E-gebruikshandleiding](docs/functional/e2e-command.md).
De outputset bevat daarnaast `companies_delivery_light.xlsx`: zakelijke
KVK-zoekvelden plus als bronvelden gemarkeerde website en sector, zonder de
technische JSON-kolommen van de volledige auditexport.
Zie [alle eindbestanden en hun veldherkomst](docs/functional/output-files.md).

De 2.0.0-CLI toont bij ieder commando gekleurde,
recordvrije voortgang op stderr; de bestaande stdout-uitvoer blijft geschikt
voor scripts. Zie [consolevoortgang](docs/functional/console-logging.md).

## Vanuit een broncheckout ontwikkelen

Gebruik voor installatie van de publieke wheel zonder checkout de
[E2E-handleiding](docs/functional/e2e-command.md). Het volgende voorbeeld
is alleen voor lokale ontwikkeling vanuit deze repository:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
export COMPANY_LOOKUP_DATA_DIR="$HOME/Documents/company-lookup-data"
.venv/bin/company-lookup doctor
RUN_DIR="$(.venv/bin/company-lookup run init --target 10000 --print-path)"
```

Zie de [geïntegreerde gebruikshandleiding](docs/functional/e2e-command.md),
[het outputbestandcontract](docs/functional/output-files.md),
[de gearchiveerde 1.0.0-snelstart](docs/functional/snelstart-v1.0.0.md),
[de uitgebreide gebruikershandleiding](docs/functional/user-guide.md),
[technische documentatie](docs/README.md) en
[releaseverificatie](docs/technical/release-and-download-verification.md).

De canonieke prioriteiten, parkeerbesluiten en uitvoeringsincrements staan in de [roadmap](ROADMAP.md).

De [publieke release v3.0.0](https://github.com/pcvantol/company-harvest/releases/tag/v3.0.0)
bevat de [direct downloadbare wheel](https://github.com/pcvantol/company-harvest/releases/download/v3.0.0/company_harvest-3.0.0-py3-none-any.whl)
en checksums; zie ook het [publicatiebewijs](docs/releases/20260919-v3.0.0-evidence.md).
Zie de [releasenotities voor 3.0.0](docs/releases/v3.0.0.md) voor de publieke
compatibiliteit en grenzen. Alle GitHub Releases en lokale/remote tags onder
3.0, inclusief `v2.0.0`, zijn op verzoek ingetrokken. De historische
[releasenotities](docs/releases/README.md) en publicatiebewijzen blijven als
archief; de oude downloadlinks werken niet meer.

## Status van externe toegang

Bron- en KVK-livecapabilities worden per run gemeten. Een succesvolle offline test is geen bewijs dat een externe route live beschikbaar is. Grootschalig gebruik van Handelsregistergegevens kent aanvullende voorwaarden; beoordeel die vóór een productierun.
