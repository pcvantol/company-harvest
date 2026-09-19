# Begrensde identiteitsmatching naar KVK-nummer

R8 koppelt de reproduceerbare R6-pilotpool aan een KVK-nummer zonder een
besluit over routemigratie, providerbulk of volledige verificatie te activeren. De
opdracht is expliciet en wordt niet gestart door `run execute`.

## Beslisvolgorde

1. Controleer hashes en groottes van pilot, sample, R6-reviewqueue en R6-reviewrapport.
2. Eis een actuele, hashgebonden R6-review met status `PASS`.
3. Zoek eerst offline in de geregistreerde bronartefacten. Bind pad, kind, SHA-256 en
   grootte van de volledige actuele bronset aan journal, rapport en runtimeconfiguratie;
   een offline beslissing verwijst daarnaast naar exact artefact en bronrij.
4. De historische no-hint-pilot doet vanaf ADR-016 geen publieke naamzoeking
   meer. Zonder offline bronmatch wordt `NO_DIRECT_KVK_HINT` vastgelegd,
   zonder GET; de oude live-limiet is in dit pad niet operationeel.
5. Ken iedere kandidaat exact één terminale uitkomst toe.
6. Publiceer resultaten, queue en rapport als één transactionele outputset en maak een
   eerdere R8-review en latere stappen stale.

Een automatische match vereist een exact genormaliseerde naam én een onafhankelijk exact
bronveld: plaats of websitehost. Naam-only, domein-only en scores zijn nooit zelfstandig
matchbewijs. Meerdere sterke KVK-kandidaten worden `AMBIGUOUS`; conflicterende offline
bronnen worden `SOURCE_CONFLICT`. De hieronder beschreven publieke
naamzoekuitkomsten zijn historische pilotsemantiek; nieuwe no-hint-pilots
produceren geen dergelijke responses meer. Zonder direct bronnummer en zonder
offline match volgt een afgeronde technische uitkomst `NO_DIRECT_KVK_HINT`.

## Betekenis van velden

Een gekoppeld nummer krijgt `PROVISIONAL_*_IDENTITY_MATCH` en is nog geen definitieve
ondernemingssleutel. Rechtsvorm, status en plaats uit de frontend zijn bronobservaties en
blijven buiten de verificatiesemantiek. Een `NO_MATCH`, `AMBIGUOUS` of technische fout
verwijdert de kandidaat niet.

## Hervatten en blokkades

Het requestjournal bindt ieder resultaat aan kandidaatinhoud, bronfeatures, pilothash,
provider, nummer-only-querybeleid en de byte-exacte actuele bronartefactset. Alleen een exact passende
inhoudelijke terminale uitkomst wordt hergebruikt;
`FAILED` en `DEFERRED` worden bij hervatting opnieuw beoordeeld.
`NO_DIRECT_KVK_HINT` is een afgeronde offline beslissing en wordt bij
gelijkblijvende fingerprint hergebruikt. `--refresh` verwijdert uitsluitend
R8-journalregels. De providerlock blijft van kracht; de no-hint-pilot doet
geen live zoekactie. Historische blokkaderesultaten blijven lokaal bewaard.

## Handmatige review en thresholds

De reviewqueue is deterministisch verdeeld over bronfamilie en terminale uitkomst. Iedere
assessmentregel moet de SHA-256 van de actuele queue dragen. Geldige verdicts zijn
`CONFIRMED`, `FALSE_MATCH` en `UNCERTAIN`; ook reviewtijd is verplicht.

Alleen bij maximaal 5% technische fouten en nul false/uncertain reviews worden de vooraf
vastgelegde R9-formules toegepast:

- minimum matchrate: `max(0,10; floor(gemeten matchrate × 0,8, 2 decimalen))`;
- maximum ambigu-rate: `min(0,50; ceil(gemeten ambigu-rate + 0,10, 2 decimalen))`;
- technische foutgraad maximaal 0,05, false matches nul en closure 1,0.

Deze kwaliteitsuitkomst activeert R9 niet: R9 vereist daarnaast nog steeds expliciete
activatie en de nog open R7-productie- en gebruiksgates. R7 staat inmiddels
op `IN_PROGRESS`; de officiële betaalde API-migratie blijft afzonderlijk geparkeerd.
