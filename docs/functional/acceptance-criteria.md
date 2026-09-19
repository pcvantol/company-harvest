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

Een volledige pre-KVK-master vereist vijf complete, byte- en scopegebonden
bronnen, unieke bronrij-identiteit, input→master-closure en nul KVK-requests.
Een geblokkeerde bron staat alleen een apart gemarkeerde preview toe:
uitgesloten bron zichtbaar, alle wachtrijregels geblokkeerd, geen
statuspromotie. De 2026-09-19-run haalde de vierbronnenpreviewgate, maar
faalde de vijfbronnenacceptatie wegens Wikidata HTTP 429.
