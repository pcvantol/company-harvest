# Release- en downloadverificatie

`tools/release.py build` vereist een schone commit, bouwt wheel/sdist/bundle en legt SHA-256 vast. Het publieke manifest bevat alleen overdraagbare assetnamen, groottes en hashes; `verify` resolveert assets relatief aan dat manifest. `publish` weigert bestaande releaseversies en controleert broncommit/werkboom. Daarna moeten release/tag/assets worden teruggelezen, de wheel zonder auth opnieuw worden gedownload, gehasht en in een verse venv geïnstalleerd.

Een lokale build is geen publieke release. Een tag zonder asset evenmin. Releasebewijs staat per versie in `docs/releases/`; echte downloadlinks worden pas na succesvolle publicatie vastgelegd.

De online bundle bevat geen dependency-wheelhouse. Voor volledig offline installeren is een vooraf opgebouwd wheelhouse nodig.
