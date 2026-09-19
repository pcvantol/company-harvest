# Versies en migraties

Packageversie is gezaghebbend in `pyproject.toml`; CLI/changelog/tag gebruiken dezelfde waarde. Vanaf 1.0.0 verhogen incompatibele publieke contractwijzigingen MAJOR, nieuwe compatibele functies MINOR en fixes PATCH. Tool-, run-/databaseschema-, export- en providerschemaversies zijn afzonderlijk.

De overgang van v1.0.0 naar 2.0.0 is MAJOR omdat de ondersteunde
Python-minorversies van 3.11–3.14 naar uitsluitend 3.14 veranderen. Een
gebruiker met Python 3.11–3.13 moet eerst Python 3.14 installeren en een
nieuwe virtuele omgeving maken. De oude v1.0.0-release en tag zijn op
19 september 2026 verwijderd; een reeds lokaal bewaarde 1.0.0-wheel wordt
hierdoor niet gewist. De tool hernoemt bestaande runs niet automatisch.

De GitHub Release en tags van v2.0.0 zijn op 19 september 2026 eveneens
op eigenaarsverzoek ingetrokken onder CH-2026-09-19-038. Dit verwijdert
geen bestaande lokale installatie of broncommit; nieuwe installaties
gebruiken de publieke v3.0.0-wheel.

De publieke versie 3.0.0 verwijdert de CLI-opties
`run e2e --export-limit` en `export --limit`. Dit is een MAJOR-wijziging
ten opzichte van v2.0.0. De export levert voortaan alle
actieve bedrijven binnen de gekozen KVK-scope. Een bestaande, onvoltooide
E2E-run met mogelijk bindende oude exportlimiet wordt niet stil omgezet;
een aantoonbaar niet-bindende limiet kan veilig naar het nieuwe contract
worden gemigreerd. Reeds geëxporteerde oude outputsets blijven auditbaar.

De 3.0.0-export gebruikt outputsetmanifest schema 2: naast de
bestaande minimale en volledige CSV/XLSX en de lege reserve bevat dit schema
een lichte, zakelijk verrijkte CSV/XLSX. Het manifest bindt alle zeven
bestanden met hashes en vermeldt de broncontext voor website/sector. `audit
verify` blijft historische schema-1-manifests met vijf bestanden accepteren;
oude outputsets worden niet herschreven. De nieuwe lichte bestanden bestaan
alleen na een nieuwe export met versie 3.0.0.

Runs met een onbekende schemawaarde worden vóór schrijven geweigerd. Er is in 1.0.0 geen algemeen migratiepad; toekomstige migraties moeten getest, expliciet en herstelbaar zijn en mogen oude semantiek niet stil wijzigen.

Broncatalogusartefacten hebben een afzonderlijk schema. Schema 2 kan oude inventarisregels lezen, vult alleen nieuwe velden met expliciete defaults/unknowns aan en schrijft daarna een nieuw immutable catalogusartefact; het oude artefact blijft in de audittrail. Een onbekende run-schemaversie geeft hersteladvies om de oorspronkelijke programmaversie te gebruiken of een nieuwe run te starten.
