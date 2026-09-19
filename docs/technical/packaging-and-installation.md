# Packaging en installatie

De Hatchling-wheel bevat de `src`-package en console-entrypoint. De
historisch gepubliceerde, inmiddels ingetrokken 2.0.0-wheel en de huidige
publieke 3.0.0-wheel ondersteunen
uitsluitend Python 3.14.x:
`Requires-Python: >=3.14,<3.15` blokkeert normale installatie met andere
minorversies en een package-guard blokkeert ook geforceerde installaties bij
het starten. De inmiddels ingetrokken v1.0.0-wheel had een breder
compatibiliteitscontract. De online route installeert dependencies vanaf hun index.
Playwright Chromium wordt bewust apart geïnstalleerd. Offline installatie
vereist een platformspecifieke wheelhouse en `--no-index`; die wheelhouse
bevat niet automatisch een browser.

De scripts in `scripts/` ondersteunen hostpreflight, niet-destructieve
venvinstallatie, runpreflight en starten op POSIX en PowerShell. Zij gebruiken
standaard `python3.14` (POSIX) of op Windows bij voorkeur `py -3.14`, met
een exacte 3.14-check van PATH-`python` als de launcher 3.14 niet vindt.
`PYTHON_BIN` kan expliciet naar een 3.14-interpreter wijzen.
Geen script gebruikt sudo, globale pip, Git of GitHub-login.

`run prepare-pre-kvk`, `kvk pre-kvk-batch` en `kvk pre-kvk-run` zijn consolecommando's van dezelfde
wheel; zij verwijzen niet naar een repositorycheckout of een losse `.local`-
runner. De datafolder blijft een externe, door de gebruiker gekozen locatie.

Voor het nieuwe `companies_delivery_light.xlsx` en de vijfbronnen-E2E-keten
is de publieke 3.0.0-wheel nodig; de ingetrokken 2.0.0-wheel had die
functies niet. De exacte macOS-/PowerShell-commando's staan in de
[E2E-handleiding](../functional/e2e-command.md). De 3.0.0-wheel kan na
download en hashcontrole zonder broncheckout worden geïnstalleerd.
De publieke 3.0.0-wheel kan op een groot bronbewijsveld vóór KVK stoppen;
de broncode voor 3.0.1 herstelt dit begrensd, maar is pas als schone-machine-
wheel bruikbaar na een afzonderlijke gekwalificeerde build.
