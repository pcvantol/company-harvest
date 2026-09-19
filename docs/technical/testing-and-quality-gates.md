# Testen en kwaliteitspoorten

`python tools/quality.py check` draait offline pytest met branchcoverage, maakt coverage-JSON, eist per eigen Pythonbestand `5 × covered > 4 × statements`, voert Ruff/mypy uit en scant gevolgde publicatiebestanden. Niet-geïmporteerde bestanden worden als `MISSING` afgekeurd; nul statements is `N/A`.

CI doet geen live harvest. Live bron-/KVK-smokes blijven lokaal en klein. De actieve
CI-matrix bestaat uitsluitend uit Python 3.14 op `macos-latest` en `windows-latest`.
Linux wordt niet door de doorlopende CI gevalideerd en is voor nieuwe
wijzigingen daarom `NOT_TESTED`. Python 3.11–3.13 en 3.15+ zijn voor de
actuele 1.1.1-broncode expliciet `UNSUPPORTED`, niet alleen ongetest. De
historische releasekwalificatie van `v0.1.0` bevat bewijs voor een bredere
matrix; de reeds gepubliceerde v1.0.0-wheel wordt niet met terugwerkende
kracht gewijzigd. De lokale Apple-Siliconcontrole gebruikt Python 3.14.
