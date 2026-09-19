# ADR-010 — Alleen Python 3.14 voor de actuele tool

Status: Accepted (2026-09-19). Execution ID: CH-2026-09-19-021.

De eigenaar kiest voor één Python-minorversie, 3.14.x, voor de actuele tool.
De nog niet gepubliceerde 1.1.0-wheel declareert
`Requires-Python: >=3.14,<3.15`. Dit is de normale installatiegrens;
`company_harvest.__init__` stopt daarnaast onmiddellijk met een duidelijke
fout als iemand de wheel ondanks die metadata toch onder een andere
minorversie installeert of rechtstreeks uit bron start.

Hostpreflight en POSIX-/PowerShell-installers controleren dezelfde exacte
minorversie vóór gebruik, ook bij een installatiedry-run. POSIX selecteert
standaard `python3.14`. Windows
probeert `py -3.14` en accepteert PATH-`python` alleen als die aantoonbaar
3.14 is; `PYTHON_BIN` blijft een expliciete keuze met dezelfde toets.
Ruff/mypy richten zich op 3.14 en de bestaande CI-matrix bevat uitsluitend
macOS/Windows met 3.14. Dit contract geldt voor de actuele broncode en een
toekomstige 1.1.0-release, niet met terugwerkende kracht voor de al
gepubliceerde v1.0.0-wheel of historische kwalificatieclaims.
