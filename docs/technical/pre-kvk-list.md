# Pre-KVK-bronlijst en foutgrenzen

`company-lookup run pre-kvk` is vanaf de huidige ongepubliceerde broncode
de geïntegreerde ingang vóór de KVK-check. Zonder `--run-dir` initialiseert
het een nieuwe HARVEST-run; met `--run-dir` opent het precies die bestaande
run. Na host-/workflowpreflight roept het dezelfde `prepare_pre_kvk`-service
aan als de bestaande voorbereiding. Het commando toont de runmap vóór de
lange broninname en geeft daarna het masterpad, rapportpad, gefilterde
`kvk_input`, uitsluitingsledger, metadata en gesloten aantallen terug.
`PRE_KVK_READY` in de CLI-uitvoer is een resultaatlabel, geen KVK-status.
Er wordt geen KVK-scope gebonden, provider gebruikt of export gestart.
Voltooide, integere bron-, master- en filterartefacten worden bij hervatten
hergebruikt; een afgebroken download kan opnieuw moeten beginnen.

`company-lookup run prepare-pre-kvk --run-dir RUN_DIR` downloadt of hergebruikt
IND, GLEIF, ANBI, DUO en TenderNed in deze volgorde en bouwt daarna één master. Wikidata
is uitgesloten. `company-lookup companies pre-kvk-list --run-dir RUN_DIR` is de
afzonderlijke offline lijstbouwopdracht. Zij doet geen bron- of KVK-verzoeken.
De master eist voor nieuwe runs vijf geselecteerde bronartefacten met
COMPLETE-registratie, exacte SHA-256/grootte, onbeperkte full-scope-inname,
count-closure en intacte response-/archivevidence. Ontbreekt één bewijs,
dan faalt de opdracht vóór publicatie van een master.
Bestaande runs met een gebonden vierbronnenscope blijven bewust op dat
historische contract; bronartefacten worden niet stil gemengd. Nieuwe runs
krijgen `source_portfolio_version=2` in `run.json`. Runs zonder die marker
blijven ook na onderbreking vóór de eerste of laatste brondownload vierbrons.

De builder spooled de ruwe kandidaatregels naar lokale SQLite met unieke
`(source_id,source_row)`-sleutel. Zij groepeert op genormaliseerde naam en
geldige directe KVK-hint. Een identieke naam zonder hint wordt niet
automatisch als dezelfde onderneming behandeld. Een gelijk hintnummer bij
verschillende namen of verschillende nummers bij dezelfde naam wordt als
`SOURCE_CONFLICT` zichtbaar. De lijst bewaart per kandidaat de volledige
originele payloads en afzonderlijke bronrelaties. De som van
`source_count` moet gelijk zijn aan alle opgenomen bronregels; de inputs
worden onder run-lock nogmaals gevalideerd vóór atomische publicatie.
Bij samengevoegde kandidaten projecteert de master voor `website` en
`sector` afzonderlijk de eerste niet-lege bronwaarde in vaste bronvolgorde.
De volledige payloads blijven behouden; deze projectie is broninformatie,
geen KVK-verificatie. De [lichte eindlijst](../functional/output-files.md)
gebruikt deze waarden alleen bij exact kandidaat-ID én KVK-nummer.

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
volledige gebonden bronmaster vier nieuwe lokale artefacten: een KVK-geschikte
TSV met volledige masterrijen, een uitsluitingsledger, een reviewlabel-TSV
en JSON-metadata.
`prepare-pre-kvk` voert deze stap voortaan automatisch na de masterbouw uit.
De filter heeft een expliciete regelversie. De metadata bevat alle criteria
en letterlijk uitgevoerde naamregexen met hoofdlettervlag,
primaire én overlappende redenaantallen, kandidaat-/bestandsaantallen en
SHA-256-bindingen, ook voor de label-TSV. Elke uitgesloten kandidaat blijft via zijn ID, naam,
bron-IDs en alle redenen in de ledger zichtbaar; de volledige bronpayload
blijft in de ongewijzigde master. `NO_DIRECT_KVK_HINT` is geen bewijs van
feitelijk ontbreken van een KVK-inschrijving. ANBI en DUO worden op bronrelatie
uitgesloten; de overige categorieën gebruiken zelfstandige naamtermen,
geen onbeperkte substringzoekactie. Bronconflicten blijven aparte reviewrijen.
Vanaf regelversie 8 is `HOLDING_OR_MANAGEMENT` uitsluitend een reviewlabel,
geen uitsluitreden. De lokale `pre_kvk_review_labels.tsv` bevat kandidaat-ID,
naam, KVK-hint en label; het volledige exportbestand bevat `candidate_id`
waarmee een label later kan worden gekoppeld. Een andere uitsluitreden blijft
ook voor holdings van kracht.
De count-closure is master = geschikt + uitgesloten. Een regelwijziging of
bestandsafwijking vereist een nieuw filter; een reeds gebruikte KVK-journal
blokkeert stil herfilteren.
De streaming partitie en de latere metadata-/artefactpublicatie zijn intern
gescheiden (ADR-011), zonder wijziging van dit contract. Bijna-gelijke
bedrijfsnamen zijn geen uitsluitingsgrond; de verkennende
[naamvariantenmeting](../measurements/20260919-pre-kvk-name-variants.md) heeft
geen fuzzy filter geactiveerd.

Vanaf bronversie 3.0.1 accepteert de gedeelde CSV-/TSV-parser velden tot
1.048.576 tekens, ook wanneer de volledige JSON-bronpayload van één masterrij boven
Python's standaardgrens van 131.072 tekens komt. Dezelfde begrensde instelling
geldt voor latere cohort-, KVK- en exportlezers; boven deze veldgrens wordt niet
afgekapt maar gestopt. Zie [ADR-018](../adr/018-bounded-csv-field-size.md).

`kvk pre-kvk-batch --run-dir RUN_DIR --limit 10` leest uitsluitend de
gefilterde, geregistreerde en aan de actuele master gebonden lijst. Ontbreekt
die of wijkt de regelversie/hash af, dan stopt de opdracht vóór de provider.
De publieke HTTP-provider volgt de waargenomen route van de
KVK-frontend. De opdracht verstuurt uitsluitend de geldige achtcijferige
bron-KVK-hint als zoekterm en accepteert alleen een exact gelijk teruggegeven
KVK-nummer; de naam is geen matchvoorwaarde. Zonder geldige hint wordt geen
naamzoekopdracht verstuurd. De opdracht gebruikt de lokale providerlock,
requestjournal en cooldown, slaat conflictrijen over en bewaart responsevidence.
De nummerzoeking is offline gemockt; de aangeleverde frontendscreenshot toont
dat zoeken op nummer via de website mogelijk is, maar de directe Web-API-route
is met een nummer nog niet live geverifieerd.
Maximaal tien nieuwe requests per aanroep, minimaal twee seconden tussentijd;
een gedeeld lokaal pacingjournal overleeft een CLI-herstart en begrenst ook
opeenvolgende batches. Per kandidaat wordt maximaal één eerste-pagina-GET
zonder automatische retry uitgevoerd; meer zoekhits blijven onvolledig.
Een toegangs- of rateblokkade stopt de batch. Alle batchoutputs blijven
`PARTIAL`, zodat `kvk consolidate` en export ze niet als volledige verificatie
kunnen lezen. Dit laatste gold voor ADR-006; ADR-008 voegt een afzonderlijke
expliciete langlopende opdracht toe.

`kvk pre-kvk-run --run-dir RUN_DIR --until-complete --interval 2` gebruikt
dezelfde gefilterde input, één pagina en één poging per kandidaat. Met
`--max-requests N` is een begrensde sessie mogelijk. Iedere aanvraag heeft
een duurzaam SQLite-journalrecord; na iedere uitkomst worden lokale TSV's
en een atomisch voortgangs-JSON bijgewerkt. Bij herstart worden de TSV's uit
de journal gereconstrueerd. Onzekere verzoekuitkomsten worden niet stil
opnieuw bevraagd. Alleen een volledige, hashgebonden kandidaatpartitie zonder
actieve blokkade levert `kvk_matches`/`kvk_unresolved` met status `COMPLETE`
voor vervolgsteps. `COMPLETE` zegt niets over het aandeel geverifieerde
matches; technische en onzekere uitkomsten blijven expliciet unresolved.

De eenmalige, genegeerde lokale Wikidata-hervattingsrunner bewaart
SPARQL-projectiepagina's en aparte labelbatches met request-/bodyhash,
grootte en tijd. HTTP-fouten en ongeldige JSON houden lokaal foutbewijs.
Alle nieuwe verzoeken zijn sequentieel, lopen uitsluitend via allowlisted
HTTPS en stoppen bij toegangs-/rateblokkade. De publieke WDQS-grens is geen
bewijs van een simultane peildatum; de waargenomen OFFSET-paginering kan
bij tussentijdse wijzigingen in de bron verschuiven.
