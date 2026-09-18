# R5-bronportfolio — feasibility en twee adapters

Datum: 2026-09-18
Status: `PASS`
User-Agent bij HTTP-bronrequests: `company-lookup/0.1`

## Besluit in één oogopslag

Zes kandidaatbronnen uit vier aanvullende bronfamilies zijn aan hetzelfde
feasibilitycontract getoetst. ANBI en DUO zijn als expliciete bulkadapters gebouwd en
volledig lokaal gemeten. TenderNed krijgt `GO` als volgende adapterkandidaat, maar niet
als impliciete download. TED, DNB en AFM blijven `PARKED` totdat de genoemde
semantiek-, toegang-, licentie- of privacyvragen zijn opgelost.

| Bron | Familie | Besluit | Direct KVK | Gemeten opbrengst |
|---|---|---|---|---:|
| ANBI Open Data | fiscale erkenningen | `GO_IMPLEMENTED` | nee | 54.922 kandidaten |
| DUO Basisgegevens instellingen | onderwijs | `GO_IMPLEMENTED` | soms | 27.601 huidige kandidaten |
| TenderNed H1 2026 | aanbestedingen | `GO_NEXT` | KVK-achtig veld; semantiek nog bevestigen | 8.373 leverancierregels |
| TED Search API | EU-aanbestedingen | `PARKED` | soms | 100 notices gesampled |
| DNB Openbaar Register | financieel toezicht | `PARKED` | nog niet vastgesteld | bulkmeting terminaal `BLOCKED` (HTTP 403) |
| AFM financieel dienstverleners | financieel toezicht | `PARKED` | nee in CSV | 17.698 regels |

Dit is technische en datakwaliteitsfeasibility, geen juridisch advies. Ruwe snapshots en
records staan uitsluitend in `.local/` en zijn niet gepubliceerd.

## Feasibilitykaart 1 — ANBI Open Data

- **Eigenaar en primaire URL:** Belastingdienst; [open-datapagina](https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/themaoverstijgend/brochures_en_publicaties/open_data_anbi) en [ZIP](https://download.belastingdienst.nl/data/anbi/anbi.zip).
- **Toegang en actualiteit:** publieke ZIP, volgens de eigenaar iedere dinsdag ververst.
- **Voorwaarden/licentie/attributie:** de eigenaar noemt onbeperkt gebruik, geen verplichte bronvermelding en CC0. `robots.txt` blokkeerde `/data/anbi/` niet.
- **Registratienummer:** `fiscaalNummer` is negen cijfers en wordt nadrukkelijk niet als KVK gepromoveerd. Het ruwe nummer blijft behouden; iedere organisatie blijft kandidaat met `MISSING` direct KVK.
- **Bias:** alleen erkende ANBI's; vestigingsland is niet als afzonderlijk veld beschikbaar en de lijst kan buitenlandse instellingen bevatten.
- **Gemeten opbrengst:** volledige snapshot: 54.922 records/kandidaten; 54.917 met fiscaal nummer en 5 zonder; 0 ontbrekende namen. Exacte count-closure op alle drie partities.
- **Overlap:** geen direct-KVK-overlap meetbaar. In de gecombineerde dedupmeting ontstond geen automatische cross-source merge; naamoverlap alleen is bewust onvoldoende bewijs.
- **Parser/onderhoud:** streaming XML uit een begrensde ZIP; lage tot middelmatige complexiteit. XML-entiteitsuitbreiding en externe verwijzingen worden door `defusedxml` geweigerd.
- **Persoons-/gebruiksrisico:** namen en fiscale identifiers blijven lokaal in evidence/review. Geen ruwe data in Git of distributie.
- **Besluit:** `GO_IMPLEMENTED` voor lokale kandidaatopbouw; fiscale nummers blijven niet-KVK en ANBI levert geen expliciete actuele status.

Evidence SHA-256: `c3390b8d893e7c9c6bf888a39eb4b9c480b6ab09c68ba2d2ed8c5558fea48513`;
ZIP 2.575.261 bytes; XML 18.163.230 bytes.

## Feasibilitykaart 2 — DUO Basisgegevens instellingen

- **Eigenaar en primaire URL:** Dienst Uitvoering Onderwijs; [bronpagina en ZIP](https://duo.nl/open_onderwijsdata/onderwijs-algemeen/basisgegevens/basisgegevens-instellingen.jsp).
- **Toegang en actualiteit:** publieke ZIP met organisaties, relaties en overgangen; wekelijkse publicatie. Gemeten peil-/publicatiedatum 14 september 2026.
- **Voorwaarden/licentie/attributie:** gepubliceerd onder Open Onderwijsdata; de bekeken bronpagina en proclaimer noemen geen concrete hergebruiklicentie. Daarom geen redistributie van de snapshot en `NEEDS_LEGAL_REVIEW` vóór externe datapublicatie. `robots.txt` bevatte voor `User-agent: *` geen `Disallow`.
- **Registratienummer:** `KVK_NR` is aanwezig maar vaak leeg. Geldige achtcijferige waarden worden hint; ontbrekende en ongeldige waarden blijven kandidaat/review.
- **Bias:** onderwijsinstellingen én organisatorische eenheden; geen algemene bedrijvenpopulatie. De mutatiehistorie bevat veel niet-huidige regels.
- **Gemeten opbrengst:** 137.084 regels; 27.601 met `CODE_STAND_RECORD=A` als huidige scope; 109.483 historische/transitieregels zichtbaar afgewezen. Onder de huidige regels: 2.284 geldige KVK-records, 2.280 unieke nummers, 25.309 ontbrekend en 8 ongeldig; 27.601 kandidaten. Alle partities sluiten exact.
- **Overlap:** in de actieve portfolio 2 exacte KVK-overlappen met de begrensde Wikidata-sample, 0 met IND/GLEIF/ANBI. Met TenderNed werden daarnaast 30 exacte achtcijferige overlaps gemeten.
- **Parser/onderhoud:** streaming UTF-8 CSV uit een begrensde ZIP; middelmatige complexiteit door historie en bronstatus.
- **Persoons-/gebruiksrisico:** de adapter leest alleen organisatievelden. Historische en ruwe regels blijven lokaal; bronstatus wordt niet als KVK-verificatie gepresenteerd.
- **Besluit:** `GO_IMPLEMENTED` voor lokale kandidaatopbouw.

Evidence SHA-256: `e6381526334e6af3aa1cf7c60ca8de5186a79f57bf2ab4fbb6a5566d49acfe59`;
ZIP 5.055.585 bytes; organisatie-CSV 49.810.704 bytes.

## Feasibilitykaart 3 — TenderNed

- **Eigenaar en primaire URL:** TenderNed/RVO; [datasets aanbesteden](https://www.tenderned.nl/cms/nl/aanbesteden-in-cijfers/datasets-aanbestedingen).
- **Toegang en actualiteit:** openbare JSON/XLSX-datasets, halfjaarlijks aangevuld. De actuele XML-API vereist credentials en nieuwe aanvragen staan volgens de bronpagina op een wachtlijst; de datasetroute niet.
- **Voorwaarden/licentie/attributie:** aankondigingen en datasets zijn openbaar; de [gebruiksvoorwaarden](https://www.tenderned.nl/cms/nl/over-deze-site/gebruiksvoorwaarden) houden databank-/auteursrechten bij de Staat. Een specifieke datasetlicentie is niet aangetroffen, dus adaptergebruik blijft lokaal totdat hergebruik/attributie expliciet is vastgelegd. De datasetroute is niet door `robots.txt` geblokkeerd.
- **Registratienummer:** `parties[].id` bevat bij leveranciers vaak exact acht cijfers. De voorwaarden melden KVK-gebruik, maar het gedownloade JSON-schema labelt dit veld niet expliciet als KVK; de adapter moet die semantiek eerst aantoonbaar bevestigen.
- **Bias:** alleen organisaties die als leverancier of aanbestedende dienst in aanbestedingen voorkomen; meerdere publicaties per partij.
- **Gemeten opbrengst:** volledige H1-2026 JSON: 14.387 releases, 22.760 partijregels en 8.373 leverancierregels. Daarvan hadden 7.913 leverancierregels een exact achtcijferig ID, 4.262 uniek; 4.947 unieke genormaliseerde leveranciersnamen.
- **Overlap:** op exact achtcijferig ID: 7 met IND, 5 met de GLEIF-sample, 30 met DUO en 0 met de Wikidata-sample. Exacte naamoverlap: 6/5/23/0 en 104 met ANBI.
- **Parser/onderhoud:** Open Contracting-achtige geneste JSON; middelmatige complexiteit, met rolfiltering en expliciete veldsemantiek vereist.
- **Persoons-/gebruiksrisico:** handelsnamen kunnen persoonsnamen bevatten; alleen organisatie-/leveranciersrollen opnemen en ruwe data lokaal houden.
- **Besluit:** `GO_NEXT`, na expliciete veldsemantiek en hergebruiknotitie; geen onderdeel van automatische `sources collect`.

Snapshot SHA-256: `a48792f1e662e961dcf0afe2d06bcd1295045250517286fca51e04c13caa8827`.

## Feasibilitykaart 4 — TED

- **Eigenaar en primaire URL:** Publications Office of the European Union; [Search API](https://docs.ted.europa.eu/api/latest/search.html) en [open-datahandleiding](https://docs.ted.europa.eu/ODS/latest/index.html).
- **Toegang en actualiteit:** authenticatieloze `POST /v3/notices/search`; maximaal 250 notices per pagina, paginamodus maximaal 15.000 en iteratiemodus voor grotere resultaten. Dag-/maandpakketten zijn ook gedocumenteerd.
- **Voorwaarden/licentie/attributie:** procurement notices zijn volgens de [legal notice](https://ted.europa.eu/en/legal-notice) vrij herbruikbaar tenzij anders vermeld; metadata is CC0 en redactionele site-inhoud CC BY 4.0. De API-host retourneerde geen `robots.txt` (404); de gedocumenteerde API wordt gebruikt, niet gecrawld.
- **Registratienummer:** `buyer-identifier`/`business-identifier` bestaat, maar kan verschillende nationale schema's en geneste meertalige vormen bevatten.
- **Bias:** alleen EU-aanbestedingen; notice- en rolherhaling; grensoverschrijdende organisaties.
- **Gemeten opbrengst:** query `buyer-country = NLD` rapporteerde 182.625 notices. In een sample van 100 hadden alle notices een buyer-name, 63 het buyer-identifier-veld, met 67 identifierstrings; 30 waren exact acht cijfers, 15 uniek.
- **Overlap:** 1 van de 15 unieke achtcijferige samplewaarden overlapte DUO; 0 met de overige actieve samples.
- **Parser/onderhoud:** hoog door legacy/eForms, arrays, taalvarianten, rollen en schemasemantiek.
- **Persoons-/gebruiksrisico:** notices kunnen contactpersonen en derdepartijcontent bevatten; een adapter moet een minimale organisatiefield-allowlist hanteren.
- **Besluit:** `PARKED`; TenderNed heeft voor Nederland eerst een eenvoudiger en beter gemeten pad.

Sample SHA-256: `c9c94c23e9ea6f4a869694ef1eaabb129d94dccd13dfeeaae15289b1c390473a`.

## Feasibilitykaart 5 — DNB Openbaar Register

- **Eigenaar en primaire URL:** De Nederlandsche Bank; [Openbaar Register](https://www.dnb.nl/openbaar-register/).
- **Toegang en actualiteit:** de eigenaar biedt XML/CSV-downloads en een API; downloads worden iedere werkdag om 06:00 bijgewerkt.
- **Voorwaarden/licentie/attributie:** register is openbaar, maar een specifieke hergebruiklicentie voor de download is niet vastgesteld. `robots.txt` en de CSV-route gaven voor de begrensde client HTTP 403; geen omzeiling uitgevoerd.
- **Registratienummer:** niet vastgesteld omdat de CSV niet veilig kon worden bemonsterd; de zichtbare index toont namen/registercategorieën maar geen direct KVK-veld.
- **Bias:** uitsluitend instellingen onder financieel toezicht; meerdere vergunning-/registerrelaties per instelling mogelijk.
- **Gemeten opbrengst/overlap:** de bronpagina en downloadmetadata waren leesbaar, maar de begrensde CSV-call eindigde terminaal in HTTP 403. Recordopbrengst en overlap zijn daarom expliciet `NOT_AVAILABLE`, niet als nul geïnterpreteerd.
- **Parser/onderhoud:** vermoedelijk middelmatig XML/CSV, maar schema en toegangsroute moeten eerst officieel worden bevestigd.
- **Persoons-/gebruiksrisico:** registerdetail kan natuurlijke personen of functionarissen bevatten; minimale organisatievelden en een persoonsfilter zijn vereist.
- **Besluit:** `PARKED`; eerst toegestane API-/downloadtoegang, schema, licentie en kleine sample vastleggen.

## Feasibilitykaart 6 — AFM financieel dienstverleners

- **Eigenaar en primaire URL:** Autoriteit Financiële Markten; [register financiële dienstverleners](https://www.afm.nl/nl-nl/sector/registers/vergunningenregisters/financiele-dienstverleners).
- **Toegang en actualiteit:** volledige publieke CSV/XML-export; de pagina was op 18 september 2026 bijgewerkt.
- **Voorwaarden/licentie/attributie:** de AFM staat overname toe met uitdrukkelijke bronvermelding. `robots.txt` staat `/` toe en blokkeert `/sitecore`.
- **Registratienummer:** de CSV bevat alleen statutaire naam, handelsnaam en vestigingsplaats; geen KVK-nummer.
- **Bias:** financiële dienstverleners, aangesloten instellingen, bemiddelaars, buitenlandse paspoorthouders en natuurlijke personen.
- **Gemeten opbrengst:** 17.698 regels, allemaal met statutaire naam; 17.628 unieke genormaliseerde namen.
- **Overlap:** exacte naamoverlap met de actieve lokale samples: 23 ANBI, 1 IND, 1 DUO en 0 GLEIF/Wikidata. Naamoverlap is geen mergegrond.
- **Parser/onderhoud:** technisch laag (puntkomma-CSV, cp1252), inhoudelijk hoog door persoons-/buitenlandclassificatie en ontbrekende identifier.
- **Persoons-/gebruiksrisico:** hoog voor deze use case doordat natuurlijke personen expliciet in de bron zitten. Eerst aantoonbaar persoonsfilter en dataminimalisatie ontwerpen.
- **Besluit:** `PARKED`.

CSV SHA-256: `a16362b7ca27b7bf7d11984b094d37ed01e56f4ea55ac316b7981dfd2f3efebe`.

## Gecombineerde vijfbronnenmeting

De lokale R4-run is uitsluitend voor meetdoeleinden uitgebreid met de twee R5-adapters.
Het outcome-rapport bevat daardoor vijf actieve bronnen en vijf onafhankelijke families:

| Metriek | Waarde |
|---|---:|
| Ruwe records | 82.973 |
| Geldige directe KVK-records | 2.702 |
| Zonder direct KVK | 80.271 |
| Kandidaten vóór/na dedup | 82.972 / 82.951 |
| Identieke merges | 1 |
| Conflictregels | 21 |
| Actieve bronnen/families | 5 / 5 |
| Grootste ruwe familie-aandeel | 66,19% |
| Ruw-naar-dedup closure | `CLOSED` (82.973 → 82.973) |
| Totale status | `PARTIAL_CLOSED` |

De status is bewust `PARTIAL_CLOSED`: R5 voerde geen publieke KVK-matching of latere
filters uit. Exacte geldige-KVK-overlap was 2 voor DUO–Wikidata en 1 voor
GLEIF–Wikidata; alle overige actieve bronparen waren 0. Nul automatische
cross-source merges is correct: gelijke nummers met afwijkende naam-evidence werden
niet stil samengevoegd.

## Implementatie- en kwaliteitsbewijs

- `sources anbi` en `sources duo` zijn expliciete acties; `sources collect` en `run execute`
  starten geen onverwachte bulkdownload.
- Beide adapters gebruiken HTTPS-hostallowlists, handmatige redirectvalidatie vóór ieder
  request, byte-/tijd-/ruimte-/ZIP-/ratio-gates, immutable evidence en exacte inputre-use.
- ANBI XML wordt streaming met entiteitsbescherming verwerkt; DUO CSV wordt streaming
  gelezen. Historische DUO-regels en alle identifierproblemen zijn zichtbaar in rejected.
- De broncatalogus vult oudere runs alleen via een expliciete migrerende actie verliesvrij aan;
  pure reads veranderen historische runs en uitkomsten niet.
- 57 tests slagen; lint en strict typecheck slagen. `public_registers.py` behaalt 337/350
  statements (96,29%); ieder eigen Pythonbestand blijft boven 80%.
- Publicatiescan houdt alle echte snapshots, records en lokale paden buiten Git.

R5 voldoet hiermee aan zijn exitcriteria. R6 kan een deterministische, gestratificeerde
500-recordsample uit alle vijf actieve bronfamilies bouwen. R7 blijft `PARKED`.
