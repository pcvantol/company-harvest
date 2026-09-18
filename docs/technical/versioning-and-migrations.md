# Versies en migraties

Packageversie is gezaghebbend in `pyproject.toml`; CLI/changelog/tag gebruiken dezelfde waarde. In 0.x verhogen incompatibele contractwijzigingen MINOR, compatibele fixes PATCH. Tool-, run-/databaseschema-, export- en providerschemaversies zijn afzonderlijk.

Runs met een onbekende schemawaarde worden vóór schrijven geweigerd. Er is in 0.1.0 nog geen migratiepad; toekomstige migraties moeten getest, expliciet en herstelbaar zijn en mogen oude semantiek niet stil wijzigen.

Broncatalogusartefacten hebben een afzonderlijk schema. Schema 2 kan oude inventarisregels lezen, vult alleen nieuwe velden met expliciete defaults/unknowns aan en schrijft daarna een nieuw immutable catalogusartefact; het oude artefact blijft in de audittrail. Een onbekende run-schemaversie geeft hersteladvies om de oorspronkelijke programmaversie te gebruiken of een nieuwe run te starten.
