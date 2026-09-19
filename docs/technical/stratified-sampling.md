# Deterministische bron- en dedupsampling

R6 leest uitsluitend de nieuwste COMPLETE CSV per `source_*`-artefact. Ieder bestand
moet bestaan en byte-identiek zijn aan zijn geregistreerde SHA-256 voordat selectie
begint. Rapport- en rejected-artefacten vallen niet onder deze selectie.

## Selectiecontract

De eerste laag is `source_family`; beschikbare capaciteit wordt in gesorteerde
round-robinrondes gelijk verdeeld. Binnen iedere familie gebeurt hetzelfde over
`VALID_DIRECT` en `WITHOUT_DIRECT`. Niet-benutte capaciteit vloeit automatisch naar
strata met resterende records. Binnen ieder stratum wint de laagste SHA-256 over de
canoniek geserialiseerde volledige bronrij. Daardoor leveren dezelfde bronartefacten en
parameters dezelfde sample op, onafhankelijk van uitvoertijd. De inputfingerprint bindt
zowel alle bronartefacthashes als de catalogushash en canonieke bron→familie-indeling.

De sample doorloopt exact dezelfde voorlopige deduplicatieregels als `companies merge`:
genormaliseerde naam plus dezelfde niet-lege KVK-hint mag worden samengevoegd; meerdere
verschillende hints bij dezelfde naam gaan volledig naar conflict; zonder hint worden
records niet alleen op naam samengevoegd. De closure vergelijkt bronrecords met de som
van alle decision-inputs en conflictinputs.

## Review en R8-overdracht

De reviewqueue neemt alle merges en conflicten op zolang de ingestelde omvang dit
toelaat. Resterende plaatsen worden deterministisch gestratificeerd over bronfamilie en
identifierstatus met `KEPT_SINGLE`-beslissingen. Een assessment is alleen geldig als
iedere actuele `review_id` exact eenmaal een toegestaan verdict heeft én iedere regel de
geregistreerde actuele queue-SHA-256 declareert. De queue zelf wordt eerst tegen haar
COMPLETE-registratie, grootte en hash gecontroleerd. `FALSE_MERGE` of `UNCERTAIN` maakt
de reviewstatus `CHANGES_REQUIRED`.

Een nieuwe sample publiceert bronrijen, kandidaten, beslissingen, conflicten, queue,
pilot en beide rapporten in één SQLite-transactie. In dezelfde transactie worden eerdere
reviewresultaten en alle downstreamartefacten stale. Runtimeconfiguratie gebruikt
`PUBLISHING` vóór en `COMPLETE` na de transactie, zodat een onderbreking geen oude PASS
als actueel presenteert.

De R8-pilotpool wordt uitsluitend uit kandidaten zonder direct geldig KVK-nummer
gevormd, gelijk verdeeld over hun bronfamilies en opnieuw met een stabiele kandidaathash.
R6 doet geen KVK-frontendcall. Het R6-rapport legt vóór R8 de terminale uitkomsten en
vereiste opbrengst-, review-, fout-, tijd- en opslagmetrics vast; thresholds volgen pas
na de gemeten pilot.
Omdat deze historische pilotpool juist geen directe KVK-hint heeft, mag de
huidige nummer-only-policy geen live KVK-zoekopdracht vanuit R8 versturen.

Alle rijen, beoordelingen en pilotkandidaten blijven lokale runartefacten. Alleen
geaggregeerde meetresultaten en schema-/contractdocumentatie mogen worden gepubliceerd.
