# ADR-015 — Geen arbitraire exportafkap

Datum: 2026-09-19 · Status: **ACCEPTED** · Execution ID: CH-2026-09-19-032

## Context

De bestaande `--export-limit`/`export --limit` koos op een vaste hash van
het KVK-nummer de eerste N actieve bedrijven, zonder inhoudelijke score.
Pas na deze selectie werd de levering alfabetisch gesorteerd. De overige
actieve, al geverifieerde bedrijven gingen naar `companies_reserve.csv`.
Een doel van circa 10.000 is geen reden om bruikbare resultaten zo af te
kappen; de grens was voor de gebruiker niet als kwaliteitsselectie te
verdedigen.

## Besluit

Verwijder beide CLI-opties en de hashgebaseerde selectie. De export levert
alle actieve, geverifieerde bedrijven uit de gekozen KVK-scope, alfabetisch.
`--limit-kvk-check N` blijft bestaan als expliciete, runbreed gebonden grens
op hoeveel kandidaten de publieke KVK-route worden aangeboden. Bij een
begrensde proef blijft het resultaat `PARTIAL` ten opzichte van de volledige
pre-KVK-wachtrij als kandidaten niet zijn bevraagd.

Het bestaande outputsetschema en auditcontract behouden voorlopig
`companies_reserve.csv`, maar dit bestand is voor nieuwe exports leeg.
Manifest `selection_policy=ALL_ACTIVE` en `active_rows` maken de nieuwe
semantiek controleerbaar; de audit eist bij die policy dat de volledige
actieve lijst is geleverd en de reserve leeg is. Oude manifesten zonder
policy blijven volgens hun oorspronkelijke contract verifieerbaar.

Een oude onvoltooide E2E-run met een mogelijk bindende exportlimiet wordt
niet stil omgezet. Alleen als de oude limiet minstens zo groot was als de
vaste KVK-cohort kan de run zonder selectieverschil hervatten. Een al
geëxporteerde oude run kan worden geauditeerd zonder nieuwe export.

Vervolg CH-2026-09-19-035: [ADR-017](017-light-business-export.md) voegt
aan nieuwe exports een lichte zakelijke CSV/XLSX toe en verhoogt het
outputsetmanifest naar schema 2. De lege reserve en `ALL_ACTIVE`-semantiek
van dit besluit blijven gelijk.

Het verwijderen van publieke CLI-opties is incompatibel en vereist daarom
MAJOR-bronversie 3.0.0. Er is hiermee geen toestemming voor een volledige
live KVK-harvest of publicatie van een release gegeven. Een 100.000+-rijen
XLSX-export heeft nog geen schaalproef; de huidige XLSX-schrijver bouwt het
werkboek in geheugen op. De R9-productie-/schaalpoort blijft open.
