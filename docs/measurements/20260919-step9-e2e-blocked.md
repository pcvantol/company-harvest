# Stap 9 met volledig bronbestand — E2E door KVK geblokkeerd

- Datum: 2026-09-19
- Execution ID: `CH-2026-09-19-019`
- Status: `BLOCKED_KVK`; offline stap-9-invoer/merge/audit: `PASS`
- Geen echte bedrijfsnamen, KVK-nummers, responsebody of ruwe output in Git

## Exacte bron en volledige inname

Het door de gebruiker opgegeven lokale `step9_input.csv` (66.684 bytes,
SHA-256 `fd1f5b78f24a721960dedee218e26c54f7a383b3fa28809f4ee8b43a4d477df5`)
is volledig door de tool-CSV-parser gelezen. De mapping is `naam` → naam,
`kvkNummer` → KVK, met `sector`, `plaats`, `website` en `actief` als aanvullende
velden. De parser telde 1.447 datarijen, 1.447 geldige naam/KVK-combinaties,
1.408 unieke syntactisch geldige KVK-nummers, 39 extra duplicaatregels,
0 afgewezen en 0 structureel afwijkende rijen. De bronhash was na uitvoering
ongewijzigd.

## Begrensde KVK-stap in bestaande run

De bestaande vierbronnenrun had 119.801 KVK-geschikte kandidaten en één
eerder `NETWORK_ERROR`-journalrecord. Om de harde grens van tien **totaal**
te respecteren, was de nieuwe opdracht beperkt tot maximaal negen nieuwe
kandidaten en minimaal twee seconden tussen requeststarts. De eerstvolgende
publieke frontendaanroep ontving HTTP 400; de tool classificeerde dit als
`PUBLIC_ACCESS_BLOCKED` en stopte meteen. Er was geen retry, providerwissel
of nieuwe run om die blokkade te omzeilen. Het lokale evidencebestand bewaart
de responsehash en -omvang, maar de body is hier niet gepubliceerd.

De voortgang staat op `BLOCKED`: 2 gejournalde kandidaten, beide `FAILED`,
119.799 resterend, nul geverifieerde matches. De lokale capabilitypreflight
was `IMPLEMENTED`, maar dat was alleen een configuratiecheck en geen live
bereikbaarheidsbewijs. Er zijn geen `COMPLETE` KVK-matchartefacten of
definitieve delivery-outputset. Rechtsvorm-/statusfiltering en export zijn
terecht niet als volledige run uitgevoerd.

## Afzonderlijke offline stap-9-proef

Omdat de definitieve linkeruitvoer ontbreekt, is in een afzonderlijke
genegeerde lokale MERGE_LISTS-run uitsluitend het exact opgegeven bestand
**met zichzelf** samengevoegd. Dit is een technische functietest, **niet**
de werkelijke eindlijstmerge en ook geen KVK-verificatie. De tool maakte
twee inputsnaps met dezelfde SHA-256 en omvang als de bron.

Het merge-rapport sluit: 2.894 gelezen/geldige regels (2 × 1.447), 0
afgewezen, 1.408 unieke nummers, 33 naamconflictgroepen met 144
conflictregels, 0 veldconflicten en 1.375 uitvoerregels. De CSV- en
XLSX-uitvoer bevatten beide 1.375 rijen met unieke KVK-nummers.
`audit verify` controleerde negen geregistreerde artefacten en gaf
`valid=true`, `errors=[]`. De uitvoer heeft
`verification_status=UNCONFIRMED_IMPORTED` en mag niet als definitieve
geverifieerde ondernemingenlijst worden gebruikt.

Een echte E2E-levering met maximaal tien KVK-items is dus **niet bewezen**:
de live route stopte al bij het tweede totale journalitem en de bestaande
tool promoveert een partiële pre-KVK-batch terecht niet tot volledige input
voor canonisering en eindexport.
