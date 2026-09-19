# Acceptatiecriteria

De softwarekwalificatie vereist: werkende offline workflows, atomische uitvoer, hervatbare state, auditchecks, veilige packaging, verse wheelinstallatie, per-file coverage boven 80%, lint/typechecks, publicatiescan en onafhankelijke review. Externe acceptatie vereist daarnaast een begrensde actuele bron-/KVK-smoke-test. Releaseacceptatie vereist correcte remote-authenticatie, CI, tag, publieke assets en herinstallatie van de anoniem gedownloade wheel.

Statussen zijn `IMPLEMENTED`, `OFFLINE_TESTED`, `LIVE_PROVEN`, `NOT_TESTED` of `BLOCKED`. Geen status impliceert een andere.

R1 is offline geaccepteerd wanneer een CLI-slice een namenbron zonder KVK-kolom verliesvrij importeert, dedupliceert en rapporteert; catalogusschema 2 legacywaarden behoudt; het JSON-outcomerapport op lege, dubbele, conflicterende en identifierloze fixtures sluit; en request-, run- en rapporttests dezelfde User-Agent `company-lookup/0.1` aantonen. Live bronopbrengst en succesdrempels vallen onder R2/R3 en worden door R1 niet geclaimd.

R4 is geaccepteerd wanneer de GLEIF-adapter met realistische offline fixtures en een
begrensde actuele evidence-run slaagt; download-, ZIP-, schema-, ruimte- en identifiergates
zijn getest; evidence en ruwe afwijzingen verliesvrij blijven; ontbrekende/ongeldige
identifiers kandidaten niet verwijderen; beide adapterpartities sluiten; hergebruik en
downstream-invalidatie aantoonbaar zijn; en opbrengst plus expliciete nul-/niet-nuloverlap
in het outcome-rapport staan zonder bronstatus als KVK-verificatie te labelen.

R5 is geaccepteerd wanneer minimaal vijf bruikbare bronfamilies aantoonbaar actief zijn,
zes kandidaatbronnen een volledige feasibilitykaart hebben, en de expliciete ANBI-/DUO-
adapters hun streaming-, veiligheids-, identifier- en count-closurecontracten halen
zonder impliciete bulkdownload of historische catalogusmutatie tijdens pure reads.

R6 is geaccepteerd wanneer dezelfde bronfingerprint steeds dezelfde 500-recordsample
oplevert, alle actieve families en beschikbare identifierstrata vertegenwoordigd zijn,
bronrecords volledig sluiten naar dedupbeslissing of conflict, een exact gekoppelde
gestratificeerde review geen onverklaarde false merge toont, en een 50-record-R8-pool plus
vooraf bepaald metriekcontract lokaal gereedstaan zonder KVK-frontendcall.

R8 is geaccepteerd wanneer de volledige R6-overdracht op hash en grootte is gevalideerd;
iedere pilotkandidaat exact één terminale uitkomst heeft; geen nummer op naam, domein of
score alleen wordt gekoppeld; ieder gekoppeld nummer een exact onafhankelijk bronveld en
voorlopige verificatiestatus draagt; blokkades en hervatting gesloten zijn; de
transactionele output/reviewlifecycle is getest; en een hashgebonden gestratificeerde
review nul false matches en nul uncertain oplevert bij maximaal 5% technische fouten.
Dit beschrijft de historische R8-pilotkwalificatie. Onder ADR-016 doet een
nieuwe no-hint-pilot geen live naamzoeking meer en kan zij zonder voldoende
offline matches deze oude acceptatiedrempels niet halen; dat is een bewuste
fail-closed uitkomst, geen geverifieerde KVK-verrijking.

De historische vijfbronnenacceptatie faalde op 2026-09-19 wegens Wikidata
HTTP 429; alleen een apart geblokkeerde vierbronnenpreview was toen mogelijk.
Onder het latere RD-008-besluit vereiste de toenmalige master vier complete,
byte- en scopegebonden bronnen (IND, GLEIF, ANBI, DUO). Nieuwe 3.0.0-runs
vereisen daarnaast TenderNed als vijfde bron; oudere gebonden vierbronnenruns
blijven op hun oorspronkelijke scope. Beide varianten vereisen unieke
bronrij-identiteit en input→master-closure zonder KVK-requests.

De huidige KVK-batchacceptatie vereist vervolgens een offline filter met
bekende regelversie, volledige criteria, een itemniveau-uitsluitingsledger,
gesloten master = geschikt + uitgesloten, bytebindingen en nul onbedoelde
KVK-requests. Een ontbrekende of stale filterset stopt vóór de provider.

De lichte-exportacceptatie voor de 3.0.0-broncode vereist een afzonderlijke
CSV/XLSX met de daadwerkelijk aanwezige zakelijke KVK-hitvelden en de als
bron gemarkeerde website/sector, zonder ruwe JSON of technische metadata.
Exacte kandidaat-ID/nummerjoin, schema-2-manifest (zeven bestanden),
PARTIAL-audit en schema-1-legacycontrole moeten offline aantoonbaar slagen.
Dat is met gemockte KVK-resultaten getest; een nieuwe live nummerzoekactie
of volledige productie-export is **niet getest** en wordt hier niet als
externe acceptatie of releasegoedkeuring gepresenteerd.
