# R2-broncapabilitymeting — IND en Wikidata

Meetdatum: 2026-09-18  
Status: afgeronde begrensde live meting  
User-Agent: `company-lookup/0.1`

## Uitkomst

| Bron | Status | Scope | Ruwe records | Geldig KVK | Uniek geldig KVK | Ongeldig | Duplicaat-ID | Duplicaatnaam |
|---|---|---|---:|---:|---:|---:|---:|---:|
| IND Openbaar register Arbeid | `LIVE_MEASURED` | volledige bronpagina | 12.980 | 12.980 | 12.977 | 0 | 3 | 10 |
| Wikidata `P3220` | `LIVE_MEASURED` | begrensde, op item-URI gesorteerde sample van 200 | 200 | 195 | 195 | 5 | 0 | 0 |

Voor beide bronnen sluit `ruw = geldig + ontbrekend + ongeldig`; er waren geen
parserafwijzingen; IND-kandidaatrijen zijn daarbij vóór validatie geteld. IND leverde één
HTTP 200-respons van 962.819 bytes in 0,191113 seconde. Wikidata leverde twee HTTP
200-responses van samen 65.477 bytes in 13,700828
seconden. Geen van beide responses bevatte de gemeten rate-limitheaders. Dat is een
observatie, geen bewijs dat geen limiet geldt.

De exacte vergelijking van unieke, syntactisch geldige KVK-nummers vond 12 gedeelde
nummers. Dat is circa 0,0925% van IND en 6,154% van de begrensde Wikidata-sample. De
laatste verhouding mag niet worden geëxtrapoleerd naar heel Wikidata: de sample is niet
aselect en de Wikidata-collectie was bewust niet volledig.

## Actualiteit, voorwaarden en semantiek

- De [IND-bronpagina](https://ind.nl/nl/openbaar-register-erkende-referenten/openbaar-register-arbeid)
  vermeldde een maandelijkse actualisatie en als brondatum 3 september 2026. De
  [IND-proclaimer](https://ind.nl/nl/proclaimer) staat hergebruik met bronvermelding toe.
- [Wikidata Data access](https://www.wikidata.org/wiki/Wikidata:Data_access) beschrijft
  gestructureerde Wikidata-inhoud als CC0 en verwijst voor programmatische toegang naar
  beheerst gebruik. De meting gebruikt de officiële
  [KvK company ID-property P3220](https://www.wikidata.org/wiki/Property:P3220).
- De vijf Wikidatawaarden die niet door de strikte validator kwamen zijn verliesvrij als
  `INVALID` bewaard. De propertydocumentatie laat historisch zeven of acht cijfers toe,
  terwijl [KVK het huidige KVK-nummer als acht cijfers beschrijft](https://www.kvk.nl/en/about-the-business-register/kvk-number-all-you-need-to-know/).
  Er is daarom niet stil voorloopnul aangevuld.
- Geen van beide adapters levert in deze slice rechtsvorm of actieve status. Een
  registratienummer uit deze bronnen is een bronhint en niet automatisch bewijs van
  actuele KVK-status of rechtsvorm.

## Bias en besluit

IND is een sterk herleidbare overheidsbron, maar omvat alleen erkende referenten voor
arbeid en is geen sectorbrede populatie. Wikidata is vrijwillig samengesteld en verschilt
per item in actualiteit en dekking. De IND-bron levert zelfstandig al meer dan 10.000
ruwe records, maar daarmee is het productdoel van 10.000 unieke, actieve ondernemingen
zonder bevestigde eenmanszaken nog niet bewezen.

De capability van beide bestaande bronnen is aangetoond; R2 kan worden gesloten. Er
worden nog geen succesdrempels afgeleid. R3 moet eerst de GLEIF-feasibility en een derde
onafhankelijke bronfamilie datagedreven beoordelen.

## Bewijsanker

De ruwe responses en rijdata blijven volgens het repositorybeleid lokaal en genegeerd.
Het gecommitte aggregaat is afgeleid van precies deze finale run en fingerprints:

- run-ID: `1789738650870482000_20260918T133730.870430Z_e9c2e6`;
- capabilityrapport SHA-256: `00cbf8661c41b59ab851821957d0f293c9b66b04559a1e4962773ab605ebae56`;
- IND-evidence SHA-256: `e9b1f1049753381a1c5c8ce2f859d8a24456547309ed4de5e194d23c7363c26e`;
- Wikidata pagina 1 SHA-256: `dfbd04192c1c4e8c0feb1c136305a0c23ba255f90420fac1269b6e1d57c4767c`;
- Wikidata pagina 2 SHA-256: `f013911971caf7806dd360e474b57bac6bebfcf97bd98b20c3858a10a2c0e48b`.
