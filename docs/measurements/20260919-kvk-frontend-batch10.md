# KVK-frontend-Web-API — geïsoleerde batch van tien

- Datum: 2026-09-19
- Execution ID: `CH-2026-09-19-008`
- Status: `LIVE_MEASURED`; onafhankelijke eindreview `PASS`
- Lokale run-ID: `1789807660326325000_20260919T084740.326194Z_4bb0e1`
- Selectiemanifest SHA-256: `54c4ffa3f9aa00f8c4173dff396815820f774502fcea216f0cf4f74e26cfe1ca`
- Samenvatting SHA-256: `fe668a483e2701916210c8c38755d67bca525139b35839ddfcaa45133d8a9ac7`

## Afbakening en uitvoering

Uit de bestaande, hashgecontroleerde R6-sample van 500 zijn deterministisch tien
andere kandidaten dan de eerdere R8-pilot van 50 gekozen: twee per actieve
bronfamilie; zes met een directe geldige KVK-hint en vier zonder. Dit is een
capability-smoke, geen steekproefschatting van de 500 of kwalificatie voor bulk.

De lokaal bewaarde, onafhankelijk vóór uitvoering beoordeelde eenmalige runner deed
precies één GET voor elk van de tien namen op de door de frontend gebruikte publieke
route `https://web-api.kvk.nl/zoeken/v3/search`. Er was geen paginering, retry,
browserfallback, betaalde API of verzoek buiten deze tien. De User-Agent was
`company-lookup/0.1`, zonder persoonlijke verwijzing. De code dwong minimaal
2,5 seconden tussen requeststarts af; de kleinste tussenruimte tussen opgeslagen
responsemetadatabestanden was 2,318 seconden. Exacte requeststarttijden zijn in
de definitieve queryrecords niet behouden en zijn dus niet achteraf onafhankelijk
te reconstrueren. De providerlock en bestaande cooldown zijn gecontroleerd.

## Waargenomen uitkomst

| Terminale identiteitsuitkomst | Aantal |
|---|---:|
| Voorlopig `MATCHED`, exacte naam plus exact onafhankelijk bronveld | 3 |
| `NO_MATCH`, geen exacte naammatch in volledig resultaat | 3 |
| `AMBIGUOUS`, alleen exacte naam als identiteitsevidence | 4 |
| Technische fout of bronconflict | 0 |
| **Totaal** | **10** |

Tien unieke queryrecords en tien lokale ruwe responses sluiten op elkaar aan.
Alle tien HTTP-statussen waren 200 en alle eerste pagina's waren volgens
`numberOfHits` volledig; er was geen blokkade of rate-limit. De tien responsebestanden
zijn byte-exact tegen hun lokale SHA-256-metadata geverifieerd. Samen bevatten ze
30.601 bytes, maximaal 14.921 bytes per response. De geïsoleerde run eindigde in
`SMOKE_COMPLETE`; de eerdere R8-pilot is niet opnieuw gestart of herberekend.

Twee van de drie voorlopige matches kwamen uit kandidaten zonder initieel
KVK-nummer. Voor één match met directe bronhint was het gevonden nummer gelijk
aan die hint; er is geen discordante voorlopige match gevonden. De andere negen
gevallen bieden geen vergelijkbare directe-hint-plus-matchcombinatie. Geen match
is zonder aanvullende verificatie een definitieve ondernemingssleutel; rechtsvorm,
activiteit en de werkelijke capaciteit voor 500/10.000 blijven `UNKNOWN/NOT_TESTED`.

## Dispositie

Deze tien groene HTTP-responses tonen alleen dat de huidige publieke
frontendroute in deze kleine batch technisch bereikbaar was. Zij bewijzen geen
gebruiksrecht, schaalcapaciteit of volledige verificatiesemantiek. RD-001 en R7
blijven `PARKED`, R9/R10 blijven geblokkeerd. Er volgt geen automatische volgende
batch, 500-run, productieharvest of release.

Echte namen, KVK-nummers, volledige URLs met zoektermen en responsebytes blijven
uitsluitend in de genegeerde lokale runopslag; dit document bevat alleen aggregaten
en hashes.

De [onafhankelijke read-only review](../reviews/20260919T085100Z_ch-2026-09-19-008_review.md)
vond na de pre-live fixes geen resterende P0/P1/P2.
