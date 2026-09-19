# Gebruikershandleiding

Deze handleiding beschrijft de **publieke 3.0.0-wheel** op Python 3.14.x.
De oudere 2.0.0-wheel bevat noch TenderNed noch de lichte eind-Excel.
Gebruik voor de geïntegreerde opdracht
[de actuele E2E-handleiding](e2e-command.md) en voor de drie Excel-varianten
[eindbestanden en veldherkomst](output-files.md). Een broncheckout is voor
gebruik van de 3.0.0-wheel niet nodig.

De [korte historische snelstart](snelstart-v1.0.0.md) beschrijft de vroegere
installatie, volledige workflow en hervatten, maar de downloadstap werkt niet
meer.

De [v1.0.0-commandotabel](v1-end-to-end-commands.md) is alleen historisch:
de ingetrokken release en haar opties zijn geen actuele installatieroute.

Installeer in een eigen virtual environment en kies `COMPANY_HARVEST_DATA_DIR`.
`run init --print-path` maakt uitsluitend een lokale run; `--target 10000`
is een doelgetal, geen exportlimiet of garantie op 10.000 bedrijven. Nieuwe
bronvoorbereiding gebruikt IND, GLEIF, ANBI, DUO en TenderNed. Wikidata
wordt niet gedownload of aan de master toegevoegd. Bestaande gebonden
vierbronnenruns behouden hun scope.

Gebruik voor ontwikkeling bijvoorbeeld:

```bash
export COMPANY_HARVEST_DATA_DIR="$HOME/Documents/company-lookup-data"
RUN_DIR="$(company-harvest run init --target 10000 --print-path)"
company-harvest run prepare-pre-kvk --run-dir "$RUN_DIR"
company-harvest kvk pre-kvk-batch --run-dir "$RUN_DIR" --limit 10
```

`prepare-pre-kvk` downloadt voor een nieuwe run vijf volledige bronnen sequentieel (IND, GLEIF, ANBI, DUO, TenderNed), hergebruikt eerder voltooide bronartefacten, bouwt een conservatief gededupliceerde master en filtert die vóór KVK. Oude vierbronnenruns blijven op hun gebonden scope. Gebruik `--refresh` alleen voor een bewust nieuwe bronmomentopname. Controleer bronrapporten, rejected-rijen, conflicten, het masterrapport en `pre_kvk_filter_metadata`. `kvk pre-kvk-batch` blijft een expliciete kleine batch via de waargenomen publieke frontend-Web-API: maximaal tien nieuwe kandidaten, alleen partiële batchartefacten. Herhaal geen geblokkeerde requests.

De eigenaar heeft daarnaast de langlopende frontendcontrole expliciet
geactiveerd. Kies bij `kvk pre-kvk-run` altijd bewust een begrensde sessie of
de hele resterende lijst:

```bash
RUN_DIR="/absoluut/pad/naar/de/bestaande/run"
company-harvest kvk pre-kvk-run --run-dir "$RUN_DIR" --max-requests 10 --interval 2
company-harvest kvk pre-kvk-run --run-dir "$RUN_DIR" --until-complete --interval 2
```

Na een pauze of herstart kunt u het tweede commando identiek herhalen. Ctrl+C
stopt een foregroundproces; een eventueel lopende aanroep krijgt de status
`SENT_OUTCOME_UNKNOWN` en wordt niet stil opnieuw verzonden.
`pre_kvk_kvk_progress.json` toont de journalstatussen en het resterende
aantal. `pre_kvk_kvk_matches.tsv` en `pre_kvk_kvk_unresolved.tsv` zijn
lokale tussentijdse outputs; zij worden pas na gesloten kandidaatpartitie
zonder actieve blokkade als COMPLETE-artefacten geregistreerd. Een onzekere
uitkomst blijft unresolved en telt niet als geverifieerde match. Een HTTP
401/403/429 stopt verder verkeer;
gebruik geen browserwissel of nieuwe run om dit te omzeilen. Voor de
historische vierbronnenlijst van 119.801 kandidaten kost alleen de minimale
pacing al ruim 66 uur; een nieuwe vijfbronnenlijst kan een ander aantal
hebben en responstijd komt
daarbovenop. Dit is geen officiële API-key-route. De volledige doorloop is
niet automatisch gestart en voorwaarden, velddekking en productkwaliteit
blijven afzonderlijk te beoordelen.

`run execute` voert dezelfde gebonden bronvoorbereiding uit; alleen met een expliciete `--limit` van 1–10 volgt één KVK-batch. Er wordt geen volledige KVK-harvest of downstream-export automatisch gestart. `sources collect` zonder selectie leest alleen IND; Wikidata vereist een expliciet legacy `--only-source` en maakt geen deel uit van deze workflow. Merge van bestaande bestanden blijft beschikbaar via `companies merge-lists --left … --right …`.

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

`sources gleif` is een afzonderlijke bulkactie en wordt niet door `sources collect` gestart; `run prepare-pre-kvk` en `run execute` starten haar wel expliciet als onderdeel van de gebonden bronvoorbereiding. Zonder `--archive` downloadt het commando de officiële huidige Golden
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

`sources anbi` en `sources duo` zijn net als GLEIF afzonderlijke bulkacties en worden niet
door `sources collect` gestart; de bronvoorbereiding gebruikt ze wel. Gebruik voor een gecontroleerde lokale
snapshot bijvoorbeeld:

```bash
company-harvest sources anbi --run-dir "$RUN_DIR" --archive anbi.zip --limit 500
company-harvest sources duo --run-dir "$RUN_DIR" --archive basisgegevens-instellingen.zip --limit 500
```

ANBI-fiscale nummers zijn geen KVK-nummers en blijven alleen als ruwe bronidentifier
beschikbaar. DUO neemt alleen huidige `A`-records als kandidaat, maar verliest historische
regels niet stil: die staan in rejected. Ook huidige DUO-records zonder of met ongeldig
KVK-veld blijven kandidaat. Bekijk na afloop de twee ingest reports en rejected-bestanden.

`companies pre-kvk-list` bouwt zonder netwerk of KVK-call één brede lijst
vlak vóór verificatie, maar alleen als alle geselecteerde bronadapters
onbegrensd en met intact bronbewijs zijn afgerond. De output bevat per
regel de originele bronpayloads en bewijsrelaties; een directe KVK-hint is
niet automatisch geverifieerd. Identieke namen zonder gedeelde geldige
KVK-hint blijven apart om foutieve samenvoegingen te voorkomen. Bij een
bronblokkade verschijnt geen volledige master. De historische run van
2026-09-19 bevat een geblokkeerde preview; die blijft een historisch artefact.
Een nieuw gebouwde `pre_kvk_master` heeft vijf bronnen. Voor een bestaande
master kan `companies pre-kvk-filter --run-dir "$RUN_DIR"` de filter zonder
herdownload of KVK-verzoek afzonderlijk bouwen. Alleen `pre_kvk_eligible`
mag naar `kvk pre-kvk-batch`. `pre_kvk_excluded` bevat iedere uitgesloten
kandidaat met alle redenen; de JSON-metadata legt de criteria, aantallen
en hashes vast. De volledige master blijft behouden. Zonder directe
KVK-bronhint betekent hier uitsluiting van de huidige KVK-wachtrij, niet
dat de organisatie in werkelijkheid geen inschrijving kan hebben.

`companies sample` bouwt de R6-kwaliteitssample zonder netwerkrequests. De verdeling is
eerst gelijkmatig over actieve bronfamilies en daarna binnen iedere familie over records
met en zonder geldig direct KVK-nummer. Bij onvoldoende capaciteit wordt het restant
deterministisch herverdeeld. Binnen ieder stratum worden de laagste SHA-256-selecties van
de volledige bronrij gekozen. De opdracht schrijft de 500 bronrecords, voorlopige
kandidaten, dedupbeslissingen, conflicten, een gestratificeerde reviewqueue, een
50-record-R8-pilotselectie en JSON-/Markdownrapporten.

Vul alle regels uit `r6_review_queue.csv` in een afzonderlijk TSV-bestand aan met
`queue_sha256` (op iedere regel exact de hash uit `r6_sample_report.json`), `review_id`,
`review_verdict` (`CONFIRMED`, `FALSE_MERGE` of `UNCERTAIN`) en `review_notes`.
Registreer het daarna met:

```bash
company-harvest companies sample-review --run-dir "$RUN_DIR" --input beoordeling.tsv
```

De beoordeling sluit alleen wanneer zij exact bij de actuele queue past. Persoons- en
bedrijfsrecords, de review en de pilotselectie blijven lokale runartefacten en worden niet
in Git opgenomen.

`kvk pilot` voert de historische R8-selectie van kandidaten zonder directe
KVK-hint nog uitsluitend offline uit. Een eenduidige bronkoppeling blijft als
voorlopige match zichtbaar; voor de overige records ontstaat
`NO_DIRECT_KVK_HINT`. Er worden **geen** publieke naamverzoeken verstuurd,
ongeacht de waarde van de historische `--max-live`-optie. De journalquery is
voor deze offline no-hint-uitkomst leeg, niet een verstuurde zoekopdracht.
Voor nieuwe publieke checks geldt altijd een geldige directe bronhint als
input. Gebruik `--refresh` alleen voor een bewuste nieuwe offline meetset;
oude op naam gezochte pilotresultaten worden niet stil hergebruikt.

Vul alle regels van `r8_review_queue.csv` in een apart TSV-bestand met
`queue_sha256`, `review_id`, `review_verdict` (`CONFIRMED`, `FALSE_MATCH` of
`UNCERTAIN`), `review_seconds` en `review_notes`. Registreer dit met:

```bash
company-harvest kvk pilot-review --run-dir "$RUN_DIR" --input r8-beoordeling.tsv
```

Een gevonden KVK-nummer blijft voorlopig. `observed_legal_form` en `observed_status`
zijn bronobservaties, geen geverifieerde canonieke velden. Ook een no-match, ambigu of
technische fout verwijdert de oorspronkelijke kandidaat niet. Een succesvolle R8-review
activeert R9 niet zolang de R7-productie- en gebruiksgates openstaan.

Na de gewone filterstappen levert `company-harvest export --run-dir "$RUN_DIR"`
alle actieve, geverifieerde bedrijven uit de gekozen KVK-scope. De actuele
broncode heeft geen `--limit` voor export: een doelgetal kapt de lijst niet
af. Een begrensde `run e2e` gebruikt uitsluitend `--limit-kvk-check` om vooraf
het aantal KVK-zoekopdrachten te beperken; de niet-gecheckte rest blijft
expliciet buiten de partiële eindlijst.

Voor direct gebruik in Excel is er daarnaast
`companies_delivery_light.xlsx` (met gelijknamige CSV) in de outputsetmap.
Die bevat naam/nummer, alle aanwezige zakelijke velden uit de bewaarde
publieke KVK-zoekhit, en `Website (bron)`/`Sector (bron)`. Technische
kolommen en de ruwe respons-JSON staan alleen in `companies_delivery_full.xlsx`.
Bronwebsite en -sector zijn niet door KVK geverifieerd; lege cellen betekenen
dat de waarde niet beschikbaar was, niet dat KVK een negatieve uitspraak deed.
Een onbekend nieuw KVK-responsveld met inhoud stopt de lichte export tot het veld is
beoordeeld. Zie [het volledige outputcontract](output-files.md) voor
bestandsrollen, kolommen, manifest en audit.

`report` schrijft een leesbaar runrapport en een `outcome_report.json`. Dat machineleesbare rapport bevat per-broncijfers, identifierdekking, deduplicatie/conflicten, reviewvolume, kandidaatdiversiteit en gemeten overlap, count-closure per beschikbare procesovergang, doorlooptijd, piekgeheugen en lokale opslaggroei. `PARTIAL_CLOSED` betekent dat alle uitgevoerde overgangen sluiten maar latere stappen nog niet zijn uitgevoerd; alleen `COMPLETE_CLOSED` bestrijkt de hele pipeline. Nieuwe runs en rapporten vermelden ook de uitgaande User-Agent `company-lookup/0.1`.
