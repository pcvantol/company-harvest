# ADR-020 — Productidentiteit Company Lookup

Status: aangenomen voor ongepubliceerde bronversie 4.0.0
(CH-2026-09-19-043).

## Context

De User-Agent heette al `company-lookup/0.1`, terwijl distributie, Python-
import en CLI nog de oude productnaam gebruikten. De eigenaar heeft een
volledige hernoeming gevraagd, inclusief de GitHub-repository. Een
distributie-/importnaamswijziging breekt bestaande installaties en scripts;
historische releasebestanden en auditbewijs zijn daarentegen feiten.

## Besluit

Vanaf 4.0.0 heten de projectdistributie en CLI `company-lookup`, de
Python-package `company_lookup`, de env-var `COMPANY_LOOKUP_DATA_DIR` en de
standaarddatamap `~/.local/share/company-lookup`. Installers, releasebouw,
CI en actuele handleidingen gebruiken dezelfde identiteit. Geen stille
alias voor de oude opdracht of import: meng beide distributies niet in één
venv. Gebruik voor een bestaande run expliciet de oude datamap via de
nieuwe env-var, `--data-dir` of `--run-dir`. De tool verplaatst, hernoemt of
herschrijft nooit een bestaande run.

De GitHub-repository wordt afzonderlijk via bevoegd beheer hernoemd naar
`pcvantol/company-lookup` zodra authenticatie en netwerk dit toestaan;
totdat dat is geverifieerd, blijft de oude remote gezaghebbend. De publieke
3.0.0-wheel, tags, releaseassets en historische bewijsdocumenten behouden
hun werkelijk gebruikte namen en byte-identiteit.

## Gevolgen en bewijs

De wijziging is MAJOR. Nieuwe offline naam-/configuratie-/CLI-tests, de
volledige per-bestand-coverageregel, wheel-/installatiesmoke en onafhankelijke
review zijn verplicht voordat de code als gekwalificeerd geldt. Een
repositoryrename of nieuwe release wordt nooit uit lokale code alleen
afgeleid. Bron-, KVK- en run-/outputschema's veranderen niet.
