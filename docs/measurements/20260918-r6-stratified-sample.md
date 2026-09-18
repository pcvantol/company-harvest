# R6 — gestratificeerde bron- en dedupsample

Datum: 2026-09-18
Status: `PASS`
Scope: lokale kwaliteitsmeting op de bestaande vijf-bronnenrun; geen netwerk- of
KVK-frontendcalls

## Reproduceerbare definitie

- Volledige selectie-inputfingerprint: `8a551deb27ea4e44e09b8bc86f6ee558556dc78bfcca7e380ac3777b159f996c`;
  deze bindt bronhashes, catalogushash en de gebruikte bron→familie-indeling.
- Omvang: 500 bronrecords.
- Familieallocatie: gelijke gesorteerde round-robin met capaciteitsherverdeling.
- Identifierallocatie per familie: dezelfde methode voor `VALID_DIRECT` en
  `WITHOUT_DIRECT`.
- Selectie binnen stratum: laagste SHA-256 van de canoniek geserialiseerde volledige
  bronrij.
- Deduplicatie: dezelfde voorlopige exacte regels als de gewone kandidaatmerge.
- Review: alle merges/conflicten indien aanwezig, daarna gestratificeerde singles.
- R8-pool: 50 kandidaten zonder direct KVK, gelijk verdeeld over beschikbare families
  en geselecteerd met een stabiele kandidaathash.

## Gemeten verdeling

| Bronfamilie | Met direct KVK | Zonder direct KVK | Totaal |
|---|---:|---:|---:|
| fiscale-erkenningen | 0 | 113 | 113 |
| onderwijsregister | 57 | 56 | 113 |
| open-kennisbank | 46 | 4 | 50 |
| overheidsregister | 112 | 0 | 112 |
| wereldwijd-entiteitenregister | 84 | 28 | 112 |
| **Totaal** | **299** | **201** | **500** |

Wikidata had in de gemeten bronlaag slechts 50 records en bereikte daarmee zijn volledige
capaciteit; de overige 450 plaatsen zijn gelijkmatig over de vier grotere families
herverdeeld. Alle acht werkelijk beschikbare familie-/identifierstrata zijn opgenomen.

## Deduplicatie en closure

- 500 bronrecords leverden 500 unieke voorlopige kandidaten.
- Identieke merges: 0; duplicate ratio: 0,000.
- Conflictrecords: 0; conflict ratio: 0,000.
- Closure: 500 input = 500 decision-inputs + 0 conflictinputs; delta 0, `CLOSED`.

De nulmetingen betekenen dat de vooraf gestratificeerde sample geen dubbele of
conflicterende naam-/KVK-combinatie bevatte; zij betekenen niet dat de volledige
82.973-recordlaag geen duplicaten of conflicten bevat. R5 mat daarin één identieke merge
en 21 conflictrecords. De fixturetests van R6 bewijzen daarnaast expliciet de merge- en
conflictroutes.

## Handmatige review

De reviewqueue bevatte 25 `KEPT_SINGLE`-beslissingen uit alle vijf bronfamilies: 12 met
een geldig direct KVK-nummer en 13 zonder. Iedere beslissing had precies één bronrecord
en dus geen uitgevoerde merge. Alle 25 zijn inhoudelijk beoordeeld en `CONFIRMED`; nul
`FALSE_MERGE`, nul `UNCERTAIN`, closure `CLOSED`, eindstatus `PASS`. Enkele namen tonen
bronbias of discutabele bronclassificatie; dat is als bronkwaliteitsvraag onderscheiden
van de correcte beslissing om niet automatisch te mergen.

## R8-overdracht en resources

- De 50 lokale R8-pilotkandidaten hebben geen direct geldig KVK-nummer.
- Voor R8 zijn vooraf vastgelegd: terminale outcome-closure, matchrate per familie,
  ambiguous-, review- en technische-foutratio, seconden en evidencebytes per kandidaat.
- Thresholds worden pas na de R8-meting en review vastgesteld.
- Gemeten duur: 3,7 seconden; Python-piekallocatie circa 71,3 MB.
- Zes data-artefacten: circa 470 kB; evidencegroei: 0 bytes.
- De transactionele SQLite-allocatie bleef door bestaande paginacapaciteit 73.728 bytes;
  gemeten publicatiegroei 0.

Alle echte namen, identifiers, bronrijen, reviewnotities en pilotselecties blijven onder
genegeerde `.local/`-runopslag en zijn niet in Git opgenomen.
