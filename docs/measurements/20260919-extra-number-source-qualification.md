# Vervolgkwalificatie bronfamilies met directe KVK-hint

Datum: 19 september 2026. Execution-ID: `CH-2026-09-19-041`.
Status: **onderzoek, geen adapter of harvest**. De actuele publieke KVK-check
vereist een achtcijferige KVK-hint uit de bron; een zoekvak waarin je een reeds
bekend nummer kunt invullen is geen bronhint. Een nummer in de footer van de
uitgever of organisator telt evenmin als nummer van een deelnemend bedrijf.

## Afbakening en beslisregel

Dit is een gerichte verkenning van publieke, primaire bronpagina's en twee
kleine officiële overheidsbestanden. Een `GO_NEXT` betekent uitsluitend dat
een **volgende begrensde feasibilityproef** zinvol is, niet dat hergebruik,
bulktoegang of adapterbouw al is vrijgegeven. `PARKED` betekent dat een direct
nummer ontbreekt in het gecontroleerde publieke record, of dat toegang/
voorwaarden een vervolg eerst vereisen. `NO_GO_FOR_NUMBER_ONLY` betekent dat
het bekeken publicatieformaat geen eigen KVK-hint per onderneming levert. Dit
is geen bewijs dat álle uitgaven, verenigingen, beurzen of gemeenten die missen.

| Bronfamilie en concrete publicatie | Direct KVK-nummer in bronrecord? | Voorlopig besluit en reden |
| --- | --- | --- |
| SBB: publieke erkende-leerbedrijfprofielen op [Stagemarkt](https://stagemarkt.nl/) en [MijnSBB Zoeken](https://zoeken-mijn.s-bb.nl/) | **Ja.** In een bekeken organisatieprofiel staan `KvK naam`, `KvK nummer` en `KvK vestigingsnummer`; MijnSBB-details hebben een gelijksoortig veld. De nummerzoekfunctie alleen was niet het bewijs. | **PARKED / geen inname.** [Stagemarkt-disclaimer](https://stagemarkt.nl/privacy-en-disclaimer/) verbiedt commerciële verwerking én een kopie van het databestand of delen daarvan. De [BPV-API](https://www.s-bb.nl/onderwijs/bpv-api) is beschreven voor mbo-scholen, niet als generieke open bulkkoppeling. Ook staan er leerlocaties en contactpersonen tussen de records; omvang van unieke *KVK-nummers* en passende gebruiksrechten zijn niet aangetoond. Eerst schriftelijke hergebruikduidelijkheid, zonder scraping als omweg. |
| Branchevereniging: [BOVAG](https://www.bovag.nl/) ledenzoeker en publiek lidmaatschapscertificaat | **Ja.** Een gecontroleerd 2026-certificaat toont bedrijfsnaam, adres, `KvK nummer` en actief **BOVAG-lidmaatschap** in dezelfde pagina; meerdere certificaten hadden dezelfde structuur. Lidstatus is geen KVK-actiefstatus. | **GO_NEXT voor kleine feasibilityproef.** BOVAG noemt op de certificaatpagina ruim 9.000 ondernemers, maar dat is geen geverifieerde omvang van openbaar oogstbare, unieke KVK-nummers. Nog onbekend: licentie/hergebruik, robots/toegestane toegang, enumeratie zonder zoekmisbruik, landelijke dekking en overlap met vijf bestaande bronnen. Geen adapter vóór die checks. |
| Andere brancheledenlijsten, o.a. KHN | **Intern mogelijk, publiek niet bewezen.** [CBS beschrijft een historische KHN-ledenlijst](https://www.cbs.nl/-/media/_pdf/2016/38/2016-koninklijke-horeca-nederland-jaarrapportage-2015.pdf) met bruikbare KVK-nummers, maar publiceert de ledenlijst niet; een nummer van de vereniging op haar eigen site telt niet voor leden. | **PARKED.** Alleen heropenen bij een actueel, publiek en herbruikbaar ledenbestand met nummer per lid. |
| Exposantenlijsten: [Gastvrij Rotterdam-deelnemerslijst 2026](https://www.gastvrij-rotterdam.nl/deelnemen/exposantenlijst), [TKD-inschrijfformulier](https://www.tkd.nl/exposanten/inschrijven-tkd/) en [Gastvrij Rotterdam-deelnameformulier](https://www.gastvrij-rotterdam.nl/files/files/2025/Deelnameformulieren/gvr2025-deelnameformulier-DSNM-nl-digitaal-2.pdf) | **Nee in de bekeken publieke lijst.** De officiële Gastvrij Rotterdam-lijst (stand 18 september 2026) toont exposantnamen maar geen `KvK`-veld. Organisatoren vragen een KVK-nummer bij inschrijving, maar onderscheiden dat van de publieke lijst/naamsvermelding. | **NO_GO_FOR_NUMBER_ONLY voor deze voorbeelden.** Een privaat verzameld inschrijfformulierveld is geen gepubliceerd deelnemersveld. Bovendien kunnen merken, buitenlandse exposanten en organisaties voorkomen. Alleen bij een concrete publieke deelnemersexport met KVK per record heropenen. |
| Rijksleveranciers: [Rijkscontractenregister (CSV, 1 juni 2026)](https://www.rijksoverheid.nl/documenten/2018/12/06/rijkscontracten) | **Ja.** Officiële CSV-kolom `Kvk Nr Leverancier`. In de begrensde lokale schematoets: 844 contractregels, 728 met exact acht cijfers, 318 unieke achtcijferige waarden; 61 leeg en 55 anders geformatteerd. Van die 55 hebben 45 slechts zeven cijfers: mogelijk ontbreekt een voorloopnul, maar die mag niet zonder verificatie worden ingevuld. | **GO_NEXT voor identifier-only feasibility, niet directe adapter.** De CSV heeft **geen afzonderlijk leveranciersnaamveld**: contracttitel of -omschrijving mag niet als bedrijfsnaam worden voorgesteld. `Aantal Unieke Deelnemers` en leveranciersrelatie moeten semantisch gecontroleerd worden. Een naam is in het huidige kandidaatschema nodig; eerst identifier-only route of een rechtmatige, exacte naamverrijking ontwerpen. Hergebruikvoorwaarden, overlap en historische peildatum nog toetsen. |
| Rijks-spendbestanden: [SZW Inkoopdata 2024](https://data.overheid.nl/dataset/inkoopdata-ministerie-van-sociale-zaken-en-werkgelegenheid-2024) | **Nee in bekeken XLSX.** Het officiële bestand `SZW_OD - Totaal.xlsx` heeft een blad `staffel` met 42 kolommen: `Leveranciersnaam`, inkoopcategorieën en eindtotaal; geen KVK-veld. De 1.734 datarijen zijn niet als kandidaten verzameld. | **NO_GO_FOR_NUMBER_ONLY voor deze export.** De datasetcatalogus is CC0, maar dat schept geen identifier. Andere departementen/jaren zijn niet uitputtend getoetst. |
| Groeibedrijven: [ECE Top 250](https://www.ece.nl/top-250/), [Deloitte Fast 50](https://www.deloitte.com/nl/en/services/deloitte-private/perspectives/2025-technology-fast-50-winners.html) en [KVK Innovatie Top 100](https://www.kvkinnovatietop100.nl/site/top-100-2025) | **Niet in gecontroleerde publieke pagina's/ranglijsten.** Namen, innovaties, sector-/groeicontext; geen KVK-veld per gepubliceerd bedrijf. ECE gebruikt KVK-registraties in de selectie, maar dat maakt de onderliggende nummers niet gepubliceerd. | **NO_GO_FOR_NUMBER_ONLY voor deze gecontroleerde publicaties.** Kleiner/sterk geselecteerd en geen directe hint. Niet-publieke registratiegegevens of een nummer in de footer van een deelnemer tellen niet. |
| Gemeentelijke bedrijventerreinsites: [Bedrijvenatlas Rijssen-Holten](https://www.rijssen-holten.nl/direct-regelen/ondernemen/uw-bedrijf/bedrijvenatlas/) en [bedrijventerreinen Utrecht](https://www.utrecht.nl/ondernemen/vestigen/bedrijventerreinen) | **Niet bewezen.** De gemeentelijke pagina's verwijzen naar een atlas/gebieds- en kavelsinformatie; de atlasviewer vereist JavaScript, zodat het individuele recordschema hier niet is vastgesteld. | **PARKED.** Eerst een concrete, herbruikbare bedrijvencatalogus met KVK per *vestiging/bedrijf* aantonen. Commerciële buurtwebsites die wel nummers afdrukken zijn niet automatisch gemeentelijke brondata. |

## Reproduceerbaarheid en resterende gaten

- Rijkscontracten: alleen de [officiële CSV van peildatum 1 juni 2026](https://www.rijksoverheid.nl/site/binaries/site-content/collections/documents/2018/12/06/rijkscontracten/01-06-2026-open-data-lijst-contracten-peildatum-1-juni-2026.csv)
  lokaal buiten Git geladen; CP1252/semicolon schema en achtcijferige
  veldwaarden geteld. De contractgegevens zelf, namen, records en CSV
  blijven lokaal. SHA-256 van de gelezen bytes:
  `c3ad4a9ff041c0126188548cbdfa70254290d1e7a9498e5fe3f69acff35ad177`.
- SZW: één [officiële XLSX-export van 2024](https://data.overheid.nl/sites/default/files/dataset/25b8a64b-1f9f-4779-b8e7-e0d0706b8048/resources/SZW_OD%20-%20Totaal.xlsx)
  lokaal buiten Git gelezen; uitsluitend de kolomkoppen en bladvorm zijn
  gebruikt voor het nummerbesluit. SHA-256:
  `8c57c80177ac0d2e62b7319b964663e8cb009390575d9996c7cc0570c5e984ca`.
  Geen kandidaten, uitgaven of persoons-/bedrijfsrijen naar Git gekopieerd.
- BOVAG en SBB: telkens enkele publieke detailpagina's bekeken; geen
  productieharvest of volledigheidsmeting. Publicatie van een nummer is
  onderscheiden van toestemming om een bronbestand samen te stellen.
- Er is geen overlapmeting met de bestaande vijfbronnenmaster uitgevoerd. Een
  netto-opbrengstclaim voor BOVAG of Rijkscontracten zou daardoor speculatief
  zijn. Geen KVK-frontend- of API-aanvragen gedaan.

**Vervolgvolgorde:** (1) BOVAG-rechten/toegang en kleine nummerdekkingproef;
(2) Rijkscontracten identifier-only gegevenscontract, leveranciersemantiek en
overlap; (3) SBB uitsluitend na duidelijke gebruikstoestemming. Expo-/groei-
en gemeentelijke lijsten pas heropenen bij een aantoonbaar direct KVK-veld in
dezelfde publieke bronset.
