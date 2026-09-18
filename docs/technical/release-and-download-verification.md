# Release- en downloadverificatie

`tools/release.py build` vereist een schone commit, bouwt wheel/sdist/bundle en legt SHA-256 vast. `verify` kwalificeert exact die bytes; `publish` weigert bestaande releaseversies en controleert broncommit/werkboom. Daarna moeten release/tag/assets worden teruggelezen, de wheel zonder auth opnieuw worden gedownload, gehasht en in een verse venv geïnstalleerd.

Een lokale build is geen publieke release. Een tag zonder asset evenmin. Releasebewijs staat per versie in `docs/releases/`; echte downloadlinks worden pas na succesvolle publicatie vastgelegd.

