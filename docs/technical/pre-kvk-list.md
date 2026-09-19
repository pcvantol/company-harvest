# Pre-KVK-bronlijst en foutgrenzen

`company-harvest run prepare-pre-kvk --run-dir RUN_DIR` downloadt of hergebruikt
IND, GLEIF, ANBI en DUO in deze volgorde en bouwt daarna één master. Wikidata
is uitgesloten. `company-harvest companies pre-kvk-list --run-dir RUN_DIR` is de
afzonderlijke offline lijstbouwopdracht. Zij doet geen bron- of KVK-verzoeken.
De master eist de vier geselecteerde bronartefacten met
COMPLETE-registratie, exacte SHA-256/grootte, onbeperkte full-scope-inname,
count-closure en intacte response-/archivevidence. Ontbreekt één bewijs,
dan faalt de opdracht vóór publicatie van een master.

De builder spooled de ruwe kandidaatregels naar lokale SQLite met unieke
`(source_id,source_row)`-sleutel. Zij groepeert op genormaliseerde naam en
geldige directe KVK-hint. Een identieke naam zonder hint wordt niet
automatisch als dezelfde onderneming behandeld. Een gelijk hintnummer bij
verschillende namen of verschillende nummers bij dezelfde naam wordt als
`SOURCE_CONFLICT` zichtbaar. De lijst bewaart per kandidaat de volledige
originele payloads en afzonderlijke bronrelaties. De som van
`source_count` moet gelijk zijn aan alle opgenomen bronregels; de inputs
worden onder run-lock nogmaals gevalideerd vóór atomische publicatie.

De historische run CH-2026-09-19-009 kreeg een HTTP 429 bij Wikidata en had
onder het toenmalige vijfbronnencontract geen volledige master. Voor de vier
wel volledig verzamelde bronnen is destijds offline de aparte
`pre_kvk_blocked_preview` gemaakt. Deze heeft dezelfde
lossless dedup- en closurecontroles, maar **alle** rijen krijgen
`BLOCKED_SOURCE_INCOMPLETE`; de artefactsoort is niet `pre_kvk_master`, het
rapport noemt Wikidata als uitgesloten en de run stond destijds
`PRE_KVK_BLOCKED`.
De preview mag niet worden aangeboden aan een KVK-provider. Onder het nieuwe
vierbronnencontract bouwt de tool een nieuw, byte-gebonden `pre_kvk_master`-artefact.
Historische previewrecords blijven ongewijzigd. CH-2026-09-19-010 heeft
dezelfde lokale run onder het nieuwe vierbronnencontract voortgezet: die run
staat nu `PRE_KVK_COMPLETE` met een apart nieuw masterartefact. Deze actuele
status verandert de historische previewstatus niet.

`companies pre-kvk-filter --run-dir RUN_DIR` maakt zonder netwerk uit de
volledige vierbronnenmaster drie nieuwe lokale artefacten: een KVK-geschikte
TSV met volledige masterrijen, een uitsluitingsledger en JSON-metadata.
`prepare-pre-kvk` voert deze stap voortaan automatisch na de masterbouw uit.
De filter heeft een expliciete regelversie. De metadata bevat alle criteria
en letterlijk uitgevoerde naamregexen met hoofdlettervlag,
primaire én overlappende redenaantallen, kandidaat-/bestandsaantallen en
SHA-256-bindingen. Elke uitgesloten kandidaat blijft via zijn ID, naam,
bron-IDs en alle redenen in de ledger zichtbaar; de volledige bronpayload
blijft in de ongewijzigde master. `NO_DIRECT_KVK_HINT` is geen bewijs van
feitelijk ontbreken van een KVK-inschrijving. ANBI en DUO worden op bronrelatie
uitgesloten; de overige categorieën gebruiken zelfstandige naamtermen,
geen onbeperkte substringzoekactie. Bronconflicten blijven aparte reviewrijen.
De count-closure is master = geschikt + uitgesloten. Een regelwijziging of
bestandsafwijking vereist een nieuw filter; een reeds gebruikte KVK-journal
blokkeert stil herfilteren.

`kvk pre-kvk-batch --run-dir RUN_DIR --limit 10` leest uitsluitend de
gefilterde, geregistreerde en aan de actuele master gebonden lijst. Ontbreekt
die of wijkt de regelversie/hash af, dan stopt de opdracht vóór de provider.
De publieke HTTP-provider volgt de waargenomen route van de
KVK-frontend. De opdracht gebruikt de lokale providerlock, requestjournal en
cooldown, slaat conflictrijen over en bewaart responsevidence. De historische
naam-zonder-hint-matchvoorwaarde blijft in code maar wordt door deze nieuwe
filter niet meer bereikt.
Maximaal tien nieuwe requests per aanroep, minimaal twee seconden tussentijd;
een gedeeld lokaal pacingjournal overleeft een CLI-herstart en begrenst ook
opeenvolgende batches. Per kandidaat wordt maximaal één eerste-pagina-GET
zonder automatische retry uitgevoerd; meer zoekhits blijven onvolledig.
Een toegangs- of rateblokkade stopt de batch. Alle batchoutputs blijven
`PARTIAL`, zodat `kvk consolidate` en export ze niet als volledige verificatie
kunnen lezen. Een volledige frontendreeks is niet vrijgegeven.

De eenmalige, genegeerde lokale Wikidata-hervattingsrunner bewaart
SPARQL-projectiepagina's en aparte labelbatches met request-/bodyhash,
grootte en tijd. HTTP-fouten en ongeldige JSON houden lokaal foutbewijs.
Alle nieuwe verzoeken zijn sequentieel, lopen uitsluitend via allowlisted
HTTPS en stoppen bij toegangs-/rateblokkade. De publieke WDQS-grens is geen
bewijs van een simultane peildatum; de waargenomen OFFSET-paginering kan
bij tussentijdse wijzigingen in de bron verschuiven.
