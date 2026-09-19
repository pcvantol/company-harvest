# ADR-009 — Geïntegreerde, runbreed begrensde E2E-verwerking

Status: Accepted (2026-09-19). Execution ID: CH-2026-09-19-020.

De eigenaar vraagt één CLI-commando op een kale machine plus een harde
`--limit-kvk-check N` voor veilige verticale proeven. `run e2e` blijft een
expliciet te starten actie van een geïnstalleerde wheel. Zonder een bewuste
`--limit-kvk-check N` of `--all-kvk` begint geen KVK-loop. De broninname blijft
full-scope; de KVK-begrenzing is geen inhoudelijk bronfilter.

Een beperkte run schrijft vóór de eerste GET een onveranderlijke prefixcohort
van de actuele, volledig gevalideerde pre-KVK-eligible-lijst. Metadata bindt
N, SHA-256 van de volledige en geselecteerde input en gesloten aantallen
`full = selected + not_checked`. De publieke KVK-run leest uitsluitend deze
cohort. Daardoor blijft N over CLI-herstarts een bovengrens; bestaande
requests inclusief onderbroken/onzekere pogingen tellen mee. Bij gewijzigde
bron, filter, cohort of N faalt de run gesloten.

De cohort is een expliciete **partitie voor een proef**, niet een bewijs dat
de overgeslagen kandidaten ongeschikt zijn. KVK-matches/unresolved worden pas
na terminale sluiting van de geselecteerde cohort voor downstream geregistreerd.
Canonisering en de rechtsvorm-/statusfilters blijven ongewijzigd. De export
begrensd op N unieke KVK-nummers krijgt PARTIAL zodra `not_checked > 0`;
onopgeloste kandidaten binnen de gekozen cohort eisen daarnaast een
expliciete `--allow-partial`, ook wanneer de cohort de volledige input omvat.
het outputmanifest en outcome-rapport vermelden de cohort. De audit toetst
inputprefix, journalsubset, closure, outputlimiet, status en hashes. Zij leest
ook PARTIAL-manifests in plaats van alleen COMPLETE-manifests.

Aanvulling CH-2026-09-19-022: de nieuwste geregistreerde outputset bepaalt
de audit. Ook een PARTIAL-manifest moet expliciet zijn status vermelden,
overeenkomen met de runstatus en vijf bestanden uit dezelfde outputset met
dezelfde registratiestatus, grootte en hash aanwijzen. Alleen de melding
`MISSING_REQUIRED` onderdrukken is geen integriteitsbewijs.

Aanvulling CH-2026-09-19-023: elke CI-platformjob doorloopt een expliciete
offline E2E-integratiepoort met echte CLI-orkestratie en downstreamverwerking,
maar synthetische broncollectors en een gemockte KVK-zoekfunctie. De poort
verbiedt niet-lokale netwerkverbindingen, maar laat lokale Playwright-IPC toe,
en toetst output, audit en hervatten. Live
bron-/KVK-capability blijft bewust buiten CI en krijgt geen impliciete PASS.

Een eerder lokaal gejournalde toegangs-/rateblokkade verhindert een nieuwe
geïntegreerde run in dezelfde datamap. De blokkadecheck wordt onder de
providerlock vóór elke GET herhaald, zodat een blokkade die tijdens de
broninname van een andere run optreedt niet wordt gemist. Een andere datamap
mag niet als omweg dienen. HTTP- en providerlocks, globale pacing,
één pagina/één poging en cooldown blijven behouden. Geen providerwissel,
betaalde API of automatische retry bij blokkade. De vroegere v1.0.0-release
blijft ongewijzigd; nieuwe functionaliteit vereist een nieuw gekwalificeerd
releaseartefact. Stap 9, de union met een externe bronlijst, blijft apart:
zo'n union kan de N-grens van de KVK-eindlijst niet impliciet behouden.
