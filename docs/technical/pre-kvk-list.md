# Pre-KVK-bronlijst en foutgrenzen

`company-harvest companies pre-kvk-list --run-dir RUN_DIR` is een offline
productopdracht. Zij doet geen bron- of KVK-verzoeken. De opdracht eist de
vijf actieve bronartefacten van IND, Wikidata P3220, GLEIF, ANBI en DUO met
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

De eenmalige run CH-2026-09-19-009 kreeg een HTTP 429 bij Wikidata en heeft
daarom geen volledige master. Voor de vier wel volledig verzamelde bronnen
is offline de aparte `pre_kvk_blocked_preview` gemaakt. Deze heeft dezelfde
lossless dedup- en closurecontroles, maar **alle** rijen krijgen
`BLOCKED_SOURCE_INCOMPLETE`; de artefactsoort is niet `pre_kvk_master`, het
rapport noemt Wikidata als uitgesloten en de run blijft `PRE_KVK_BLOCKED`.
De preview mag niet worden aangeboden aan `kvk resolve` of als volledige
vijfbronnenlijst worden geïnterpreteerd.

De eenmalige, genegeerde lokale Wikidata-hervattingsrunner bewaart
SPARQL-projectiepagina's en aparte labelbatches met request-/bodyhash,
grootte en tijd. HTTP-fouten en ongeldige JSON houden lokaal foutbewijs.
Alle nieuwe verzoeken zijn sequentieel, lopen uitsluitend via allowlisted
HTTPS en stoppen bij toegangs-/rateblokkade. De publieke WDQS-grens is geen
bewijs van een simultane peildatum; de waargenomen OFFSET-paginering kan
bij tussentijdse wijzigingen in de bron verschuiven.
