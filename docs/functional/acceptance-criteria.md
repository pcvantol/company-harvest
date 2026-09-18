# Acceptatiecriteria

De softwarekwalificatie vereist: werkende offline workflows, atomische uitvoer, hervatbare state, auditchecks, veilige packaging, verse wheelinstallatie, per-file coverage boven 80%, lint/typechecks, publicatiescan en onafhankelijke review. Externe acceptatie vereist daarnaast een begrensde actuele bron-/KVK-smoke-test. Releaseacceptatie vereist correcte remote-authenticatie, CI, tag, publieke assets en herinstallatie van de anoniem gedownloade wheel.

Statussen zijn `IMPLEMENTED`, `OFFLINE_TESTED`, `LIVE_PROVEN`, `NOT_TESTED` of `BLOCKED`. Geen status impliceert een andere.

