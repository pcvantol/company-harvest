# R8-meting — begrensde KVK-nummermatchingpilot

- Datum: 2026-09-18
- Scope: 50 vooraf geselecteerde kandidaten zonder direct KVK-nummer
- Provider: huidige publieke KVK-frontendroute via `public-http`
- User-Agent: `company-lookup/0.1`
- Uitvoering: sequentieel, interval 2 seconden
- Lokale run-ID: `1789740162353845000_20260918T140242.353792Z_eb463e`
- Matchingrapport SHA-256: `cf0565755c261c67ca0f70f9754ecc6d55e08c345ca67d9fdd6f6887f3a38e6c`
- Reviewrapport SHA-256: `68701a92aeeddf95cdc34d90b4f3a4b7e3c951b95fa33799be6d7ab1d05b0aee`
- Actuele bronartefactfingerprint: `8ca9f7342d4e6a40d80b208fc960be5fb6bbf4affbbfb57504e8dc1ce8af0ef2`
- Privacy: namen, identifiers, responses en reviewregels uitsluitend onder genegeerde
  lokale runopslag

## Uitkomst

| Uitkomst | Aantal | Percentage |
|---|---:|---:|
| `MATCHED` | 15 | 30% |
| `NO_MATCH` | 28 | 56% |
| `AMBIGUOUS` | 6 | 12% |
| `SOURCE_CONFLICT` | 0 | 0% |
| `TECHNICAL_ERROR` | 1 | 2% |
| **Totaal** | **50** | **100%** |

De closure is 50/50. Alle 15 KVK-nummers zijn voorlopige identiteitsmatches op exacte
genormaliseerde naam plus exacte bronplaats. Geen naam-onlymatch is automatisch
geaccepteerd. Zes gevallen bleven ambigu: vier hadden alleen exactenaambewijs en twee
hadden meerdere KVK-nummers met dezelfde sterke velden. Alle kandidaten bleven behouden.

Per bronfamilie waren de voorlopige matches: fiscale erkenningen 11/16,
onderwijsregister 4/15, open kennisbank 0/4 en wereldwijd entiteitenregister 0/15. Deze
kleine gestratificeerde pilot is geen populatieschatting en vormt geen basis om een bron
te verwijderen.

## Techniek en capaciteit

- 50 live calls; geen rate-limit of toegangsblokkade.
- Doorlooptijd 125,049 seconden; 2,501 seconden per kandidaat.
- Response-evidence: 79.124 bytes.
- Eén netwerkfout bleef expliciet technisch en leidde niet tot een matchclaim.
- Een eerdere sandboxrun met 50 lokale DNS-fouten was technisch ongeldig, is door een
  netwerktoegankelijke refresh vervangen en blijft uitsluitend lokaal auditbaar als
  stale meetset.

## Review en thresholds

De deterministisch gestratificeerde queue bevatte 20 items uit vier bronfamilies en alle
aanwezige uitkomsttypen. Alle 20 zijn tegen de opgeslagen response en bronvelden
beoordeeld als `CONFIRMED`: nul `FALSE_MATCH`, nul `UNCERTAIN`. De review kostte 88,0
seconden, gemiddeld 4,4 seconden per item.

R8 krijgt `PASS` en `GO_R9_METRICS`. De vooraf gedeclareerde formules leveren:

- matchrate minimaal 24%;
- ambigu-rate maximaal 22%;
- technische foutgraad maximaal 5%;
- false matches nul;
- terminale closure 100%.

Dit is geen toestemming voor R9 of een 10.000-run. R9 blijft geblokkeerd zolang R7 niet
expliciet is geactiveerd en succesvol afgerond.

De volledige-run-audit is na R8 bewust niet groen: R8 maakt eerdere stap-5+-outputs
stale, terwijl de terminale downstreamkandidaatlaag pas na de geblokkeerde vervolgstappen
kan worden opgebouwd. De lokale audit meldt daarom stale oude rapporten en ontbrekende
terminale kandidaatartefacten. R8 zelf is op geregistreerde hashes, closure, review en de
repositoryqualitygate gecontroleerd; de run is nadrukkelijk niet releasegekwalificeerd.
