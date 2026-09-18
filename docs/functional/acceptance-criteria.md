# Acceptatiecriteria

De softwarekwalificatie vereist: werkende offline workflows, atomische uitvoer, hervatbare state, auditchecks, veilige packaging, verse wheelinstallatie, per-file coverage boven 80%, lint/typechecks, publicatiescan en onafhankelijke review. Externe acceptatie vereist daarnaast een begrensde actuele bron-/KVK-smoke-test. Releaseacceptatie vereist correcte remote-authenticatie, CI, tag, publieke assets en herinstallatie van de anoniem gedownloade wheel.

Statussen zijn `IMPLEMENTED`, `OFFLINE_TESTED`, `LIVE_PROVEN`, `NOT_TESTED` of `BLOCKED`. Geen status impliceert een andere.

R1 is offline geaccepteerd wanneer een CLI-slice een namenbron zonder KVK-kolom verliesvrij importeert, dedupliceert en rapporteert; catalogusschema 2 legacywaarden behoudt; het JSON-outcomerapport op lege, dubbele, conflicterende en identifierloze fixtures sluit; en request-, run- en rapporttests dezelfde User-Agent `company-lookup/0.1` aantonen. Live bronopbrengst en succesdrempels vallen onder R2/R3 en worden door R1 niet geclaimd.
