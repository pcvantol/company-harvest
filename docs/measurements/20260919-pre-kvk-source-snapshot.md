# Eenmalige pre-KVK-bronmomentopname — CH-2026-09-19-009

Status op 2026-09-19: `BLOCKED_PREVIEW_NOT_KVK_READY`. De volledige
vijfbronnenmaster is **niet** gebouwd. De lokale run blijft
`PRE_KVK_BLOCKED`; er zijn nul KVK-verzoeken gedaan. R7 blijft `PARKED`.

De scope is de kandidaatlaag van de vijf actieve bronadapters, niet de gehele
Nederlandse ondernemingspopulatie en niet de historische/rejected-laag. Ruwe
download/evidence, echte organisaties en de lijst staan uitsluitend onder
`.local/r4/runs/1789809357641683000_20260919T091557.641560Z_aa1cb6/`
en buiten Git/assets. De oude R6/R8-runs zijn niet gewijzigd.

| Bron | Aantoonbaar volledig opgenomen kandidaatregels |
|---|---:|
| IND Arbeid | 12.980 |
| GLEIF NL Golden Copy | 197.163 |
| ANBI | 54.922 |
| DUO huidige instellingen | 27.601 |
| Wikidata P3220 | `BLOCKED`; geen volledige bronoutput |

Wikidata's bestaande label-SPARQL-paginering gaf eerst een leestime-out.
Een hervatting met ruimere leestijd gaf opnieuw een time-out. De lichtere
P3220-projectie leverde vervolgens twee gecontroleerde pagina's van 500
bindings; de derde kreeg HTTP 429 met `Retry-After: 120`. De runner stopte
direct, voerde geen latere bron- of KVK-verzoeken uit en hervat niet
automatisch na deze blokkade. De losse 1.000 bindings zijn alleen lokale
partiële evidence, geen compleet bronartefact en geen masterinput. Ook een
geslaagde OFFSET-doorloop zou slechts de *waargenomen* pagina's afsluiten,
niet een transactionele Wikidata-stand op één peildatum bewijzen.

Voor de vier volledige bronnen is offline een afzonderlijk,
KVK-geblokkeerd previewbestand gemaakt:

| Maatstaf | Waarde |
|---|---:|
| Bronkandidaatregels in preview | 292.666 |
| Previewregels | 289.916 |
| Samengevoegde bronregels | 2.750 |
| Regels met bronconflict | 8.170 |
| Voor KVK geblokkeerde regels | 289.916 |
| KVK-verzoeken | 0 |
| Masterbestand bytes | 361.340.447 |
| Masterbestand SHA-256 | `9b0ad8e660eb02ebee65fe8d6fc4ee1d4bec73b66df07e8a8f1489bc2215882b` |

De bron→preview-closure is `292.666 = Σ source_count` over alle 289.916
previewregels. Een onafhankelijke streaming narekening bevestigde tevens
289.916 unieke kandidaat-ID's, dezelfde bestandshash en uitsluitend
`BLOCKED_SOURCE_INCOMPLETE` als KVK-wachtrijstatus. De samenvoeging is
bewust conservatief: alleen exact dezelfde genormaliseerde naam én dezelfde
geldige directe KVK-hint worden automatisch samengevoegd. Naamgenoten
zonder zo'n hint blijven gescheiden; een gelijkende naam bewijst geen
identiteit. Conflicterende hints blijven zichtbaar en ongeverifieerd.

De preview is dus één lokale lijst van alle **volledig verzamelde
bron-kandidaatregels binnen de vierbronnenscope**, niet de gevraagde
vijfbronnenlijst en niet gereed voor een KVK-check. Het aparte rapport noemt
Wikidata als uitgesloten bron, draagt `CLOSED_INCLUDED_SCOPE_ONLY` en bindt
input/output aan hashes. De installeerbare productopdracht
`companies pre-kvk-list` weigert bij de ontbrekende vijfde bron een
volledige master te publiceren.
