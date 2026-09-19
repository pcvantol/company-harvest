# CH-2026-09-19-020 — geïnstalleerde-wheelproef

Datum: 2026-09-19. Status: **PASS, uitsluitend synthetisch/offline**.

Een lokaal gebouwde 1.1.0-wheel is in een schone tijdelijke `site`-map
geïnstalleerd. De test draaide vanuit een andere werkmap dan de checkout en
assertte dat `company_harvest.__file__` onder die geïnstalleerde map lag.
Bronartefacten en KVK-respons werden door een zelfstandige synthetische
testharness geleverd; er is dus niets van externe bronnen gedownload en geen
live KVK-aanroep gedaan. De productiecode van de wheel voerde wel het
geïntegreerde CLI-commando, pre-KVK-dedup/filter, cohortbinding, KVK-journal,
canonisering, export, rapportage en audit uit.

| Controle | Waarneming |
|---|---:|
| CLI `run e2e --limit-kvk-check 1` | exit 0 |
| Geïnstalleerde package buiten checkout | bevestigd |
| Synthetische KVK-zoekaanroepen | 1 |
| Volledige eligible-lijst / gekozen cohort / buiten cohort | 2 / 1 / 1 |
| Eindlijst | 1 regel, `PARTIAL_EXPORTED` |
| `audit verify` | `valid=true` |
| Hervatten met dezelfde run en limiet | exit 0, nog steeds 1 totale zoekaanroep |

Daarnaast slaagt de reguliere offline test met 62 eligible kandidaten,
`--limit-kvk-check 50`, precies 50 gesimuleerde KVK-verzoeken en 50
eindregels. Dit bewijst de begrenzingslogica, niet de bereikbaarheid of
toegestaanheid van de publieke KVK-route. De eerdere echte HTTP 400 is niet
opnieuw getest of omzeild. De 1.1.0-wheel is lokaal gebouwd, niet gepubliceerd.
