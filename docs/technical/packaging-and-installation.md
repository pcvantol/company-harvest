# Packaging en installatie

De Hatchling-wheel bevat de `src`-package en console-entrypoint. Ondersteund: CPython 3.11–3.14. De online route installeert dependencies vanaf hun index. Playwright Chromium wordt bewust apart geïnstalleerd. Offline installatie vereist een platformspecifieke wheelhouse en `--no-index`; die wheelhouse bevat niet automatisch een browser.

De scripts in `scripts/` ondersteunen hostpreflight, niet-destructieve venvinstallatie, runpreflight en starten op POSIX en PowerShell. Geen script gebruikt sudo, globale pip, Git of GitHub-login.

`run prepare-pre-kvk` en `kvk pre-kvk-batch` zijn consolecommando's van dezelfde
wheel; zij verwijzen niet naar een repositorycheckout of een losse `.local`-
runner. De datafolder blijft een externe, door de gebruiker gekozen locatie.
