# Externe reviewinput — Claude-review van handoff

Status: ongetoetste externe input, letterlijk bewaard.  
Deze tekst is geen canoniek besluit en claims zijn niet automatisch als feit overgenomen. De geautoriseerde koers staat in [`ROADMAP.md`](../../../ROADMAP.md).

---

Grondig gelezen. Hieronder mijn review. Ik begin met de twee bevindingen die naar mijn mening de grootste impact hebben, daarna de rest.

---

## 1. Algemene beoordeling

De engineering-kwaliteit is hoog: idempotentie, invalidatie, evidence, hashes, partitie-closure, 12/12 CI-matrix. Dat is serieus werk en het fundament is goed.

Maar er zit een scheefgroei in: **de machinerie is af, het product niet.** De tool heeft op dit moment één record end-to-end verwerkt, uit een catalogus van twee bronnen, waarvan er één (Wikidata) nooit live gedraaid heeft. De opdracht was ~10.000 records. Er is dus een volledige release-, review- en auditcyclus doorlopen rond een pipeline waarvan de kerneigenschap — schaal — ongetest is.

De handoff is daar eerlijk over (§7 "Eerlijke lacune", §12 "bewust geen productieharvest"), wat ik waardeer. Maar de voorgestelde volgende actie in §14 is een patchrelease om een User-Agent-string te wijzigen. Dat is een prioriteitsinversie: je gaat een tweede publieke release met volledige review-cyclus uitvoeren voor een cosmetische header, terwijl de tool zijn hoofdtaak nog nooit heeft gedaan.

---

## 2. De KVK-route: dit kan legitiem, en het is vrijwel gratis

Dit is mijn belangrijkste bevinding. De hele `public-http`/`public-browser`-architectuur — frontend-`profileId`, cooldowns, retries, browserfallback, schemadriftdetectie — bestaat om te vermijden wat je voor een paar euro per maand gewoon kunt afnemen.

De officiële KVK-API's:

- Je hebt een abonnement nodig van €6,20 per maand, en betaalt daarnaast per bevraging: Zoeken €0, Basisprofiel €0,02, Vestigingsprofiel €0,02, Naamgeving €0,02.
- Je mag tot 300.000 bevragingen per maand doen, met maximaal 100 per seconde.
- Testen kan gratis via SwaggerUI met testdata of met een test-API-key in je eigen software.

Je stelde dat "die gasten niet willen betalen voor een dataset". Dat argument geldt hier niet: de Zoeken-API kost €0 per query en het abonnement is €6,20/maand. Voor 10k lookups betaal je dus letterlijk zes euro. Basisprofiel voor alle 10k records is €200 eenmalig.

Wat dit oplost in één klap:
- Geen ongedocumenteerd endpoint, geen `profileId`-afhankelijkheid, geen versieloos responseschema.
- Geen cooldownstate, geen 429-afhandeling, geen browserfallback, geen Playwright-dependency, geen schemadrift-contracttest (jouw Prioriteit 2 verdwijnt volledig).
- 100 qps in plaats van voorzichtig gedoseerde scraping. Je harvest van 10k draait in minuten.
- Je `public-browser`-provider, de `auto`-fallback en een flink deel van je retry/cooldown-logica kunnen weg. Dat is netto minder code, niet meer.

Ik zou dit als eerste doen, vóór alles wat in §14 en §15 staat. De architectuur wordt er simpeler van en het verwijdert de enige echt fragiele afhankelijkheid in het systeem.

Kanttekening bij de huidige route: de handoff kwalificeert netjes dat dit "een door de publieke frontend gebruikte route" is en geen ondersteunde API. Dat klopt, maar het betekent ook dat je op productieschaal geautomatiseerd verkeer stuurt naar een endpoint dat daar niet voor bedoeld is, via een publiek gedistribueerde wheel die anderen hetzelfde laat doen. Dat is een reëel risico voor KVK én voor jullie continuïteit, en het is onnodig geworden zodra je weet wat het alternatief kost.

---

## 3. De User-Agent-wijziging

Ik wil dit expliciet benoemen omdat het in combinatie met het vorige punt anders leest dan bedoeld.

De handoff vermeldt dat de oude UA `company-harvest/0.1` geen GitHub-URL, gebruikersnaam of lokaal pad bevatte, maar "op verzoek" toch is vervangen. De regressietests controleren nu expliciet dat de string geen `github` bevat. Het netto-effect is een minder identificeerbare client die een ongedocumenteerd endpoint aanroept.

Als het doel privacy was (geen persoonlijke gebruikersnaam of pad in outbound headers), is dat volledig legitiem, en dat was met de oude string al geregeld. Als het doel was om minder herleidbaar te zijn richting KVK, gaat dat de verkeerde kant op: bij scraping is een UA die je identificeert plus een contactadres juist de norm, niet iets om te verbergen. Ik zou aanraden:

```
company-lookup/0.1 (+contact@jullie-domein.nl)
```

Met een officiële API-key verdwijnt deze hele discussie trouwens, want dan identificeer je je via de key en is de UA niet meer relevant.

---

## 4. Technisch risico: het eenmanszaak- en actief-filter is niet bewezen

Dit is het risico dat mij het meest zorgen baart in de huidige opzet, en het is met N=1 niet zichtbaar geworden.

Je harde eisen zijn: **actief** en **geen eenmanszaak**. Beide vereisen rechtsvorm- en statusinformatie. De KVK-zoekroute (zowel de frontend-route als de officiële Zoeken-API) levert primair naam, KVK-nummer, adres en vestigingstype — niet noodzakelijk de rechtsvorm. Rechtsvorm en status zitten in het **Basisprofiel**, niet in Zoeken.

Je §12 rapporteert `legale-vormpartities [1, 0, 0]` en `statuspartities [1, 0, 0]` op één record. Dat vertelt je niets over of de velden gevuld worden; het vertelt je alleen dat er één record in bucket 1 viel. §6 stelt terecht "onbekende rechtsvorm of status wordt niet geraden" — maar als het zoekresultaat die velden structureel niet bevat, betekent die regel dat straks je hele dataset in de unknown-bucket belandt.

**Concreet: draai morgen een sample van 200 records door de volledige matchstap en tel hoeveel er een niet-lege rechtsvorm én status hebben.** Als dat percentage laag is, heb je een tweede call per record nodig (Basisprofiel, €0,02 → €200 voor 10k) en verandert je kostenmodel en je pipeline-vorm. Dit wil je weten vóór je bronnen gaat uitbreiden, niet erna.

---

## 5. Validatie op N=1

Gerelateerd, maar breder. Een run met één IND-record, één kandidaat, één match, nul unresolved bewijst de *plumbing*, niet het *systeem*. Alles wat pas bij volume ontstaat is ongetest:

- Matchkwaliteit en de verdeling over accept/review/no-match.
- Dedupgedrag, blocking-performance, false merges.
- Naar hoeveel canonieke bedrijven 10k kandidaten daadwerkelijk collapsen.
- Geheugen- en SQLite-gedrag bij 10k+ records met evidence per record.
- Hoeveel records door "voldoende bewijs van Nederlandse relatie" (§6) heenkomen — die regel is nu vaag en zal bij volume of te streng of te los blijken.

Ik zou een **sample-run van 500 records** als kwaliteitspoort invoeren vóór elke release, met harde metrics: match rate, review-queue-omvang, dedup-ratio, percentage bruikbare rechtsvorm/status. Dat zegt meer over releasegereedheid dan 12 CI-jobs op zes Python-versies.

---

## 6. Brondekking: dit is je echte openstaande werk

Twee bronnen, waarvan IND een niche-register is en Wikidata vrijwillig samengesteld. Realistische opbrengst: IND-register enkele duizenden erkende referenten, Wikidata met `P3821` waarschijnlijk in de lage duizenden en flink overlappend. Je komt zo niet in de buurt van 10k unieke, actieve, niet-eenmanszaken.

Twee opmerkingen over je bronarchitectuur voordat ik de lijst geef:

**Sorteer bronnen op of ze een KVK-nummer meeleveren.** IND en Wikidata doen dat, en dat is precies waarom ze makkelijk waren. Bronnen mét KVK-nummer slaan je hele fuzzy-matchprobleem over: je valideert alleen nog. Bronnen zonder KVK-nummer kosten je een matchstap met een review-queue. Prioriteer de eerste categorie.

**Waarschuwing zodat je er geen tijd in steekt:** de KVK Handelsregister Open Dataset lijkt op het antwoord, maar is het niet. De HVDS bevat geen persoonsgegevens, en als gevolg daarvan ontbreken juist de naam van de onderneming en het KVK-nummer; van het vestigingsadres zijn alleen de eerste twee cijfers van de postcode opgenomen. Daarnaast bevat die dataset alleen BV's en NV's. Bruikbaar voor statistiek, waardeloos als leadlijst.

### Bronnen met KVK-nummer of registratienummer (hoogste prioriteit)

| Bron | Wat je krijgt | Opmerking |
|---|---|---|
| **GLEIF LEI-bulkdownload** | Naam, status (ACTIVE/INACTIVE), rechtsvorm-ELF-code, registratienummer bij nationale autoriteit | Gratis dagelijkse volledige dump, wereldwijd, filterbaar op NL. Voor NL-entiteiten is het registratienummer doorgaans het KVK-nummer. Verifieer dat op een sample, maar dit kan in één download duizenden gevalideerde records opleveren — inclusief rechtsvorm en status, precies je twee filtervelden |
| **Common Crawl / gerichte .nl-crawl op KVK-nummer in footer** | Domein + KVK-nummer | Nederlandse sites zetten hun KVK-nummer standaard in de footer, op de contactpagina of in de algemene voorwaarden. Regex op `KvK` + 8 cijfers geeft je een directe koppeling zonder enige naammatching. Naar mijn inschatting je hoogste opbrengst per uur werk |
| **TED / EU-aanbestedingen open data** | Winnende partijen incl. nationaal registratienummer | Gratis bulk, gestructureerd |
| **TenderNed gunningen** | Gegunde partijen | NL-specifiek |

### Bronnen zonder KVK-nummer (matchstap nodig)

| Bron | Volume | Kwaliteit |
|---|---|---|
| **SBB register erkende leerbedrijven** | Zeer groot (ordegrootte honderdduizenden) | Publiek doorzoekbaar, actuele erkenning = actief bedrijf. Groot genoeg om in je eentje je target te halen, maar bevat ook veel kleine ondernemers |
| **Brancheverenigingen**: NLdigital, FME, Koninklijke Metaalunie, Techniek Nederland, Bouwend Nederland | Elk honderden tot duizenden | Ledenlijsten vaak platte HTML. Lidmaatschap ≈ geen eenmanszaak |
| **Exposantenlijsten** RAI, Jaarbeurs, vakbeurzen | Honderden per beurs, stapelt snel | Schoon, en exposeren vereist budget → grotere bedrijven |
| **Rijksoverheid inkoopuitgaven / leveranciersbestanden** (data.overheid.nl) | Duizenden | Publieke CSV's, leveranciersnamen + bedragen |
| **Sectorregisters**: AFM, DNB, en vergelijkbare toezichtsregisters | Honderden tot duizenden per register | Zeer schoon, gevalideerd, maar sectorspecifiek |
| **Techleap / Dealroom NL, Silicon Canals, FD Gazellen, Deloitte Fast 50** | Honderden | Klein maar hoge kwaliteit en triviaal te parsen |
| **Gemeentelijke bedrijventerrein- en parkmanagementsites** | Honderden per gemeente | Saai werk, maar schoon en zeer NL-specifiek |

Mijn advies voor de volgorde: **GLEIF eerst** (één download, levert direct rechtsvorm en status), **dan de KVK-nummer-uit-footer-crawl** (grootste hefboom, omzeilt matching), **dan SBB en brancheverenigingen** voor volume. Met die vier zit je ruim boven 10k.

Registreer per bron wat §15 al voorstelt — voorwaarden, bias, actualiteit, aantallen — en voeg toe: **levert deze bron een KVK-nummer, ja/nee**. Dat veld bepaalt je hele verwerkingspad.

---

## 7. Procesverbeteringen

**Snoei de ceremonie.** Een twaalfvoudige CI-matrix (drie OS'en × Python 3.11–3.14), onafhankelijke review-cycli per release, distributiemanifesten met byte-vergelijking en publieke wheels — voor een interne lead-generatietool met één gebruiker. Die investering betaalt zich niet terug en vertraagt juist het werk dat wél waarde heeft. Ik zou terugbrengen naar Linux + de Python-versie die je draait, eventueel één extra. macOS/Windows × vier versies kun je missen tot er een tweede gebruiker is.

**Heroverweeg publieke distributie.** Een publieke GitHub-release van een tool die een ongedocumenteerd KVK-endpoint aanroept, nodigt anderen uit hetzelfde te doen. Met de officiële API verdwijnt dat bezwaar. Maar vraag jezelf ook af waarom dit een publiek pakket moet zijn: als het een intern hulpmiddel is, scheelt een private repo je de volledige release-, hash- en manifestmachinerie.

**Vervang release-gates door outcome-gates.** "31 tests passed, Ruff passed, mypy passed" zegt niets over of de tool bruikbare leads produceert. Voeg de sample-run uit §5 toe als harde poort.

**Sla v0.1.1 over, of bundel hem.** Als de UA-wijziging publiek moet, laat hem meeliften op een release die ook daadwerkelijk iets toevoegt. Een aparte review-cyclus voor een header-string is niet proportioneel. De aanwijzing in §14 om tag `v0.1.0` niet te wijzigen en niet het oude manifest te hergebruiken klopt en moet je aanhouden — dat deel is prima.

**Restrisico orphan-directory (§8):** terecht als niet-blokkerend gemarkeerd. Laat staan tot na de brondekking.

---

## 8. Voorgestelde volgorde

1. **Vraag een KVK API-key aan** (€6,20/mnd, Zoeken gratis). Test eerst met de gratis testomgeving.
2. **Meet op 200 records of rechtsvorm en status daadwerkelijk gevuld worden** uit Zoeken. Zo niet: bouw de Basisprofiel-call in en herbereken de kosten.
3. **Vervang `public-http`/`public-browser` door één officiële provider.** Verwijder cooldown-, fallback- en schemadriftlogica. Je codebase krimpt.
4. **GLEIF-adapter** — snelste weg naar duizenden gevalideerde records met rechtsvorm en status.
5. **KVK-nummer-uit-footer-crawl** — de grootste hefboom, en hij omzeilt je matchprobleem volledig.
6. **Sample-run van 500** met harde metrics op match rate, review-queue en dedup-ratio. Pas hierna weet je of je pipeline klopt.
7. **SBB, brancheverenigingen, exposantenlijsten** tot je boven de 10k zit.
8. Pas daarna: releases, CI-onderhoud, orphan-recovery.

---

## Slot

De fundering is degelijk gebouwd en daar zou ik niets aan afdoen. Het probleem is dat er veel energie in de *verpakking* is gegaan (releases, manifesten, reviews, UA-strings) en weinig in de twee dingen die het product bepalen: **genoeg bronnen** en **een KVK-route die op 10k schaalt**. Dat tweede blijkt bij navraag een kwestie van zes euro per maand te zijn, wat een aanzienlijk deel van de meest complexe code in het project overbodig maakt.

Eén ding dat ik eerder noemde en nog steeds relevant is: laat de klant vóór het bellen even naar AVG en het bel-me-niet-regime voor zakelijke contacten kijken, en naar de voorwaarden van de bronnen die je scrapet (de CC BY 4.0-licentie op KVK-open data is bijvoorbeeld expliciet). Ik ben geen jurist, maar dat wil je geregeld hebben vóór de lijst de telefoon op gaat, niet erna.

Wil je dat ik een van deze punten uitwerk — bijvoorbeeld de migratie naar de officiële KVK-provider, of een concrete adapter-opzet voor de GLEIF- en footer-crawlbronnen?
