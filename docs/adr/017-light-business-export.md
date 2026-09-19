# ADR-017 — Lichte, zakelijk verrijkte export naast auditexport

Status: aangenomen voor versie 3.0.0 (CH-2026-09-19-035).

## Context en besluit

De bestaande minimale Excel bevat alleen naam en KVK-nummer; de volledige
Excel bevat ook `response_json`, `source_relations` en technische metadata.
Een direct bruikbare zakelijke lijst ontbreekt. Daarom schrijft stap 8 in een
eigen `companies_delivery_light.csv` en `.xlsx` alle actieve geleverde
bedrijven, zonder tweede afkap. De oude minimale en volledige bestanden
blijven inhoudelijk ongewijzigd.

De lichte lijst bevat de canonieke KVK-naam, het exacte achtcijferige nummer,
rechtsvorm, status, plaats en land. Daarnaast worden de aanwezige zakelijke
velden uit de bewaarde publieke KVK-zoekhit als platte tekstkolommen
geprojecteerd. Het expliciete veldcontract dekt alle zakelijke velden die in
de lokaal waargenomen publieke respons voorkwamen. Bekende velden krijgen
Nederlandse koppen; toegestane geneste velden worden als afzonderlijke
kolommen uitgeklapt en meerdere waarden met `; ` gescheiden. Een onbekend
veld met projecteerbare inhoud blokkeert export voor review, zodat toekomstige technische metadata
niet ongemerkt in de lichte lijst terechtkomen.
Interne responsvelden (`id`, `bron`, `set`), ruwe JSON, provider,
controltijd, kandidaat-ID en bronrelaties staan niet in de lichte lijst.

`Website (bron)` en `Sector (bron)` komen uit de pre-KVK-master of de
kandidaatbron, niet van KVK. Koppeling gebeurt alleen via een unieke
`candidate_id` en exact gelijk bron-KVK-nummer. In de geïntegreerde
pre-KVK-route wordt per website en sector de eerste niet-lege bronwaarde
gebruikt, in vaste bronvolgorde. Een oudere master met nog lege projectie kan die waarden
uit zijn bewaarde bronpayloads halen. Ontbrekende bronwaarden blijven leeg.
Als broncontext is geregistreerd, verhindert een ontbrekende kandidaat-ID
of een afwijkend KVK-nummer de export. Bij een oudere run zonder geregistreerde
broncontext blijven beide bronkolommen leeg.
Er is geen naamfuzzy matching of onbewezen websitegok.

## Integriteit en migratie

Het outputsetmanifest heeft nu schema 2 en bindt alle zeven bestanden, plus
de gebruikte broncontext met pad en hash. Audit vergelijkt de lichte CSV
inhoudelijk met de KVK-/bronprojectie en controleert hashes en status voor
CSV en XLSX, ook bij PARTIAL. Historische schema-1-sets met vijf bestanden
blijven auditbaar; ze krijgen niet achteraf een lichte lijst. Een nieuwe
export is nodig om het nieuwe bestand te krijgen.

De publieke zoekrespons kan veranderen. Onbekende velden vergen dan eerst
een inhoudelijke beoordeling en uitbreiding van het veldcontract. Afwezigheid
in de lichte lijst is geen bevestigde negatieve KVK-uitspraak. Er is geen
live KVK-run uitgevoerd voor dit besluit.

## Aanvulling voor lokale 3.0.1-patch (CH-2026-09-19-040)

De begrensde live herhaling met tien nummerverzoeken gaf drie zakelijke
veldpaden die de 3.0.0-allowlist niet kende:
`bezoeklocatie.huisnummerToevoeging`, `oudeHandelsnamen` en `oudeNamen`.
Deze worden vanaf de lokale 3.0.1-bronversie als afzonderlijke lichte
kolommen toegelaten. Ook de overeenkomstige huisnummertoevoeging van het
postadres wordt als zakelijk adresonderdeel toegelaten. De oorspronkelijke
veiligheidsregel blijft: ieder ander onbekend veld met inhoud stopt de export.
Dit wijzigt geen ruwe KVK-respons of eerdere publieke wheel.
