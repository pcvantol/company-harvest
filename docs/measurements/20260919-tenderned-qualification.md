# TenderNed — vervolgkwalificatie KVK-veld

Datum: 2026-09-19 · Execution ID: CH-2026-09-19-030
Besluit op dit meetmoment: **GO voor ontwerp van een begrensde, lokale bronadapter**. Implementatie volgt afzonderlijk onder CH-2026-09-19-031.

## Bron en veldbetekenis

De [officiële datasetpagina](https://www.tenderned.nl/cms/nl/aanbesteden-in-cijfers/datasets-aanbestedingen)
biedt openbare XLSX- en JSON-bestanden zonder account. Onderzocht zijn de XLSX
`Dataset_Tenderned-compleet-2021-01-01-2026-06-30.xlsx` en de al lokaal
vastgelegde JSON 2026 Q1/Q2. In de XLSX definieert `Leeswijzer!A93:B93`
`ON kvknummer` als **“KvK-nummer van de onderneming”**; `Mapping OCDS !A80:B80`
koppelt dit aan `awards/suppliers/id`. De daadwerkelijke XLSX-kolom is
`OpenData sheet!CA`, naast leveranciersnaam `BZ` en vestigingsland `CF`.
Daarmee is de eerdere veldsemantiekvraag uit R5 opgelost. `parties[].id` bij
de JSON-rol `supplier` had in de onderzochte 2026-snapshot exact dezelfde
verzameling achtcijferige IDs als `awards[].suppliers[].id` (beide 4.262).

Het veld is een **door TenderNed gepubliceerd KVK-bronhint**, geen op dit moment
geverifieerde Handelsregisterstatus of bewijs van juiste rechtspersoon. Volgens
[TenderNed](https://www.tenderned.nl/cms/nl/nieuws/nieuwe-aankondigingsformulieren-alle-wijzigingen-op-een-rij)
komt het nummer voor elektronische inschrijvingen uit de organisatiegegevens,
wordt het voor handmatig toegevoegde ondernemingen door de aanbestedende dienst
ingevuld, en krijgen buitenlandse ondernemingen een automatisch referentienummer.
De [gebruiksvoorwaarden](https://www.tenderned.nl/cms/nl/over-deze-site/gebruiksvoorwaarden)
zeggen bovendien dat TenderNed ingevoerde gegevens niet op juistheid,
volledigheid of actualiteit verifieert. Daarom zijn acht cijfers en het
XLSX-label onvoldoende voor een definitieve KVK-match zonder landfilter en
verdere controles.

## Gemeten opbrengst

De volledige XLSX 2021 t/m 2026 Q1/Q2 heeft 131.958 publicatieregels. Van
55.567 regels met een naam van een gegunde onderneming hebben 39.201 een
exact achtcijferig `ON kvknummer`, 15.475 missen een nummer en 891 hebben
een niet-achtcijferige waarde. Achtcijferige nummers zijn op **alle landen**
ontdubbeld tot 11.201; bij regels met `ON land = Nederland` tot **11.147**.
De 39.201 geldige-vormregels bevatten 39.120 Nederlandse regels. Deze
vormcontrole is geen controle op bestaan of geldigheid bij de KVK.

| Publicatiejaar | Publicatieregels | Regels met gegunde onderneming | Met achtcijferig nummer | Unieke achtcijferige nummers |
|---|---:|---:|---:|---:|
| 2021 | 21.035 | 8.709 | 4.291 | 2.379 |
| 2022 | 22.394 | 10.285 | 5.163 | 2.788 |
| 2023 | 23.347 | 10.329 | 5.732 | 2.962 |
| 2024 | 25.014 | 9.948 | 9.004 | 4.156 |
| 2025 | 25.781 | 9.874 | 9.012 | 4.396 |
| 2026 Q1/Q2 | 14.387 | 6.422 | 5.999 | 3.295 |

De jaartotalen van unieke nummers zijn niet optelbaar: dezelfde leverancier
verschijnt in meerdere publicaties en jaren. Bij 1.871 unieke nummers kwam
meer dan één casefold-naam voor; dat kan handelsnamen of schrijfwijzen betreffen en
is geen automatisch bewijs van een conflict of afzonderlijk bedrijf.

De 2026-JSON heeft **4.262** unieke achtcijferige IDs van
`awards[].suppliers[]`: 967 meer dan de XLSX-weergave van 2026, met alle
3.295 XLSX-IDs ook in JSON. Van de 967 JSON-only-IDs komen 640 zelfs nergens
voor in de onderzochte XLSX 2021–2026. De 2026-JSON bevat 9.694
`awards[].suppliers[]`-regels tegenover 6.422 XLSX-regels met gegunde
onderneming. Een aanvullende read-only reconciliatie koppelde alle 967
JSON-only-IDs aan publicatie-IDs die wél in de XLSX staan. Bij 958 stond in de
XLSX een **ander** achtcijferig leveranciersnummer, bij negen geen geldig
nummer. De XLSX representeert dus niet elke gegunde leverancier van een
publicatie; JSON kan meerdere leveren. Voor de adapter telt daarom de XLSX
uitsluitend tot en met het jaar vóór de actuele JSON, en de JSON het laatste
jaar. De twee tellingen worden nooit blind opgeteld.

## Overlap met de huidige vierbronnenrun

Op exact achtcijferig nummer, zonder naammatching, overlappen 1.769 van de
11.201 XLSX-nummers met de **directe bronhints** in de volledige master
(289.916 regels; 206.943 unieke geldige directe nummers). De overige **9.432**
ontbreken als directe nummerhint in die master; voor `ON land = Nederland` is
dat **9.380**. Met de 119.801 pre-KVK-geschikte nummers overlappen er 1.489;
de overige 9.712 (9.660 met Nederlandse landregel) zitten niet in die
KVK-wachtrij. Dit zijn potentiële extra nummerhints, **niet** evenveel netto
nieuwe entiteiten of toekomstige eindregels: naamloze KVK-kandidaten kunnen al
in de master zitten en de bestaande pre-KVK-filter kan TenderNed-rijen alsnog
uitsluiten.

De 2026-JSON heeft op zichzelf 4.262 unieke achtcijferige leveranciers-IDs;
3.535 daarvan ontbreken als directe KVK-hint in de volledige master. Het
verschil met de XLSX-cijfers komt mede door JSON/XLSX-representatie; voor een
gecombineerde 2021–2026-JSON-opbrengst zijn de historische JSON-bestanden nog
niet gedownload of gemeten.

## Geschiktheid en open poorten

- **Dekking/bias:** alleen gegunde ondernemingen in gepubliceerde
  aanbestedingen; geen algemene bedrijvendatabase, geen bewijs van huidige
  activiteit of personeelsomvang. Publicatie- en leverancierherhaling.
- **Actualiteit:** de [Q1-2026-aankondiging](https://www.tenderned.nl/cms/nl/nieuws/nieuwe-dataset-q1-2026-beschikbaar)
  noemt sinds 2026 kwartaalpublicatie. De datasetpagina en voorwaarden zeggen
  nog “halfjaarlijks”; de actuele downloadlijst en versiedatum zijn daarom
  leidend voor een latere adapter, niet een vaste kalenderaanname.
- **Toegang:** openbare bulkdownload is passend voor lokale analyse; de
  afzonderlijke actuele XML-API vraagt credentials en staat voor nieuwe
  aanvragen op een wachtlijst. Die API is niet nodig voor dit voorstel.
- **Gebruik/privacy:** dataset is publiek en voor analyse aangeboden, maar er
  is geen expliciete datasetlicentie of toestemming voor redistributie
  vastgesteld. De voorwaarden plaatsen intellectuele-eigendomsrechten op
  onder meer databestanden bij de Staat. Geen ruwe records in Git of wheel; extern publiceren van
  afgeleide lijsten vergt afzonderlijke beoordeling. Handelsnamen kunnen
  persoonsnamen bevatten; contactvelden zijn voor deze usecase niet nodig.
- **Acceptatie van een eventuele adapter:** alleen `awards[].suppliers[]` met
  expliciete Nederlandse land-evidence; exact acht cijfers als bronhint;
  ontbrekende/ongeldige/tegenstrijdige IDs naar lokaal review-/rejected-pad;
  per bronpublicatie herkomst en snapshot-hash; geen automatische samenvoeging
  op naam; bestaande pre-KVK-filter en KVK-check blijven afzonderlijke poorten.
  De JSON/XLSX-rijreconciliatie is hierboven uitgevoerd. Adapterbouw en
  broninname horen bij een apart increment; deze kwalificatie deed geen
  KVK-harvest.

## Lokaal bewijs en reproduceerbaarheid

- Officiële XLSX: 69.915.228 bytes, SHA-256
  `c55a4a10cfe50b3c9aacc338ef091099fba22bd57e89880f4f37cc945f49db54`;
  uitsluitend lokaal onder `.local/tenderned-qualification/`.
- JSON 2026 Q1/Q2: SHA-256
  `a48792f1e662e961dcf0afe2d06bcd1295045250517286fca51e04c13caa8827`;
  eerder lokaal onder `.local/r5/20260918T142300Z/evidence/`.
- Vergelijkingsbestanden: volledige pre-KVK-master en laatste geschikte lijst
  van de lokale run `1789809357641683000_20260919T091557.641560Z_aa1cb6`.
- Telling: read-only `openpyxl`-iteratie per XLSX-rij, exacte Python-regex
  `[0-9]{8}`, set-dedup per nummer, JSON `awards[].suppliers[]`, TSV-join
  alleen op `source_kvk_hint`; geen KVK-/bron-API-aanroepen tijdens de telling.
  Een lokale, genegeerde analysetool bevat de reproduceerbare aggregatie en
  print geen bedrijfsnamen of nummers.

Status van een volledige historische JSON-vergelijking, netto nieuwe
eindbedrijven, KVK-validatie en externe hergebruikrechten: **NOT_TESTED**.
