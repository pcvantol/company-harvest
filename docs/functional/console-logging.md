# Consolevoortgang (vanaf 2.0.0)

Ieder `company-harvest`-commando toont op stderr een tijd, een gekleurde
status (`START`, `STEP`, `INFO`, `OK`, `WARN` of `FOUT`) en een korte
beschrijving. Bij een E2E-run zie je de hele volgorde van downloads,
samenvoeging, filter, KVK-check, vervolgfilters, export en audit. De
langlopende KVK-controle meldt op vaste intervallen het aantal verwerkte
kandidaten; er verschijnen geen bedrijfsnamen of KVK-nummers in deze regels.

De al bestaande resultaten blijven op stdout, bijvoorbeeld het pad van
`run init --print-path` en JSON-uitvoer. Daardoor werken bestaande scripts
en omleidingen ongewijzigd. Wil je alleen het machineleesbare resultaat:

```sh
RUN_DIR="$(company-harvest run init --target 10000 --print-path 2>/dev/null)"
```

Bij een fout stopt de betreffende fase met `FOUT`; een veilige foutcategorie
en de exitcode blijven zichtbaar. Vrije foutdetails (zoals ingevoerde
bestands- en werkbladnamen) worden bewust niet herhaald; bij een ongeldige
optie wordt alleen een herkende optienaam vermeld. Een onderbreking geeft
`WARN` en exitcode 130. Bij omleiding naar een bestand verschijnen dezelfde regels zonder
ANSI-codes. Voor geforceerde kleur gebruik je `FORCE_COLOR=1`; met
`NO_COLOR=1` schakel je kleur altijd uit. Dit verandert nooit wat wordt
opgeslagen of welke KVK-aanvragen worden gedaan.
