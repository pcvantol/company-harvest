# Eén commando van bronnen tot eindlijst (release 3.0.0)

> **Actuele beperking (live meting 19 september 2026):** de ongewijzigde
> v3.0.0-wheel haalde alle vijf bronnen binnen, maar stopte op één te lang
> CSV-veld bij de pre-KVK-filter. Er waren nul KVK-verzoeken en er ontstond
> geen eind-Excel. Zie het [meetverslag](../measurements/20260919-v3-live-wheel-e2e-10-blocked.md).
> De nog niet gepubliceerde bronversie 3.0.1 bevat een begrensde parserfix;
> de onderstaande installatiecommando's voor de publieke 3.0.0-wheel
> bevatten die fix **niet**. Een volledige live E2E-slaagkans is nog niet bewezen.

`run e2e` verbindt de bestaande stappen 1–8: hostcheck, volledige downloads
van IND/GLEIF/ANBI/DUO/TenderNed, samenvoegen/dedupliceren, pre-KVK-filter, publieke
KVK-frontendcheck, canonisering, eenmanszaak-/statusfilters, export, rapport en
audit. Er wordt geen Wikidata gelezen en geen officiële API-key gebruikt.
De **publieke 3.0.0-wheel** bevat dit proces en werkt zonder broncheckout,
GitHub-login of Codex. De inmiddels ingetrokken 2.0.0-wheel verwerkte nog
vier bronnen en maakte geen `companies_delivery_light.xlsx`. Alleen Python 3.14.x wordt
ondersteund. Controleer vóór installatie de wheelhash tegen de
`SHA256SUMS.txt` van [release v3.0.0](https://github.com/pcvantol/company-harvest/releases/tag/v3.0.0).

Installeer de gedownloade wheel in een nieuwe virtuele omgeving:

```bash
# macOS
python3.14 -m venv .venv
.venv/bin/python -m pip install ./company_harvest-3.0.0-py3-none-any.whl
.venv/bin/company-harvest --version
source .venv/bin/activate
```

```powershell
# Windows PowerShell
py -3.14 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install .\company_harvest-3.0.0-py3-none-any.whl
& .\.venv\Scripts\company-harvest.exe --version
```

Beide versiecontroles moeten `3.0.0` melden. Op macOS is de venv hierboven
geactiveerd; gebruik hieronder dat `company-harvest`-commando. Op Windows
blijft het volledige venv-pad staan. Afhankelijkheden worden bij installatie
online opgehaald; er is geen lokale broncheckout nodig.

Voor een bewust begrensde proef op een nieuwe datamap:

```bash
export COMPANY_HARVEST_DATA_DIR="$HOME/Documents/company-lookup-data"
company-harvest run e2e --limit-kvk-check 50 --interval 2
```

In Windows PowerShell is de overeenkomstige expliciete start bijvoorbeeld:

```powershell
$env:COMPANY_HARVEST_DATA_DIR = "$HOME\Documents\company-lookup-data"
& .\.venv\Scripts\company-harvest.exe run e2e --limit-kvk-check 10 --interval 2
```

De tool drukt de absolute `run_dir` meteen vóór de lange broninname af.
Bewaar die map. Bij onderbreking of een herstelbare bronfout: herhaal met
**dezelfde** map en dezelfde KVK-limiet en interval:

```bash
company-harvest run e2e --run-dir "/absoluut/pad/naar/de/run" \
  --limit-kvk-check 50 --interval 2
```

Windows PowerShell (als de eerste start limiet 10 gebruikte):

```powershell
& .\.venv\Scripts\company-harvest.exe run e2e --run-dir 'C:\pad\naar\de\run' --limit-kvk-check 10 --interval 2
```

`--run-dir` moet de **exacte runmap** zijn die de eerste start op stdout
afdrukte, niet alleen de bovenliggende datamap. Zonder deze optie begint een
nieuwe run. Hervatten vereist dezelfde `--limit-kvk-check 50` (of dezelfde
keuze `--all-kvk`) en dezelfde `--interval 2`; de gekozen KVK-cohort kan in
dezelfde run niet worden vergroot. Een afgeronde proef van 50 wordt dus niet
door herhaling de volgende batch van 50. Voor een groter bereik is een
afzonderlijk, bewust runbesluit nodig; gebruik een nieuwe run nooit als
uitweg voor een toegangs- of rateblokkade.

Bij hervatten **doorloopt de tool de fasen als controles**. Voltooide,
geregistreerde bronbestanden met passende instellingen en intact bewijs
worden hergebruikt, zonder tweede download. Dezelfde pre-KVK-master en
filteruitvoer worden eveneens hergebruikt zolang hun bronbindingen kloppen.
Een bronstap die vóór voltooiing is afgebroken heeft geen gegarandeerde
byte-voor-byte-downloadhervatting en kan opnieuw moeten downloaden. Als
een eerder bewijsbestand of instelling afwijkt, kan de collector opnieuw
downloaden of de integriteitsgate de run stoppen; dit is geen stil hergebruik.

De KVK-fase leest het duurzame SQLite-journal (`state.sqlite3`) en bevraagt
reeds geregistreerde kandidaten niet opnieuw. Een op het moment van een
crash lopend verzoek wordt als `SENT_OUTCOME_UNKNOWN` vastgelegd, niet
automatisch opnieuw verstuurd. Het blijft in de unresolved-lijst; voor een
export met zulke uitkomsten is bij de hervatte opdracht expliciet
`--allow-partial` nodig. Controleer de voortgang in
`pre_kvk_kvk_progress.json`. Een al geëxporteerde run controleert alleen
rapport en audit en start geen bron- of KVK-verzoeken meer.

De CLI toont daarnaast op stderr per fase een
gekleurde, recordvrije voortgangsregel en tijdens de KVK-check alleen
checkpointaantallen. stdout blijft de bestaande machineleesbare uitvoer;
zie [consolevoortgang](console-logging.md).

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

Er bestaat geen afzonderlijke `--export-limit` meer: na de KVK-check komen
**alle** actieve, geverifieerde bedrijven uit de gekozen cohort in de
eindlijst, alfabetisch gepresenteerd. Er wordt geen willekeurige hashselectie
of tweede afkap toegepast. Het verplichte `companies_reserve.csv` uit het
bestaande outputsetschema blijft leeg voor compatibiliteit en audit.

Na succes staan de bestanden in
`$RUN_DIR/artifacts/*_08_delivery_outputset/`: `companies_delivery.csv`/`.xlsx`
(naam en KVK), `companies_delivery_light.csv`/`.xlsx` (zakelijke KVK-velden,
plus duidelijk gemarkeerde website en sector uit de bron),
`companies_delivery_full.csv`/`.xlsx` (inclusief technisch bewijs),
`companies_reserve.csv` en `outputset_manifest.json`. De lichte export heeft
geen `response_json`, `source_relations`, kandidaat-ID, provider of tijdstempel.
Naast naam, nummer, rechtsvorm, status, plaats en land bevat hij aanwezige
zakelijke velden uit de publieke KVK-zoekhit, zoals inschrijfdatum,
handelsnamen, activiteit, vestiging en adres. Meerdere publieke waarden in
één veld staan als leesbare tekst gescheiden door `; `; ontbrekende velden
blijven leeg. Website en sector zijn **brondata, niet door KVK bevestigd**.
Nieuwe, nog niet beoordeelde responsvelden met inhoud blokkeren de lichte export in
plaats van mogelijk technische metadata te publiceren.
Bij geregistreerde broncontext gebruikt de join uitsluitend kandidaat-ID
plus hetzelfde achtcijferige KVK-nummer; zonder broncontext blijven de
bronkolommen leeg. Er wordt geen naamkoppeling gebruikt. Het manifest bevat
bestandschecksums, `status` en de KVK-cohortaantallen. `audit verify` is
onderdeel van het commando en controleert ook PARTIAL-manifests met alle zeven
bijbehorende bestanden; historische schema-1-outputsets met vijf bestanden
blijven auditbaar. `pre_kvk_kvk_progress.json` en het SQLite-journal
tonen onderweg verzoeken, matches en resterende **cohort**kandidaten.
De volledige uitvoerlijst bevat `candidate_id`. Via die sleutel kan het
reviewlabel uit de lokale `artifacts/*_03_pre_kvk_review_labels.tsv` worden
teruggevonden; holdings worden op naam alleen niet vooraf uitgesloten.
De KVK-check verstuurt alleen het achtcijferige bron-KVK-nummer, nooit een
bedrijfsnaam als zoekterm. Bedrijven zonder geldige bronhint blijven wel in de
master, maar gaan niet naar deze KVK-check.

Zie [eindbestanden en veldherkomst](output-files.md) voor de exacte rollen
van de drie Excel-varianten, de veldherkomst en de betekenis van lege cellen.

De automatische CI-proef gebruikt hetzelfde `run e2e`-commando vanaf een lege
run met synthetische brondata en gemockte KVK-zoekresultaten. Zij controleert
de eindlijst en audit zonder live aanvragen; een geslaagde CI-proef bewijst
geen actuele bereikbaarheid van publieke bronnen of KVK.

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
