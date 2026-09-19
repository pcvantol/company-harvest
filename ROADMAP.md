# Company Harvest — canonieke roadmap

Statusdatum: 2026-09-18  
Roadmap-eigenaar: repository-eigenaar  
Status: actief  
Dit document is de canonieke bron voor prioriteit, volgorde, scope en uitstelbesluiten. Bij strijdigheid met losse handoffs, reviews of ideeënlijsten geldt deze roadmap, tenzij een later ADR of expliciet gebruikersbesluit haar wijzigt.

## 1. Productuitkomst

Het doel blijft een aantoonbaar bruikbare lijst van circa 10.000 unieke, actieve Nederlandse ondernemingen zonder bevestigde eenmanszaken, met reconcilieerbare herkomst en zonder fictieve aanvulling. Een technisch werkende pipeline of succesvolle packaging is daarvoor noodzakelijk, maar niet voldoende.

De eerstvolgende fase verschuift daarom van releaseceremonie naar drie meetbare productvragen:

1. Welke brede combinatie van goede, onafhankelijke bronnen levert voldoende unieke Nederlandse organisaties, en welke identificatievelden levert iedere bron werkelijk?
2. Hoe gedragen deduplicatie, identiteit, reviewqueues en opslag zich op representatieve samples?
3. Welke verificatieroute kan rechtsvorm en status aantoonbaar en verantwoord leveren voordat een schaalrun wordt toegestaan?

## 2. Vaststaande besluiten

### RD-001 — Officiële KVK-routemigratie geparkeerd; publieke frontend gecontroleerd hervatbaar

Een migratie naar officiële KVK-API's wordt nu niet ontworpen, gebouwd of aangevraagd. De eigenaar heeft op 2026-09-19 de bestaande publieke frontend-Web-API expliciet aangewezen voor een beheerste, hervatbare doorloop met minimaal twee seconden tussen verzoekstarts. ADR-008 specificeert de technische begrenzing; het is geen API-key-integratie.

Voor de nog niet beantwoorde gebruiks- en productvragen:

- blijft de huidige `public-http`/`public-browser`-implementatie bestaan;
- blijven ontwikkeltests klein en sequentieel; een volledige doorloop is een expliciete afzonderlijke CLI-actie, niet automatisch tijdens ontwikkeling, CI of installatie;
- geldt de frontendroute nog niet als bewezen route voor 10.000 geverifieerde actieve ondernemingen;
- worden Playwright, cooldowns en fallbacklogica nog niet verwijderd;
- wordt geen aanname gedaan dat Zoeken rechtsvorm en ondernemingsstatus volledig levert.

R7 is door de eigenaar technisch geactiveerd voor deze frontendroute; externe gebruiksvoorwaarden, veldsemantiek en productkwaliteit blijven open gates.

### RD-002 — User-Agent blijft voorlopig `company-lookup/0.1`

Alle uitgaande bron- en KVK-HTTP-requests gebruiken:

```text
company-lookup/0.1
```

Er wordt geen persoonlijke GitHub-URL, gebruikersnaam, lokaal pad of contactadres in de User-Agent opgenomen. Een wijziging vereist een nieuw expliciet besluit. Er komt geen afzonderlijke patchrelease uitsluitend voor deze stringwijziging.

### RD-003 — Outcome-gates gaan vóór een volgende release

De volgende publieke release bundelt een betekenisvolle productverbetering, bijvoorbeeld een nieuwe gevalideerde bronadapter plus meetrapportage. Het GitHub Release-object `v0.1.0` en de bijbehorende assets zijn op expliciet eigenaarsbesluit verwijderd; de historische tag blijft staan. Die tag wordt niet verplaatst en het oude manifest wordt niet hergebruikt.

### RD-004 — Geen automatische productieharvest

Samples worden begrensd en vooraf gespecificeerd. Een 10.000-run wordt pas na de schaal- en gebruikspoorten in R9 door de eigenaar gestart; nooit automatisch tijdens ontwikkeling, CI, installatie of review.
De expliciet gekozen hervatbare pre-KVK-frontendcontrole uit ADR-008 is
een afzonderlijke verificatieactie, geen automatische productieharvest of
kwalificatie van de uiteindelijke levering.

### RD-005 — Gefocuste engineeringgates

Op expliciet besluit van de repository-eigenaar bestaat de actieve CI-matrix uit Python
3.14 op macOS en Windows. Ubuntu en Python 3.11–3.13 zijn geen doorlopende CI-gates
meer en gelden voor nieuwe wijzigingen als `NOT_TESTED`. De per-file coveragegate,
assetprovenance en onafhankelijke release-review blijven ongewijzigd. Een toekomstige
release beschrijft ondersteuning afzonderlijk van de werkelijk uitgevoerde CI-matrix.

### RD-006 — Breed verzamelen, gecontroleerd verkleinen

De bronfase optimaliseert eerst op brede, herleidbare dekking (`recall`) en pas later op definitieve selectie (`precision`). Het is beter om kandidaten met onzekerheden traceerbaar te bewaren dan ze vroeg weg te filteren en later niet meer te kunnen herstellen.

Daarom:

- worden meerdere onafhankelijke bronfamilies vroeg onderzocht en, na een positieve feasibility, verzameld;
- is een direct KVK-/registratienummer een waardevol routerings- en kwaliteitskenmerk, maar geen voorwaarde om een goede bron vroeg op te nemen;
- blijven originele bronrecords, ontbrekende velden en onzekerheden behouden;
- worden kandidaten zonder registratienummer vroeg in een afzonderlijke kandidaatlaag opgenomen en mogen zij binnen het normale proces naar een KVK-nummer worden gematcht of verrijkt;
- vinden rechtsvorm-, status- en definitieve identiteitsfilters pas plaats wanneer de benodigde verificatie aantoonbaar beschikbaar is;
- worden commerciële geschiktheid, sector, werknemersaantal of lage bronfrequentie niet als vroege uitsluitingsreden gebruikt;
- betekent “breed” niet onbegrensd of willekeurig: iedere bron moet herleidbaar, relevant, technisch beheersbaar en volgens vastgelegde voorwaarden toegankelijk zijn.

De architectuur onderscheidt voortaan drie lagen: **ruwe brondekking**, **voorlopige kandidaten** en **geverifieerde levering**. Verkleining is een expliciete, meetbare overgang tussen lagen en nooit stil dataverlies.

### RD-007 — KVK-nummermatching is toegestaan

Het ontbreken van een KVK-nummer in een bronrecord maakt die bron of kandidaat niet waardeloos. Matching en verrijking naar een KVK-nummer zijn toegestaan als normale, meetbare verwerkingsstap. Dit omvat exacte koppeling via andere herleidbare bronnen en begrensde zoek-/reviewroutes volgens het bestaande providercontract.

Daarbij gelden de volgende grenzen:

- het oorspronkelijke record blijft altijd behouden;
- een match krijgt methode, bronbewijs, score/reden en terminale uitkomst;
- een matchscore is prioriteringsinformatie en nooit zelfstandig beslissend bewijs;
- naam-, domein- of fuzzy-overeenkomst alleen is nooit voldoende voor een automatische definitieve merge;
- een gevonden KVK-nummer blijft voorlopig totdat het volgens ADR-002 en het bestaande providercontract is geverifieerd; alleen een geverifieerd KVK-nummer is een definitieve ondernemingssleutel;
- meerdere mogelijke KVK-nummers of conflicterende naam-, bron- of plaatsevidence eindigen als `AMBIGUOUS` of `SOURCE_CONFLICT`, zonder canonieke merge;
- `no-match` en `ambigu` blijven bruikbare kandidaten en worden niet verwijderd;
- KVK-nummermatching bewijst niet automatisch rechtsvorm, status of activiteit;
- de huidige pre-KVK-wachtrij mag op expliciet eigenaarsbesluit via de begrensde, hervatbare publieke frontendroute worden gecontroleerd; migratie naar een andere route blijft geparkeerd.

### RD-008 — Vierbronnenvoorbereiding zonder Wikidata

Op 2026-09-19 heeft de eigenaar voor de zelfstandige tool de geselecteerde
pre-KVK-invoer teruggebracht tot IND, GLEIF, ANBI en DUO. Wikidata is geen
vereiste of automatische download meer voor deze workflow. De historische
vijfbronnenmeting en R5-portfoliobesluiten blijven als toenmalig bewijs
ongewijzigd; de nieuwe master claimt uitsluitend sluiting over de vier
geselecteerde bronnen. De tool downloadt/hergebruikt deze vier bronnen,
controleert full-scope evidence en dedupliceert ze vóór KVK.

De eigenaar vroeg koppeling aan de door de frontend gebruikte publieke
Web-API. Naast de oorspronkelijke batch van maximaal tien is na expliciet
eigenaarsbesluit een afzonderlijke hervatbare langlopende CLI-opdracht
beschikbaar (ADR-008). De publieke route en geslaagde kleine batches bewijzen
niet vanzelf externe toestemming, schaalgeschiktheid of productkwaliteit;
de definitieve 10.000-export blijft onder R9 en kwaliteitscontrole vallen.

### RD-009 — Expliciete filter vóór de huidige KVK-wachtrij

Op 2026-09-19 heeft de eigenaar besloten de vierbronnenmaster breed en
verliesvrij te behouden, maar de *huidige* publieke KVK-batch uitsluitend
gevoed te laten worden door een afzonderlijk gefilterde lijst. Kandidaten
zonder directe KVK-hint, ANBI-/DUO-instellingen, conflicten en herkenbare
scholen, holdings/beheermaatschappijen, stichtingen/verenigingen, banken,
pensioen-/beleggingsfondsen, religieuze organisaties en politieke partijen
worden vóór die batch uitgesloten. Iedere uitsluiting blijft met regelversie,
reden, bronidentiteit en masterverwijzing lokaal herleidbaar. Dit verandert
RD-006's brede bronverzameling niet; het beperkt alleen deze KVK-wachtrij.
RD-007's toegestane matching zonder initieel nummer blijft voor andere,
afzonderlijk gekozen trajecten bestaan, maar wordt in deze route niet gestart.
De filter is heuristisch en kan na expliciet besluit herzien worden.

## 3. Statuslegenda

| Status | Betekenis |
|---|---|
| `DONE` | Afgerond en aantoonbaar geverifieerd |
| `ACTIVE` | Huidig increment; werk mag worden uitgevoerd |
| `NEXT` | Eerstvolgende uitvoerbare increment |
| `PLANNED` | Gespecificeerd, maar afhankelijk van eerdere uitkomsten |
| `PARKED` | Bewust uitgesteld; niet uitvoeren zonder expliciet besluit |
| `BLOCKED` | Kan niet verantwoord verder zonder externe keuze of toegang |

## 4. Roadmapoverzicht

| Increment | Status | Uitkomst | Afhankelijk van |
|---|---|---|---|
| R0 | `DONE` | Roadmap, besluiten en prioriteiten canoniek vastgelegd en onafhankelijk gereviewd | — |
| R1 | `DONE` | Meetcontract en rijkere broncatalogus | R0 |
| R2 | `DONE` | Bestaande IND/Wikidata-capabilities werkelijk gemeten | R1 |
| R3 | `DONE` | GLEIF-feasibility met gereviewd `GO`-besluit | R1 |
| R4 | `DONE` | Eerste nieuwe bronadapter en herbruikbare brede-innamebasis | R2, R3 en een `GO` |
| R5 | `DONE` | Brede bronportfolio uit meerdere onafhankelijke bronfamilies | feasibility na R1; adapterimplementatie na R4 |
| R6 | `DONE` | Gestratificeerde bron-/dedupsample van 500 uit de brede kandidaatlaag | R4 en voldoende R5-breedte |
| R7 | `IN_PROGRESS` | Publieke frontendroute technisch hervatbaar; voorwaarden, schaal, velden en resultaten nog te beoordelen | expliciete activatie eigenaar op 2026-09-19 |
| R8 | `DONE` | Begrensde KVK-nummermatchingpilot voor kandidaten zonder registratienummer | R6 |
| R9 | `BLOCKED` | Volledige sample- en schaalvalidatie, daarna eigenaar-go/no-go voor 10.000 | R6, R7, R8 |
| R10 | `DONE` (toolrelease) | Door eigenaar gevraagde toolrelease 1.0.0 met herdownloadkwalificatie; R7/R9 blijven open | relevante toolincrements + distributiegates |

De volgorde is outcome-gedreven. Een later increment mag niet worden gestart omdat het technisch aantrekkelijk is; de afhankelijkheden en exitcriteria moeten eerst zijn gehaald.

## 5. R0 — Canonieke koersvastlegging

Status: `DONE` — onafhankelijke review `PASS` vastgelegd.

### Scope

- Claude-review vertalen naar toetsbare increments.
- KVK-migratie expliciet parkeren.
- `company-lookup/0.1` als voorlopig vast besluit registreren.
- Geen aparte `v0.1.1` voor alleen de User-Agent plannen.
- Roadmap vanuit de repository- en documentatie-index vindbaar maken.

### Exitcriteria

- `ROADMAP.md` bestaat en is vanuit `README.md` en `docs/README.md` gelinkt.
- ADR-001 verwijst naar het actuele parkeerbesluit.
- De uitvoering is in het promptregister opgenomen.
- Een onafhankelijke read-only review is met status `PASS` vastgelegd.

## 6. R1 — Meetcontract en broncatalogus 2.0

Status: `DONE` — verticale slice geïmplementeerd en onafhankelijk gereviewd met `PASS`.

### Doel

Maak productopbrengst meetbaar voordat nieuwe scrapers of releases worden gebouwd.

### Werk

Breid het bronmodel minimaal uit met:

- `has_registration_number`;
- `registration_number_type`;
- `provides_legal_form`;
- `provides_status`;
- `access_mode` (`bulk`, `api`, `download`, `html`, `manual-import`);
- voorwaarden-/licentieverwijzing;
- actualiteits- of refreshinformatie indien bekend;
- live meetstatus en gemeten aantal;
- geschatte overlap alleen wanneer daadwerkelijk gemeten.
- `source_family`, `inclusion_reason` en kwaliteits-/herkomststatus;
- de kandidaatlaag waarin het record zich bevindt (`raw`, `candidate`, `verified`).

Voeg aan runrapportage minimaal toe:

- ruwe records per bron;
- records met syntactisch geldig KVK-nummer;
- records zonder direct registratienummer;
- unieke kandidaten vóór en na deduplicatie;
- identieke merges, conflicten en reviewgevallen;
- ontbrekende rechtsvorm/status per bron;
- brondiversiteit, overlap en concentratie van kandidaten per onafhankelijke bronfamilie;
- doorlooptijd, piekgeheugen en SQLite-/evidencegroei;
- volledige count-closure tussen iedere stap.

### Tests

- Catalogusschema- en migratietests.
- Rapportmetriek met lege, dubbele en conflicterende fixtures.
- Geen verlies van records door ontbrekende optionele meetvelden.
- Bestaande run-schema's blijven leesbaar of worden expliciet geweigerd met hersteladvies.

### Exitcriteria

- Iedere bron heeft een expliciet registratie-ID-profiel.
- Een synthetische sample levert een volledig outcome-rapport met sluitende aantallen.
- Er zijn nog geen verzonnen succesdrempels; thresholds worden pas na R2/R3 met data vastgesteld.

### Gerealiseerd bewijs

- Broncatalogusschema 2 bevat alle afgesproken profiel-, toegang-, actualiteits-, meet-, herkomst- en laagvelden.
- Oude catalogusartefacten worden bij lezen verliesvrij genormaliseerd en als schema 2 vastgelegd.
- Handmatige bronnen zonder KVK-kolom blijven als kandidaten behouden; ontbrekende en ongeldige nummers zijn afzonderlijk meetbaar.
- `report` schrijft naast Markdown een machineleesbaar `outcome_report.json` met bron-, identifier-, dedup-, conflict-, review-, diversiteits-, closure- en resourcecijfers.
- `company-lookup/0.1` staat in nieuwe runmetadata en in ieder outcome-/runrapport.
- Lege, dubbele, conflicterende en identifierloze fixtures bewijzen de meetsemantiek; succesdrempels blijven bewust unset tot R2/R3.

## 7. R2 — Bestaande bronnen werkelijk meten

Status: `DONE` — live gemeten en onafhankelijk gereviewd met `PASS`.

### Doel

Vervang aannames over IND en Wikidata door actuele, reproduceerbare capabilitymetingen.

### Werk

- Voer een begrensde IND-meting uit en registreer werkelijk aantal, geldige KVK-hints, duplicaten en parserafwijzingen.
- Voer een begrensde live Wikidata-meting uit; de bestaande offline tests alleen zijn onvoldoende.
- Meet overlap tussen IND en Wikidata op KVK-nummer.
- Leg actualiteit, voorwaarden, rate-limitobservaties en evidence vast.
- Classificeer rechtsvorm/status uit deze bronnen uitsluitend als brondata, niet automatisch als KVK-gevalideerd filterveld.

### Grenzen

- Geen bulk-KVK-verrijking.
- Geen claim dat twee bronnen het target dekken.
- Geen volledige Wikidata-download wanneer een kleinere meting de capabilityvraag beantwoordt.

### Exitcriteria

- Beide bronnen hebben `LIVE_MEASURED`, `BLOCKED` of een concrete foutstatus.
- Werkelijke aantallen en overlap zijn aantoonbaar.
- Bijdrage, overlap en bias van beide bronnen binnen de brede kandidaatlaag zijn datagedreven vastgelegd.

### Gerealiseerd bewijs

- `sources measure` schrijft ook bij bronblokkade of transportfout een terminaal JSON- en Markdownrapport.
- IND is volledig gemeten op 12.980 ruwe records en 12.977 unieke geldige KVK-nummers; de bronpagina droeg peildatum 3 september 2026.
- Wikidata is via officiële property `P3220` begrensd gemeten op 200 records, waarvan 195 unieke geldige achtcijferige KVK-nummers en vijf verliesvrij bewaarde ongeldige waarden.
- De begrensde vergelijking vond 12 gedeelde nummers; bias, voorwaarden, actualiteit, request-/rate-limitobservaties en niet-extrapoleerbaarheid staan in [`docs/measurements/20260918-r2-source-capability.md`](docs/measurements/20260918-r2-source-capability.md).
- Beide adapters leveren in deze slice geen rechtsvorm of status; er wordt geen geschiktheid voor een 10.000-run geclaimd.

## 8. R3 — GLEIF-feasibility, nog geen productieadapter

Status: `DONE` — feasibilitybesluit `GO`, onafhankelijk gereviewd met `PASS`.

### Doel

Onderzoek de reviewhypothese dat GLEIF in één bulkbron Nederlandse organisaties met bruikbare registratienummers, status en rechtsvorm kan leveren.

### Werk

- Verifieer primaire documentatie, downloadroute, licentie/voorwaarden, updatefrequentie en bestandsformaat.
- Filter een lokale sample op Nederlandse entiteiten.
- Meet hoeveel nationale registratienummers exact als achtcijferig KVK-nummer valideerbaar zijn.
- Meet duplicaten, ontbrekende identifiers, legal-formvelden en statusvelden.
- Controleer betekenis en peildatum van GLEIF-status/rechtsvorm; behandel die niet stil als KVK-verificatie.
- Schat downloadgrootte, verwerkingstijd, geheugen en opslag.

### Go/no-go-criteria

Een `GO` vereist minimaal:

- juridisch/operationeel toelaatbare toegang volgens vastgelegde voorwaarden;
- reproduceerbare bulkdownload;
- betekenisvolle Nederlandse opbrengst;
- aantoonbare mapping naar KVK-nummers voor een substantieel deel van de sample;
- beheersbare verwerking zonder volledige dataset in geheugen;
- duidelijk provenance- en refreshmodel.

Bij `NO_GO` wordt alleen het bewijsdocument toegevoegd; er wordt geen halfwerkende adapter gebouwd.

### Besluit en gerealiseerd bewijs

`GO` voor een streaming GLEIF Level 1 Golden Copy-adapter in R4. De officiële route is
gratis, CC0, driemaal daags bijgewerkt en reproduceerbaar als CSV-ZIP. De live index
rapporteerde 197.093 Nederlandse records. Een begrensde, statusgestratificeerde sample
van 100 `ACTIVE` en 100 `INACTIVE` records bevatte 200 unieke achtcijferige
`registeredAs`-waarden, alle gekoppeld aan registratieautoriteit `RA000463` (KVK).
Een volledige streaming kwalificatiescan van de actuele CSV-ZIP vond 194.884 unieke
geldige KVK-nummers onder autoriteitscode `RA000463` en complete legal-form- en statusvelden voor alle 197.093 Nederlandse
records. De 504.128.840-byte ZIP (4.987.509.988 bytes ongecomprimeerd) werd in 47,49
seconden verwerkt met 24.150.016 bytes piek-RSS en 2.805.760 bytes tijdelijke SQLite.

De steekproef is doelbewust niet representatief voor statusverhoudingen. GLEIF
`entity.status` en LEI-`registration.status` blijven bronsemantiek en bewijzen niet zonder
meer actuele KVK-activiteit. De gemeten grootte-, geheugen- en opslagprofielen sturen de
gates die in R4 worden geïmplementeerd. Volledig bewijs en hashes staan in
[`docs/measurements/20260918-r3-gleif-feasibility.md`](docs/measurements/20260918-r3-gleif-feasibility.md).

## 9. R4 — Eerste nieuwe bronadapter en brede-innamebasis

Status: `DONE` — verticale slice geïmplementeerd, live begrensd gemeten en onafhankelijk gereviewd met `PASS`.

### Doel

Voeg de eerste nieuwe bron met aantoonbare kwaliteit en opbrengst toe en maak de innamebasis geschikt om daarna meerdere onafhankelijke bronfamilies naast elkaar te verwerken. Een direct registratienummer heeft voorkeur wanneer kwaliteit en opbrengst vergelijkbaar zijn, maar is geen algemene toelatingseis voor de brede kandidaatlaag.

### Werk

- Streaming of chunked verwerking.
- Begrensde download, redirect- en groottelogica passend bij bulkbestanden.
- Lokale immutable evidence met bronversie, tijd en hash.
- Deterministische filtering op Nederlandse entiteiten.
- Expliciete identifier-validatie en rejected-uitvoer.
- Het ongewijzigde ruwe record en iedere afwijzingsreden blijven bewaard.
- Een overigens relevante organisatie met ontbrekend of syntactisch ongeldig registratienummer blijft kandidaat/reviewgeval; alleen het identifierpad wordt afgewezen.
- Bronstatus/rechtsvorm als afzonderlijke bronvelden bewaren.
- Records zonder registratienummer bewaren in de kandidaatlaag met expliciete matchbehoefte; niet vroeg verwijderen.
- Downstream-invalidatie en resume/hergebruik testen.

### Exitcriteria

- Adapter slaagt offline met realistische fixtures en live met een begrensde capabilityrun.
- Alle aantallen sluiten.
- Geen bronveld wordt stil als KVK-gevalideerd gepromoveerd.
- Opbrengst en overlap zijn in het outcome-rapport zichtbaar.

### Gerealiseerd bewijs

- `sources gleif` verwerkt de officiële Level 1 Golden Copy CSV-ZIP streaming en kan
  zowel zelf begrensd downloaden als een reeds gekwalificeerde lokale snapshot innemen.
- HTTPS-host, redirects, downloadgrootte, ZIP-structuur, compressieratio, ongecomprimeerde
  grootte en vrije schijfruimte hebben expliciete gates; tijdelijke bestanden worden bij
  fouten verwijderd en HTTP-blokkades veroorzaken geen fallback.
- De evidencekopie is immutable geregistreerd met SHA-256. Verplichte kolommen worden
  gevalideerd; onbekende extra kolommen blijven toegestaan.
- Nederlandse records zonder KVK-nummer, met ongeldig nummer of met een andere
  registratieautoriteit blijven kandidaat. De originele registratie blijft behouden en
  het identifierprobleem staat afzonderlijk in rejected-uitvoer met het ruwe bronrecord.
- GLEIF-rechtsvorm en beide statusvelden blijven expliciet brondata en worden nergens als
  actuele KVK-verificatie gepromoveerd.
- De begrensde capability-run op 200 Nederlandse records sloot beide adapterpartities:
  200 kandidaten, 172 geldige unieke KVK-hints, 28 identifier-reviewgevallen en geen
  ontbrekende legal-form- of statusvelden. De gecombineerde outcome-run telde 450
  records uit drie bronfamilies en maakte ook nuloverlap expliciet zichtbaar; één geldig
  KVK-nummer overlapte tussen GLEIF en de Wikidata-sample.
- Offline regressies dekken verwerking, hergebruik, refresh/invalidatie, CLI, download,
  User-Agent, schema-, ruimte-, ZIP- en groottefouten. Het nieuwe adapterbestand behaalt
  283/294 statements coverage (96,26%).

Het volledige aggregaatbewijs staat in
[`docs/measurements/20260918-r4-gleif-adapter.md`](docs/measurements/20260918-r4-gleif-adapter.md).

## 10. R5 — Brede bronportfolio

Status: `DONE` op 2026-09-18. Zes kandidaatbronnen zijn volledig gekwalificeerd; ANBI
en DUO zijn als afzonderlijke verticale adapters toegevoegd. De actieve meetportfolio
bevat vijf bronnen uit vijf bronfamilies. TenderNed is `GO_NEXT`; TED, DNB en AFM zijn
gemotiveerd `PARKED`. Bewijs:
[`docs/measurements/20260918-r5-source-portfolio.md`](docs/measurements/20260918-r5-source-portfolio.md).

Latere uitvoer CH-2026-09-19-009 probeerde deze vijf actieve bronnen
eenmalig volledig naar één pre-KVK-lijst te brengen. Vier bronnen zijn
full-scope ingenomen; Wikidata stopte op HTTP 429. De afzonderlijke
[vierbronnenpreview](docs/measurements/20260919-pre-kvk-source-snapshot.md)
is voor KVK geblokkeerd. Dit verandert R5's portfolioacceptatie niet en
activeert R7 niet; een vijfbronnenmaster is nog niet bewezen.

### Doel

Verzamel een brede set goede bronnen voordat definitieve verkleining begint. Selecteer op herleidbaarheid, relevante Nederlandse organisatie-evidence, voorwaarden, opbrengst en onderhoudbaarheid. Identifierkwaliteit bepaalt het latere verwerkingspad, niet of een bron bij voorbaat wordt genegeerd.

### Onderzoeksvolgorde

De externe review noemt onder meer TED, TenderNed, leveranciersbestanden, sectorregisters, SBB, brancheverenigingen en exposantenlijsten. Hun identifierbeschikbaarheid, volume en geschiktheid zijn hypotheses, geen vastgestelde feiten. Daarom geldt:

1. inventariseer per kandidaat welke identifiers werkelijk beschikbaar zijn;
2. bewijs dit met primaire documentatie en een begrensde sample;
3. geef bronnen met een betrouwbaar direct registratienummer binnen een implementatiegolf voorrang wanneer overige kwaliteit vergelijkbaar is;
4. implementeer adapters beheerst één voor één, maar blijf feasibility en portfolio-opbouw over meerdere onafhankelijke bronfamilies sturen;
5. neem ook bewezen goede bronnen zonder registratienummer vroeg op in de kandidaatlaag en routeer ze naar de toegestane matching-/reviewstap.

Feasibilitykaarten en bronselectie mogen vanaf R1 parallel worden voorbereid. Implementatie van de tweede en volgende adapters start pas nadat R4 de gedeelde brede-innamebasis heeft bewezen.

### Verplichte feasibilitykaart per kandidaatbron

- eigenaar en primaire URL;
- toegangstype en updatefrequentie;
- voorwaarden, licentie, robots/crawlbeperkingen en vereiste attributie;
- wel/geen registratienummer;
- verwachte bias;
- gemeten sampleopbrengst;
- overlap met bestaande bronnen;
- parsercomplexiteit en onderhoudsrisico;
- persoonsgegevens- en gebruiksrisico;
- `GO`, `NO_GO` of `PARKED`.

### Footer-crawl

Een gerichte crawl naar KVK-nummers in websites wordt als afzonderlijke kandidaat behandeld, niet automatisch gebouwd. Voor een `GO` zijn eerst vereist:

- een legitieme, begrensde seedset;
- beoordeling van voorwaarden en robotsregels;
- lage requestfrequentie, hostgrenzen en maximale omvang;
- bewijs dat een gevonden nummer aan de juiste organisatie kan worden gekoppeld;
- rejected/reviewpad voor conflicten;
- expliciete eigenaarstoestemming voor live uitvoering.

Common Crawl of een internetbrede `.nl`-crawl wordt niet zonder afzonderlijk ontwerp- en gebruiksbesluit gestart.

### Exitcriteria

- Minimaal zes kandidaatbronnen uit meerdere bronfamilies hebben een volledige feasibilitykaart.
- De actieve portfolio bevat als richtinggevend minimum vijf bruikbare bronnen van minimaal drie onafhankelijke eigenaren of bronfamilies, tenzij meetbewijs een expliciet roadmapbesluit voor een andere grens onderbouwt.
- Adapters zijn beheerst één voor één geïmplementeerd, maar de portfolio als geheel is op dekking en diversiteit gestuurd.
- Zowel records mét als zonder direct registratienummer blijven herleidbaar in de kandidaatlaag.
- Selectie en eventuele afwijzing per bron zijn gemotiveerd met gemeten opbrengst, overlap, voorwaarden en risico.

## 11. R6 — Bron- en dedupsample van 500

Status: `DONE` op 2026-09-18 na onafhankelijke review `PASS`. Een deterministische
500-recordsample uit vijf
bronfamilies is volledig gesloten, een gestratificeerde review van 25 beslissingen is
`PASS` en een reproduceerbare 50-recordselectie plus metriekcontract voor R8 zijn
vastgelegd. Bewijs:
[`docs/measurements/20260918-r6-stratified-sample.md`](docs/measurements/20260918-r6-stratified-sample.md).

### Doel

Test schaalgedrag en datakwaliteit op een doorsnede van de brede kandidaatlaag zonder de geparkeerde KVK-beslissing te omzeilen. De sample is een kwaliteitsinstrument en geen plafond op hoeveel brondata wordt verzameld.

### Werk

- Bouw een deterministische, gestratificeerde sample van 500 bronrecords uit alle actieve bronfamilies, inclusief records met en zonder direct registratienummer.
- Voer verzamelen, normaliseren, voorlopige deduplicatie en conflictdetectie uit.
- Meet per bron en totaal:
  - geldige directe registratienummers;
  - duplicate ratio;
  - identieke merges;
  - conflicten en reviewqueue;
  - aantal unieke kandidaten;
  - rechtsvorm-/statusdekking als brondata;
  - tijd, geheugen, database- en evidencegroei.
- Laat een handmatig gestratificeerde steekproef van mergebeslissingen beoordelen voordat thresholds worden vastgezet.

### Grenzen

- Geen 500 KVK-frontendcalls zolang R7 geparkeerd is.
- KVK-nummers mogen binnen de sample wel uit directe bronvelden en exacte, deterministische offline koppeling tussen reeds verzamelde bronnen worden aangevuld.
- R6 doet geen publieke-frontendmatching; het vormt de gestratificeerde pilotselectie voor R8.
- Geen bronstatus of GLEIF-status presenteren als KVK-gevalideerde ondernemingsstatus.
- Geen releaseclaim dat het einddoel is bewezen.
- Geen vroege verwijdering omdat een record nog geen KVK-nummer, rechtsvorm of status heeft; het blijft kandidaat of reviewgeval.

### Exitcriteria

- 100% count-closure en nul stil verloren records.
- Geen onverklaarde false merge in de beoordeelde steekproef.
- Meetrapport bevat reproduceerbare sampledefinitie.
- De meting levert bron-/deduplicatiebaselines, een reproduceerbare R8-pilotselectie en vooraf vastgelegde R8-metrics op.
- Match-, review- en capaciteitsthresholds voor R9 worden pas na de R8-pilot vastgesteld.

## 12. R7 — KVK-verificatiebesluit

Status: `IN_PROGRESS` voor de publieke frontendroute; officiële API-migratie blijft `PARKED`.

De eigenaar heeft de publieke frontendroute met minimaal twee seconden interval expliciet geactiveerd. ADR-008 beschrijft de hervatbare uitvoering. De onderstaande product- en gebruiksvragen blijven open; technische beschikbaarheid alleen sluit R7 niet af.

### Te beantwoorden vragen

- Welke officiële en publieke routes zijn op dat moment beschikbaar en toegestaan?
- Welke route levert naam, KVK-nummer, Nederlandse vestiging, rechtsvorm en ondernemingsstatus met bewezen semantiek?
- Is een afzonderlijk basis-/vestigingsprofiel nodig?
- Wat zijn actuele kosten, limieten, voorwaarden en secretbeheervereisten?
- Welke bestaande frontendprovidercode kan na succesvolle migratie veilig vervallen?

### Gefaseerde aanpak wanneer geactiveerd

1. Alleen primaire KVK-documentatie en testomgeving onderzoeken.
2. Providercontract en kostenmodel documenteren; nog geen productiekey committen of loggen.
3. Sample van maximaal 200 records uitvoeren met vooraf bepaalde metrics.
4. Rechtsvorm-, status-, match- en unresolved-dekking meten.
5. Go/no-go en nieuwe ADR vastleggen.
6. Pas bij `GO` provider implementeren en oude code gecontroleerd uitfaseren.

### Open poorten voor productkwaliteit en gebruik

De eigenaar heeft de beheerste publieke frontenddoorloop expliciet geactiveerd,
maar daarmee zijn externe gebruiksvoorwaarden, schaalgedrag en de semantiek van
rechtsvorm/status nog niet gekwalificeerd. Een volledige verificatierun wordt
niet automatisch door installatie, CI of ontwikkeling gestart. R9 en een
definitieve 10.000-levering blijven afhankelijk van gemeten kwaliteit en een
afzonderlijk go/no-go-besluit.

De [afzonderlijke tien-GET-capability-smoke van 2026-09-19](docs/measurements/20260919-kvk-frontend-batch10.md)
is als kleine regressiemeting beoordeeld, niet als activering van R7 of vrijgave
voor de 500-recordbulk.

## 13. R8 — Begrensde KVK-nummermatchingpilot

Status: `DONE`; implementatie, echte 50-recordmeting, hashgebonden review en
onafhankelijke finale review zijn afgerond met status `PASS`. R7 was destijds
`PARKED` en was voor deze begrensde identiteitsmatching niet vereist.

De externe review noemt onder andere SBB, brancheverenigingen, exposantenlijsten en lokale bedrijventerreinlijsten. Zulke bronnen kunnen waardevolle organisaties leveren zonder direct KVK-nummer. R8 meet daarom expliciet hoe goed hun kandidaten naar een KVK-nummer kunnen worden verrijkt. Het doel is identiteitskoppeling, niet het omzeilen van het geparkeerde besluit over providerbulk, rechtsvorm of ondernemingsstatus.

### Werk

- Selecteer vooraf een kleine, reproduceerbare en gestratificeerde pilot uit meerdere bronfamilies.
- Gebruik eerst exacte koppeling via herleidbare bronvelden en bestaande kandidaten; gebruik de huidige publieke frontend alleen klein, sequentieel en binnen het bestaande providercontract.
- Meet match, no-match, ambigu, review en technische terminale uitkomsten.
- Registreer eventueel aangetroffen rechtsvorm/status alleen als bronobservatie; promoveer die niet zonder bewezen verificatiesemantiek.
- Bewaar ieder origineel bronrecord en iedere matchbeslissing; een mislukte match verwijdert de kandidaat niet.
- Automatiseer geen merge op alleen naam, domein of fuzzy score.
- Behandel een score uitsluitend als reviewprioriteit, nooit als zelfstandig matchbewijs.
- Routeer meerdere mogelijke KVK-nummers of conflicterende naam-, bron- of plaatsevidence naar `AMBIGUOUS` of `SOURCE_CONFLICT`; maak daaruit geen canonieke merge.
- Leg per bron matchopbrengst, reviewkosten en stopcriteria vast.

### Exitcriteria

- Iedere pilotkandidaat heeft exact één reconcilieerbare terminale uitkomst.
- Elk toegevoegd KVK-nummer heeft herleidbaar matchbewijs en een expliciete matchmethode.
- Een gevonden KVK-nummer blijft voorlopig totdat het volgens ADR-002 en het bestaande providercontract is geverifieerd; alleen daarna mag het de definitieve ondernemingssleutel zijn.
- Rechtsvorm en status blijven `UNKNOWN` tenzij zij via een afzonderlijk bewezen pad zijn gevalideerd.
- Handmatige controle van een gestratificeerde steekproef toont geen onverklaarde false merge.
- De pilot levert vooraf vast te leggen thresholds, reviewkosten en capaciteitsevidence voor R9.
- Een `no-match` of `ambigu` verlaagt de gemeten dekking, maar verwijdert de kandidaat niet en maakt de bron niet onbruikbaar.

## 14. R9 — Volledige sample- en schaalvalidatie

Status: `BLOCKED`, onvoorwaardelijk afhankelijk van R6, een geslaagde R8-pilot en een expliciet geactiveerd en succesvol afgerond R7-besluit. R6 en R8 zijn gereed; R7 is voor de publieke frontendroute technisch `IN_PROGRESS`, maar nog niet succesvol afgerond. Daarom is R9 nog niet uitvoerbaar.

### Fase A — volledige sample van 500

Meet minimaal:

- match rate;
- no-match, ambigu en technische foutpercentages;
- reviewqueuegrootte;
- dedup-ratio vóór en na verificatie;
- unieke canonieke bedrijven;
- percentage met bewezen rechtsvorm;
- percentage met bewezen ondernemingsstatus;
- verdeling actief/inactief/unknown;
- verdeling eenmanszaak/non-sole/unknown;
- tijd, throughput, retries, opslag en evidencegroei;
- volledige closure van kandidaten naar iedere terminale uitkomst.

Thresholds worden vastgesteld op basis van R6-R8-data en handmatige kwaliteitscontrole. Ze worden niet achteraf aangepast om een slechte run groen te maken.

### Fase B — schaalstappen

Na een geslaagde sample:

1. synthetische of lokale 2.000-record belastingstest;
2. synthetische of lokale 10.000-record belastingstest;
3. pas daarna een eigenaar-go/no-go voor een echte 10.000-run.

### Exitcriteria

- Outcome-thresholds gehaald.
- Geen niet-lineaire fout in tijd, geheugen of SQLitegedrag.
- Externe routecapaciteit en voorwaarden aantoonbaar passend.
- Operationele en juridische checklist door eigenaar geaccepteerd.

## 15. R10 — Volgende release

Status: `DONE` voor de expliciet gevraagde toolrelease 1.0.0;
[releasebewijs](docs/releases/20260919-v1.0.0-evidence.md). R7 en R9 blijven
respectievelijk `IN_PROGRESS` en `BLOCKED`.

Er komt geen standalone `v0.1.1` uitsluitend voor de User-Agent. De eigenaar
heeft na de betekenisvolle vierbronnen-, filter- en hervatbare KVK-tooling een
release 1.0.0 gevraagd. Dat versienummer kwalificeert de distributie van de
tool, **niet** een voltooide KVK-bulkdoorloop of levering van 10.000 actieve
bedrijven. R7/R9 blijven afzonderlijke product-/gebruiksgates.

### Verplichte gates

- relevante roadmap-exitcriteria gehaald;
- outcome-rapport aanwezig;
- volledige lokale qualitygate;
- toepasselijke CI-matrix groen;
- onafhankelijke read-only review van exacte commit en distributiebytes;
- nieuw commitgebonden manifest;
- nieuwe tag; bestaande tags nooit verplaatsen;
- anonieme herdownload, hashcontrole en verse installatiekwalificatie;
- release notes maken expliciet onderscheid tussen offline, live bewezen, parked en niet getest.

## 16. Parallelle werkstroom — voorwaarden, privacy en gebruik

Deze werkstroom blokkeert geen offline ontwerp, maar wel operationeel gebruik wanneer open punten materieel zijn.

Per bron en beoogd gebruik moet worden vastgelegd:

- voorwaarden/licentie en attributie;
- toegestane download-/crawlwijze;
- bewaartermijn en verwijder-/refreshstrategie;
- aanwezigheid van persoonsgegevens;
- beoogd gebruik van de uiteindelijke lijst;
- organisatorische beoordeling van AVG, direct-marketing- en belregels;
- wie eigenaar is van het finale gebruiksbesluit.

De repository doet geen juridische garantie. Bij twijfel is beoordeling door een bevoegde privacy-/juridische verantwoordelijke nodig vóór operationeel gebruik.

## 17. Bewust uitgesteld

De volgende onderwerpen zijn lager geprioriteerd totdat bronopbrengst en verificatie zijn bewezen:

- orphan-outputdirectory automatisch herstellen;
- packagingceremonie verder optimaliseren;
- opnieuw publiceren uitsluitend voor documentatie of User-Agent;
- publieke/private repositorystrategie wijzigen;
- internetbrede footer-crawl;
- volledige 10.000-bedrijvenproductierun.

## 18. Roadmapwijzigingen

Een roadmapwijziging vermeldt minimaal:

- datum en aanleiding;
- gewijzigd besluit of increment;
- effect op afhankelijkheden en exitcriteria;
- eventuele nieuwe ADR;
- wie de wijziging expliciet heeft geautoriseerd.

Losse reviews en handoffs zijn input, geen automatische roadmapwijziging. Vooral R7 mag niet impliciet worden geactiveerd door technisch onderzoek of een implementatievoorstel.

### Wijzigingslog

- **2026-09-19 — publieke frontendroute hervatbaar:** de eigenaar activeerde
  expliciet een beheerste doorloop via de bestaande frontend-Web-API op
  minimaal twee seconden per verzoekstart. ADR-008 en CH-2026-09-19-012
  leggen checkpointing en stopvoorwaarden vast. R7 is `IN_PROGRESS`;
  gebruiks-, schaal- en productgates blijven open, R9 blijft `BLOCKED`.
- **2026-09-19 — zelfstandige vierbronnenworkflow:** op expliciete vervolgvraag
  vallen Wikidata-download en -vereiste buiten de nieuwe pre-KVK-master.
  IND/GLEIF/ANBI/DUO worden door de tool zelf ingenomen en verliesvrij
  samengebracht; de lokale master sloot 292.666→289.916. Alleen kleine,
  expliciete KVK-Web-API-batches zijn geïmplementeerd. R7-bulkverificatie en
  downstream-export blijven `PARKED`/`BLOCKED` onder RD-001/004/008.
- **2026-09-18 — R8 afgerond:** de byte-exact aan pilot en bronartefactset gebonden
  50-recordmatchingpilot sloot met 15 voorlopige matches, 28 no-match, 6 ambigu, nul
  bronconflicten en 1 technische fout. De hashgebonden review bevestigde 20/20
  beslissingen zonder false/uncertain; onafhankelijke review is `PASS`. R8 is `DONE`,
  R7 blijft `PARKED` en R9 daarom `BLOCKED`.
- **2026-09-18 — R6 afgerond:** de vijf-bronnenlaag is deterministisch gestratificeerd
  tot 500 records, volledig gededupliceerd en gesloten. Alle 25 handmatig beoordeelde
  beslissingen zijn bevestigd; de 50-record-R8-pilotpool en het vooraf bepaalde
  metriekcontract zijn vastgelegd. De onafhankelijke review is `PASS`; R8 is `NEXT` en
  R7 blijft `PARKED`.
- **2026-09-18 — R5 afgerond:** ANBI en DUO zijn als expliciete, streaming bulkadapters
  toegevoegd; zes bronnen zijn met primaire documentatie en gemeten samples beoordeeld.
  De actieve kandidaatlaag telt vijf onafhankelijke bronfamilies. R6 is geactiveerd;
  R7 blijft `PARKED`.
- **2026-09-18 — R4 afgerond:** de streaming GLEIF-adapter, brede-innamecontracten,
  begrensde capability-run, expliciete bronpaaroverlap en onafhankelijke review zijn
  afgerond. R5 is de eerstvolgende uitvoerbare increment; R7 blijft `PARKED`.
- **2026-09-18 — GitHub Release `v0.1.0` verwijderd:** op expliciet besluit van de repository-eigenaar zijn het release-object en de vijf assets verwijderd. De Git-tag, broncommit en historische kwalificatie-evidence zijn behouden. Op dat moment was er geen publieke release; een volgende release moest opnieuw alle toepasselijke gates doorlopen.
- **2026-09-18 — CI-matrix gericht verkleind:** op expliciet besluit van de repository-eigenaar is RD-005 gewijzigd. Doorlopende CI valideert voortaan uitsluitend Python 3.14 op macOS en Windows; Ubuntu en Python 3.11–3.13 zijn voor nieuwe wijzigingen `NOT_TESTED`. De overige kwaliteits- en releasegates blijven staan.
- **2026-09-18 — breedte vóór verkleining:** op expliciet besluit van de repository-eigenaar is RD-006 toegevoegd. R4-R6 en R8-R9 zijn aangepast zodat meerdere goede bronfamilies vroeg worden verzameld, ook zonder direct registratienummer. De aanvankelijke koppeling van externe matching aan R7 is later op dezelfde datum vervangen door RD-007.
- **2026-09-18 — KVK-nummermatching toegestaan:** op expliciet besluit van de repository-eigenaar is RD-007 toegevoegd. Kandidaten zonder initieel KVK-nummer mogen regulier worden gematcht en verrijkt; R8 vereist daarom niet langer R7. Alleen providerbulk, routemigratie en volledige rechtsvorm-/statusverificatie blijven onder RD-001/R7 geparkeerd.
- **2026-09-19 — toolrelease `v1.0.0` gepubliceerd:** na groene exacte-commit-CI op macOS/Windows, onafhankelijke bron-/assetreview, byte-identieke anonieme herdownload en verse installatie. R10-toolrelease is `DONE`; R7/R9 blijven open. Zie het [releasebewijs](docs/releases/20260919-v1.0.0-evidence.md).
- **2026-09-19 — eigenaarsverzoek nieuwste wheel, `v2.0.0` gepubliceerd:**
  de geïntegreerde E2E-tool en auditfix zijn na onafhankelijke SemVer-review
  als MAJOR uitgebracht, omdat Python 3.11–3.13 niet langer worden
  ondersteund. Exacte-commit-CI op macOS/Windows, assetscan, anonieme
  byte-identieke herdownload en een verse installatie slaagden. Dit is een
  toolrelease, geen vrijgave of bewijs van volledige live KVK-bulkverwerking;
  R7/R9-productgates blijven open. Zie het
  [releasebewijs](docs/releases/20260919-v2.0.0-evidence.md).
- **2026-09-19 — oude releases/tags onder 2.0 ingetrokken:** op expliciet
  eigenaarsverzoek zijn uitsluitend de `v1.0.0`-GitHub Release met vijf
  assets en de remote/lokale tag verwijderd. `v0.1.0` was al weg;
  `v2.0.0`, broncommits en historische bewijsdocumenten blijven behouden.
  Nieuwe installaties gebruiken alleen de publieke v2.0.0-wheel. R7/R9
  blijven ongewijzigd; zie CH-2026-09-19-029.
