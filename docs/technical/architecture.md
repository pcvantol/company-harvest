# Architectuur

`cli` routeert naar gedeelde services. `core` beheert runs, SQLite, locks, logging en snapshots. `sources` bevat de begrensde catalogus/adapters. `kvk` implementeert één canoniek providercontract voor waargenomen publieke HTTP en gewone Playwright-interactie. `workflow` verzorgt dedup, filters en export; `merge_lists` is de zelfstandige offline workflow; `audit` verifieert en traceert.

Externe inhoud is uitsluitend data. Host allowlists, HTTPS, response-/redirectgrenzen en syntactische schema-validatie beperken invoer. De runtime gebruikt een gebruikersschrijfbare dataroot, nooit packagebestanden.

Broncatalogusschema 2 is het capabilitycontract voor iedere bron. Ruwe bronrecords behouden de oorspronkelijke identifiertekst en een afzonderlijke validatiestatus, zodat ontbrekende of ongeldige KVK-nummers geen dataverlies veroorzaken. Identifierloze of ongeldige naamgenoten blijven afzonderlijke kandidaten; meerdere geldige KVK-hints bij dezelfde genormaliseerde naam gaan naar conflict. `workflow.outcome_metrics` leest de laatste complete artefacten en produceert via `report` zowel JSON als Markdown. Count-closure wordt afzonderlijk gemeten voor raw→dedup, kandidaat→KVK-terminal, match→canoniek, rechtsvormpartitie, statuspartitie en actief→delivery/reserve. Niet uitgevoerde overgangen staan expliciet op `NOT_AVAILABLE`.

`core.HTTP_USER_AGENT` is de enige runtimebron voor `company-lookup/0.1`. Nieuwe runs leggen deze waarde vast in `run.json`; bron- en KVK-clients en outcome-rapportage gebruiken dezelfde waarde.

`pre_kvk` bouwt de volledige vierbronnenmaster. `pre_kvk_filter` maakt daaruit
een byte- en regelversiegebonden KVK-toelatingslijst plus uitsluitingsledger;
`pre_kvk_kvk` weigert iedere andere invoer vóór netwerkverkeer. Deze splitsing
houdt brede brondekking gescheiden van een herzienbare, expliciete
verificatieprioritering.

`end_to_end` routeert dezelfde services in één expliciete CLI-opdracht.
`kvk_scope` bindt een begrensde proef vóór de eerste GET aan de volledige
filterhash en een vaste prefixcohort. De KVK-journal en downstream-closure
betreffen dan alleen die cohort; de niet-bevraagde rest blijft afzonderlijk
zichtbaar en de outputstatus is PARTIAL. Audit controleert de cohortbinding,
request-/eindlijstgrens en ook PARTIAL-outputsets. Een nieuwe E2E-run in
dezelfde datamap negeert een eerder gejournalde toegangsblokkade niet.

`gleif` is de eerste bulkadapter op de brede-innamebasis. Zij levert hetzelfde `RAW_HEADERS`-
contract als de kleine bronadapters, maar houdt download-, ZIP- en streamingverwerking
afzonderlijk zodat `sources collect` nooit impliciet een groot bestand ophaalt. Immutable
evidence blijft de verliesvrije ruwe laag; de TSV is de kandidaatlaag; KVK-verificatie en
definitieve filters blijven latere, afzonderlijke overgangen.
