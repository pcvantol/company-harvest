# Eén commando van bronnen tot eindlijst (broncode 1.1.1)

`run e2e` verbindt de bestaande stappen 1–8: hostcheck, volledige downloads
van IND/GLEIF/ANBI/DUO, samenvoegen/dedupliceren, pre-KVK-filter, publieke
KVK-frontendcheck, canonisering, eenmanszaak-/statusfilters, export, rapport en
audit. Er wordt geen Wikidata gelezen en geen officiële API-key gebruikt.
Installeer eerst de **1.1.1-wheel zodra die is uitgebracht** in een venv op
Python 3.14.x; andere Python-minorversies worden geweigerd. De huidige
v1.0.0-wheel bevat dit commando niet. Een checkout,
GitHub-login of Codex is tijdens gebruik niet nodig.

Voor een bewust begrensde proef op een nieuwe datamap:

```bash
export COMPANY_HARVEST_DATA_DIR="$HOME/Documents/company-lookup-data"
company-harvest run e2e --limit-kvk-check 50 --interval 2 --export-limit 50
```

De tool drukt de absolute `run_dir` meteen vóór de lange broninname af.
Bewaar die map. Bij onderbreking of een herstelbare bronfout: herhaal met
**dezelfde** map en dezelfde KVK-/exportlimiet en interval:

```bash
company-harvest run e2e --run-dir "/absoluut/pad/naar/de/run" \
  --limit-kvk-check 50 --interval 2 --export-limit 50
```

`--limit-kvk-check 50` is een harde **runbrede** grens, niet een batchgrootte.
Vóór de eerste GET wordt de eerste stabiele cohort van hoogstens 50 toegelaten
kandidaten met bron- en filterhash vastgelegd. Ook na herstart kan deze run
geen 51e kandidaat bevragen of de cohort wijzigen. De overige kandidaten
blijven in de volledige gefilterde lijst en staan als `not_checked_rows` in
`*_03_kvk_scope_metadata.json`; zij zijn niet als inhoudelijk irrelevant
uitgesloten. Deduplicatie en filters kunnen de levering kleiner maken dan 50,
zelfs leeg. Wanneer de volledige lijst meer dan 50 kandidaten telt, is de
export `PARTIAL_EXPORTED` en mag die niet als volledige harvest worden
gepresenteerd, ook als alle 50 gekozen kandidaten slagen. Is de volledige
lijst hoogstens 50 en is iedere match gesloten, dan kan de export wel compleet
zijn.

Na succes staan de bestanden in
`$RUN_DIR/artifacts/*_08_delivery_outputset/`: `companies_delivery.csv`/`.xlsx`
(naam en KVK), `companies_delivery_full.csv`/`.xlsx` (extra velden),
`companies_reserve.csv` en `outputset_manifest.json`. Het manifest bevat
bestandschecksums, `status` en de KVK-cohortaantallen. `audit verify` is
onderdeel van het commando en controleert ook PARTIAL-manifests met alle vijf
bijbehorende bestanden. `pre_kvk_kvk_progress.json` en het SQLite-journal
tonen onderweg verzoeken, matches en resterende **cohort**kandidaten.

Een HTTP-blokkade of rate limit stopt vóór export; een nieuwe run in dezelfde
datamap wordt niet automatisch als uitweg gebruikt. Bekijk de lokale evidence
en beoordeel de toegang afzonderlijk. De interval is minstens twee seconden
tussen verzoekstarts, geen garantie op bereikbaarheid of toestemming. De
journalcontrole bestrijkt alleen dezelfde datamap; een andere datamap mag niet
als omweg voor een bekende toegangsblokkade worden gebruikt.

Een volledige, onbegrensde KVK-doorloop vereist bewust `--all-kvk` in plaats
van `--limit-kvk-check`. Als binnen de gekozen cohort onopgeloste kandidaten
overblijven, weigert de export óók bij een begrensde proef. `--allow-partial`
is dan een aparte expliciete keuze, ook bij hervatten; de output krijgt een
PARTIAL-status. De onafhankelijke
stap 9 (`companies merge-lists`) blijft een apart commando omdat het toevoegen
van een externe lijst anders de harde 50-recordgrens van deze eindlijst zou
doorbreken.
