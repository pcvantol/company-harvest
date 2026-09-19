# Testen en kwaliteitspoorten

`python tools/quality.py check` draait offline pytest met branchcoverage, maakt coverage-JSON, eist per eigen Pythonbestand `5 × covered > 4 × statements`, voert Ruff/mypy uit en scant gevolgde publicatiebestanden. Niet-geïmporteerde bestanden worden als `MISSING` afgekeurd; nul statements is `N/A`.

`tests/test_cli_routing.py` bewaakt na ADR-011 de servicekeuze, de
JSON-versus-tekstuitvoer en expliciet de doorgifte van optiecombinaties per
commandofamilie. De pre-KVK-filtertests bewaken dat bijna-gelijke namen met
verschillende KVK-hints niet stil worden samengevoegd. Een offline E2E-proef
blijft de gedeelde keten met gemockte KVK-verzoeken toetsen.

CI doet geen live harvest. Live bron-/KVK-smokes blijven lokaal en klein. De actieve
CI-matrix bestaat uitsluitend uit Python 3.14 op `macos-latest` en `windows-latest`.
De workflow gebruikt `actions/checkout@v7` en `actions/setup-python@v7`;
beide officiële acties draaien op de Node 24-runtime. Dat is de runtime van
de GitHub Actions-stappen, niet een extra Python-/Node-applicatiematrix.
Elke matrixjob heeft na de algemene gate een afzonderlijke **offline E2E-
integratiestap** (`tests/test_ci_e2e_integration.py`). Die start de echte
`run e2e`-CLI op een lege synthetische run, simuleert broncollectors en de
KVK-zoekresultaten, verbiedt externe netwerkverbindingen (lokale Playwright-
IPC blijft mogelijk) en controleert de pre-KVK-
cohort, het KVK-journal, de eenmanszaakfilter, eindlijst, manifest, audit en
idempotent hervatten. De test wordt ook door de algemene pytest-/coveragegate
uitgevoerd; de aparte stap maakt haar CI-uitkomst expliciet zichtbaar.
Linux wordt niet door de doorlopende CI gevalideerd en is voor nieuwe
wijzigingen daarom `NOT_TESTED`. Python 3.11–3.13 en 3.15+ zijn voor de
actuele 1.1.1-broncode expliciet `UNSUPPORTED`, niet alleen ongetest. De
historische releasekwalificatie van `v0.1.0` bevat bewijs voor een bredere
matrix; de reeds gepubliceerde v1.0.0-wheel wordt niet met terugwerkende
kracht gewijzigd. De lokale Apple-Siliconcontrole gebruikt Python 3.14.
