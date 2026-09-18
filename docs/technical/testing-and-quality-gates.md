# Testen en kwaliteitspoorten

`python tools/quality.py check` draait offline pytest met branchcoverage, maakt coverage-JSON, eist per eigen Pythonbestand `5 × covered > 4 × statements`, voert Ruff/mypy uit en scant gevolgde publicatiebestanden. Niet-geïmporteerde bestanden worden als `MISSING` afgekeurd; nul statements is `N/A`.

CI doet geen live harvest. Live bron-/KVK-smokes blijven lokaal en klein. Matrix: macOS arm64 Python 3.14 lokaal; Linux en Windows Python 3.11–3.14 via CI. Niet-uitgevoerde matrixcellen zijn `NOT_TESTED`.

