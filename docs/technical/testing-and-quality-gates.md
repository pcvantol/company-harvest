# Testen en kwaliteitspoorten

`python tools/quality.py check` draait offline pytest met branchcoverage, maakt coverage-JSON, eist per eigen Pythonbestand `5 × covered > 4 × statements`, voert Ruff/mypy uit en scant gevolgde publicatiebestanden. Niet-geïmporteerde bestanden worden als `MISSING` afgekeurd; nul statements is `N/A`.

CI doet geen live harvest. Live bron-/KVK-smokes blijven lokaal en klein. De actieve
CI-matrix bestaat uitsluitend uit Python 3.14 op `macos-latest` en `windows-latest`.
Linux en Python 3.11–3.13 worden niet meer door de doorlopende CI gevalideerd en zijn
voor nieuwe wijzigingen daarom `NOT_TESTED`, ook al bevat release `v0.1.0` historisch
bewijs voor een bredere matrix. De lokale Apple-Siliconcontrole gebruikt Python 3.14.
