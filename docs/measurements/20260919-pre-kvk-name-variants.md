# Pre-KVK-naamsvarianten: verkennende meting

Status: **ALLEEN ANALYSE — GEEN NIEUWE FILTER**. Bron is de nieuwste lokale
`pre_kvk_eligible.tsv` uit de afgeronde vierbronnenfilter met regelversie
`pre-kvk-eligibility-7`, SHA-256
`7291708bf10808335df49fa8cee88fba7c28036855f8855b47849d7e5313a0fc`.
De metadata sluit 289.916 masterregels op 119.801 geschikte en 170.115
uitgesloten regels. Geen bron is opnieuw gedownload en geen KVK-verzoek is
gedaan. Ruwe namen, KVK-nummers en runbestanden blijven buiten Git.

De bestaande `normalized_name` past NFC, trimmen, witruimtecompressie en
casefold toe. In de 119.801 geschikte regels is die naam uniek. Ook elk
opgegeven directe KVK-nummer is uniek. De eerdere deduplicatie heeft dus
geen naam- of KVK-gelijke regels in deze lijst overgelaten.

| Naamvergelijking | Groepen | Regels in groepen | Hypothetisch overschot bij één regel per groep | Naampaarvergelijkingen |
|---|---:|---:|---:|---:|
| Extra: alle spaties, punten en koppeltekens weglaten | 126 | 254 | 128 | 130 |
| Daarbovenop: afsluitend `BV`/`B.V.` optioneel | 283 | 568 | 285 | 287 |

De tweede rij omvat de eerste en is **niet optelbaar**. Van de 283 groepen
komen er 261 uitsluitend uit GLEIF, 18 uit GLEIF plus IND en 4 uitsluitend
uit IND. In **alle 283 groepen** hebben de regels verschillende opgegeven
KVK-nummers. De 285 zijn dus hooguit mogelijke te besparen KVK-checks
(0,24% van de lijst) als iedere naambotsing werkelijk één entiteit was,
**geen bewezen dubbelen**.

Een aanvullende, bewust begrensde één-teken-screening vond 1.913 paren van
verschillende vergelijkingssleutels. Deze screening vereiste gelijke eerste
vier tekens en een sleutellengte van 10–60. Hij is niet volledig en is niet
opgeteld bij de 285. Veel treffers zijn genummerde/geromaniseerde
entiteiten of andere plausibel zelfstandige bedrijven. Eén teken verschil
is daarom geen betrouwbare uitsluitgrond.

Interpretatie: een automatische verwijdering vóór KVK kan verschillende
geregistreerde entiteiten samenvoegen en daarmee de verliesvrije bronlijst
schenden. De naamvarianten zijn hoogstens kandidaten voor een latere
reviewmarkering. Een feitelijke dubbelstatus kan deze meting zonder
identiteitsbewijs niet vaststellen. De eigenaar beslist apart over een
eventuele implementatie; tot dan blijft de tool ongewijzigd.
