# Eindbestanden en veldherkomst (versie 3.0.0)

Deze beschrijving geldt voor de **publieke 3.0.0-wheel** en dezelfde
broncode. De oudere 2.0.0-wheel maakt geen lichte export. Na `run e2e` of een
afzonderlijke `export` staan de zeven databestanden plus het manifest bij het gerapporteerde
`outputset_manifest.json` in dezelfde tijdgestempelde `*_08_delivery_outputset`
map. Een begrensde KVK-proef is `PARTIAL` als er niet-gecheckte kandidaten
overblijven; de bestanden bevatten nooit meer bedrijven dan de vaste
`--limit-kvk-check`-cohort.

| Bestand | Gebruik en inhoud |
|---|---|
| `companies_delivery.xlsx` / `.csv` | Minimale lijst met exact `Bedrijfsnaam` en `KVK-nummer`. |
| `companies_delivery_light.xlsx` / `.csv` | Zakelijke eindlijst met KVK-velden, plus `Website (bron)` en `Sector (bron)`. Geen ruwe JSON, bronrelaties, kandidaat-ID, provider of controletijd. |
| `companies_delivery_full.xlsx` / `.csv` | Technische/audituitvoer met o.a. `candidate_id`, rechtsvorm/status, `response_json` en `source_relations`; bevat niet automatisch de bronwebsite/-sector als aparte kolommen. |
| `companies_reserve.csv` | Compatibiliteitsbestand; bij nieuwe exports leeg. Geen verborgen tweede afkap. |
| `outputset_manifest.json` | Schema 2: status (`COMPLETE`/`PARTIAL`), selectiebeleid `ALL_ACTIVE`, aantal actieve rijen, zeven bestanden met hashes/grootten en eventuele KVK-cohort/broncontext van de lichte lijst. |

Alle CSV-bestanden zijn UTF-8 **tabgescheiden** ondanks de `.csv`-extensie.
De XLSX behandelt het achtcijferige KVK-nummer als tekst, zodat voorloopnullen
behouden blijven. De lichte lijst is bedoeld voor analyse; bewaar ook de
volledige outputset en het manifest als auditspoor.

## Kolommen van de lichte lijst

De vaste kolommen zijn `Bedrijfsnaam`, `KVK-nummer`, `Rechtsvorm (KVK)`,
`Status (KVK)`, `Plaats (KVK)`, `Land (KVK)`, `Website (bron)` en
`Sector (bron)`. Naam, nummer en rechtsvorm zijn uit de exact op nummer
gematchte publieke zoekhit overgenomen. `Status (KVK)` is bij de publieke
HTTP-respons de leesbare afleiding van de `actief`-vlag. Plaats komt uit de
publieke locatie; land kan als Nederland uit die locatie zijn afgeleid.
Alleen bedrijven met een expliciet actieve status en bekende, niet als
eenmanszaak geclassificeerde rechtsvorm halen deze eindlijst.

Wanneer aanwezig komen daarnaast de zakelijke velden uit het waargenomen
publieke responscontract in aparte kolommen: rechtsvormcode, actief-vlag,
inschrijfdatum en -type, activiteitomschrijving/-velden, vestiging en
vestigingsnummer, statutaire/handelsnamen, en onderdelen van bezoek- en
postadres. De lokale 3.0.1-patch kwalificeert bovendien oude handelsnamen,
oude namen en `huisnummerToevoeging` als afzonderlijke KVK-kolommen. De
kolomset kan per run variëren omdat afwezige responsvelden
geen kolom krijgen. Geneste velden worden platte kolommen; meerdere waarden
in één veld worden met `; ` gescheiden. Een lege waarde betekent *niet
beschikbaar*, niet een door KVK bevestigde ontkenning. Een onbekend nieuw
responsveld met projecteerbare inhoud stopt de export totdat het zakelijke/
technische karakter is beoordeeld; het wordt niet stil als kolom toegevoegd.

`Website (bron)` en `Sector (bron)` zijn **geen KVK-gegevens** en worden
niet geraden of gevalideerd. In de geïntegreerde pre-KVK-route komen zij uit
de eerste niet-lege waarde van samengevoegde bronrecords; bij de oudere
generieke kandidaatroute geldt de daar bewaarde kandidaatwaarde. De koppeling
aan de KVK-rij vereist dezelfde
`candidate_id` en hetzelfde achtcijferige KVK-nummer zodra broncontext is
geregistreerd. Bij ontbrekende broncontext blijven beide bronkolommen leeg;
een aanwezige maar onvolledige of tegenstrijdige broncontext blokkeert de
export. Een afwijkende handelsnaam wordt hiervoor niet fuzzy vergeleken.
De precieze bronrelaties blijven in de volledige export en lokale
pre-KVK-master.

`audit verify --run-dir <runmap>` controleert ook `PARTIAL`-manifesten en
alle zeven geregistreerde bestanden. Oudere schema-1-outputsets met vijf
bestanden blijven controleerbaar, maar krijgen niet achteraf een lichte
Excel. Een nieuwe export met de actuele broncode is daarvoor nodig.
