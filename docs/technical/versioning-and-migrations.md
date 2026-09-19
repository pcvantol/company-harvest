# Versies en migraties

Packageversie is gezaghebbend in `pyproject.toml`; CLI/changelog/tag gebruiken dezelfde waarde. Vanaf 1.0.0 verhogen incompatibele publieke contractwijzigingen MAJOR, nieuwe compatibele functies MINOR en fixes PATCH. Tool-, run-/databaseschema-, export- en providerschemaversies zijn afzonderlijk.

De overgang van v1.0.0 naar 2.0.0 is MAJOR omdat de ondersteunde
Python-minorversies van 3.11–3.14 naar uitsluitend 3.14 veranderen. Een
gebruiker met Python 3.11–3.13 moet eerst Python 3.14 installeren en een
nieuwe virtuele omgeving maken; de oude v1.0.0-wheel blijft beschikbaar voor
historisch gebruik. De tool hernoemt bestaande runs niet automatisch.

Runs met een onbekende schemawaarde worden vóór schrijven geweigerd. Er is in 1.0.0 geen algemeen migratiepad; toekomstige migraties moeten getest, expliciet en herstelbaar zijn en mogen oude semantiek niet stil wijzigen.

Broncatalogusartefacten hebben een afzonderlijk schema. Schema 2 kan oude inventarisregels lezen, vult alleen nieuwe velden met expliciete defaults/unknowns aan en schrijft daarna een nieuw immutable catalogusartefact; het oude artefact blijft in de audittrail. Een onbekende run-schemaversie geeft hersteladvies om de oorspronkelijke programmaversie te gebruiken of een nieuwe run te starten.
