# Architectuur

`cli` routeert naar gedeelde services. `core` beheert runs, SQLite, locks, logging en snapshots. `sources` bevat de begrensde catalogus/adapters. `kvk` implementeert één canoniek providercontract voor waargenomen publieke HTTP en gewone Playwright-interactie. `workflow` verzorgt dedup, filters en export; `merge_lists` is de zelfstandige offline workflow; `audit` verifieert en traceert.

Externe inhoud is uitsluitend data. Host allowlists, HTTPS, response-/redirectgrenzen en syntactische schema-validatie beperken invoer. De runtime gebruikt een gebruikersschrijfbare dataroot, nooit packagebestanden.

Broncatalogusschema 2 is het capabilitycontract voor iedere bron. Ruwe bronrecords behouden de oorspronkelijke identifiertekst en een afzonderlijke validatiestatus, zodat ontbrekende of ongeldige KVK-nummers geen dataverlies veroorzaken. Identifierloze of ongeldige naamgenoten blijven afzonderlijke kandidaten; meerdere geldige KVK-hints bij dezelfde genormaliseerde naam gaan naar conflict. `workflow.outcome_metrics` leest de laatste complete artefacten en produceert via `report` zowel JSON als Markdown. Count-closure wordt afzonderlijk gemeten voor raw→dedup, kandidaat→KVK-terminal, match→canoniek, rechtsvormpartitie, statuspartitie en actief→delivery/reserve. Niet uitgevoerde overgangen staan expliciet op `NOT_AVAILABLE`.

`core.HTTP_USER_AGENT` is de enige runtimebron voor `company-lookup/0.1`. Nieuwe runs leggen deze waarde vast in `run.json`; bron- en KVK-clients en outcome-rapportage gebruiken dezelfde waarde.
