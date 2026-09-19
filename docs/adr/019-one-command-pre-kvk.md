# ADR-019 — Eén opdracht tot vóór de KVK-check

Status: aangenomen voor de nog ongepubliceerde bronversie 3.1.0
(CH-2026-09-19-042).

## Context

`run prepare-pre-kvk` kon de volledige bronvoorbereiding al uitvoeren, maar
vereiste eerst afzonderlijk `run init`. `run e2e` startte wel zelfstandig,
maar ging na de pre-KVK-lijst ook door met de publieke KVK-check. Voor een
bronmomentopname zonder KVK-verkeer ontbrak één expliciete opdracht.

## Besluit

`run pre-kvk` maakt desgewenst een nieuwe HARVEST-run aan en geeft de
absolute runmap onmiddellijk op stdout terug. `--run-dir` hervat dezelfde
run. Host/workflow worden vóór de bronverwerking gecontroleerd; vervolgens
wordt de bestaande, hash-/evidencegebonden `prepare_pre_kvk`-service gebruikt.
Het resultaat noemt de paden van master, masterrapport, gefilterde KVK-invoer,
uitsluitingen en filtermetadata plus gesloten aantallen. Het commando bindt
geen KVK-cohort, start geen provider en maakt geen eind-Excel.

Geen nieuwe `--refresh`-optie op deze geïntegreerde opdracht: standaard
hervatten en behoud van de gebonden bronmomentopname gaan voor. Voor een
bewuste bronverversing blijft de expliciete lage-niveau-opdracht bestaan.
`PRE_KVK_READY` is alleen het CLI-resultaatlabel. De blijvende runstatus
blijft door de bestaande services bepaald.

## Bewijs en gevolgen

Een synthetische vijfbronnentest bewijst een nieuwe run, gesloten
master/filteraantallen, nul KVK-journalrijen en identieke hervatting zonder
nieuwe master/filterartefacten. Fout- en verkeerde-workflowpaden worden
apart getest. Een live volledige download of schaalrun maakt geen deel uit
van dit besluit. Het CLI-contract is additief en krijgt daarom een nieuwe
MINOR-versie; v3.0.0 en de lokaal gebouwde 3.0.1-wheel blijven onveranderd.
