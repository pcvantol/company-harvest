# Logging en audit

Iedere run schrijft `execution.log` en `events.jsonl` met UTC-tijd, level, event, run/recordcontext en geschoonde fouten. Credentialachtige waarden worden geredigeerd. Volledige providerresponses staan alleen onder lokaal bewijs.

Artefacten krijgen SHA-256, grootte, stap, type en status in SQLite. `audit verify` controleert bestaan/grootte/hash. `audit trace` zoekt een KVK-nummer door tabulaire snapshots en toont bron→stap→output. Dit detecteert wijzigingen, maar beschermt niet tegen iemand die database en bestanden met dezelfde rechten herschrijft.

`report` registreert een immutable JSON-outcomerapport en daarna het leesbare Markdown-runrapport. Het JSON-artefact vermeldt zijn eigen schema, run-/catalogusschema, User-Agent, meetmoment, per-broncijfers, closure per procesovergang, werkelijk gemeten kandidaat-overlap/concentratie en resourceobservaties. Nieuwe runs bewaren een lokale SQLite-/evidencebaseline, zodat het rapport actuele bytes én groei kan onderscheiden. Oude runs zonder baseline tonen `UNAVAILABLE_BASELINE` in plaats van een geschatte groei.

`sources list` mag een legacycatalogus expliciet naar een nieuw immutable schema-2-artefact migreren. De meetfunctie zelf leest en normaliseert de catalogus zonder die migratieschrijfactie, zodat rapportberekening geen verborgen catalogusmutatie veroorzaakt.

`sources measure` registreert per bron de meetstatus, scope, volledigheid, brondatum,
record- en identifierclosure, duplicaten, parserafwijzingen, duur, responsaantal en -bytes,
HTTP-statussen en waargenomen rate-limitheaders. Het JSON- en Markdownrapport worden als
immutable stap-02-artefacten geregistreerd. Ruwe responses blijven uitsluitend in lokale
evidence; canonieke documentatie bevat alleen aggregaten.

`sources gleif` registreert daarnaast het originele ZIP-bestand als stap-02-evidence,
een kandidaatbestand, een afzonderlijk identifier-/naam-rejectedbestand en JSON-/Markdown-
innamerapport. Het rapport bevat evidencehash en -omvang, CSV-omvang, lokale of HTTP-
acquisitiemetadata, scope, duur, alle partitieaantallen en twee closurecontroles. Bij
lokale inname is de User-Agent bewust `null`, omdat geen request plaatsvindt; bij download
wordt de centrale `company-lookup/0.1` vastgelegd. Ruwe echte records blijven uitsluitend
in de lokale evidence en runartefacten; canonieke documentatie bevat alleen aggregaten.
