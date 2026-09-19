# Release- en downloadverificatie

`tools/release.py build` vereist een schone commit, bouwt wheel/sdist/bundle en legt SHA-256 vast. Het publieke manifest bevat alleen overdraagbare assetnamen, groottes en hashes; `verify` resolveert assets relatief aan dat manifest. Publiceer gefaseerd: verifieer GitHub-toegang en versie-exclusiviteit, maak de tag en een **conceptrelease**, download alle conceptassets terug en vergelijk hun bytes/hashes met het gekwalificeerde manifest. Zet pas daarna de release openbaar. `tools/release.py publish` automatiseert deze tussencontrole niet en mag daarvoor niet blind worden gebruikt. Na publicatie moeten release/tag/assets opnieuw worden teruggelezen en de wheel zonder auth opnieuw worden gedownload, gehasht en in een verse venv geïnstalleerd.

Een lokale build is geen publieke release. Een tag zonder asset evenmin. Releasebewijs staat per versie in `docs/releases/`; echte downloadlinks worden pas na succesvolle publicatie vastgelegd.

De actuele [v3.0.0-release](../releases/v3.0.0.md) bevat de vijfbronnenketen
en lichte export. Haar distributiebewijs wordt afzonderlijk vastgelegd na
CI, conceptcontrole, publicatie en anonieme herdownload. Ook de vorige
[v2.0.0-toolrelease](../releases/20260919-v2.0.0-evidence.md) is uit de
exacte broncommit gebouwd, op macOS/Windows-Python-3.14-CI gekwalificeerd
en byte-identiek hergedownload. Dit bewijst de distributie, niet een
volledige live KVK-harvest.

Voor CH-2026-09-19-010 is alleen een lokale wheel-smoke gedaan: de wheel is
in een tijdelijke Python-3.14-omgeving buiten de checkout geïnstalleerd,
met reeds aanwezige afhankelijkheden, en de twee nieuwe CLI-commando's plus
`run init` werkten daar. Dit bewijst de package-entrypoints, niet een
anonieme download, volledige dependency-installatie op een schone pc, macOS+
Windows-CI of releasekwalificatie. Er is geen nieuwe tag of asset gepubliceerd.

De online bundle bevat geen dependency-wheelhouse. Voor volledig offline installeren is een vooraf opgebouwd wheelhouse nodig.
