# ADR-011 — Commandoroutering en pre-KVK-partitie scheiden

Status: Accepted (2026-09-19). Execution ID: CH-2026-09-19-025.

De CLI-parser en de publieke commandonamen blijven ongewijzigd. De dispatch
routeert eerst nieuwe-runopdrachten en de zelfstandige `MERGE_LISTS`-workflow;
voor bestaande runs zijn de handlers per commandofamilie gegroepeerd. Zij
roepen dezelfde services met dezelfde opties en uitvoerconventies aan. Er is
geen alternatieve, lichtere HARVEST-pipeline ingevoerd.

De bestaande pre-KVK-filter heeft nu een afzonderlijke streaming partitie
van master naar geschikte lijst en uitsluitingsledger. Pas na count-closure,
hercontrole van de master en publicatie worden metadata en artefactregistratie
afgerond. Regelversie, volgorde van redenen, kolommen, hashbinding, atomische
publicatie en opruimen van tijdelijke bestanden blijven gelijk.

Deze modulegrenzen maken toekomstige criteria afzonderlijk toetsbaar, maar
geven **geen** toestemming voor een fuzzy naamfilter. Bijna-gelijke namen
met verschillende KVK-hints blijven beide behouden totdat een apart besluit
en identiteitsbewijs anders rechtvaardigen. Geen runmigratie of nieuwe
runtime-dependency is nodig.
