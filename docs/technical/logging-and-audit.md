# Logging en audit

Iedere run schrijft `execution.log` en `events.jsonl` met UTC-tijd, level, event, run/recordcontext en geschoonde fouten. Credentialachtige waarden worden geredigeerd. Volledige providerresponses staan alleen onder lokaal bewijs.

Artefacten krijgen SHA-256, grootte, stap, type en status in SQLite. `audit verify` controleert bestaan/grootte/hash. `audit trace` zoekt een KVK-nummer door tabulaire snapshots en toont bron→stap→output. Dit detecteert wijzigingen, maar beschermt niet tegen iemand die database en bestanden met dezelfde rechten herschrijft.

