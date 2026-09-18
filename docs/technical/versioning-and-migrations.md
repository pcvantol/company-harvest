# Versies en migraties

Packageversie is gezaghebbend in `pyproject.toml`; CLI/changelog/tag gebruiken dezelfde waarde. In 0.x verhogen incompatibele contractwijzigingen MINOR, compatibele fixes PATCH. Tool-, run-/databaseschema-, export- en providerschemaversies zijn afzonderlijk.

Runs met een onbekende schemawaarde worden vóór schrijven geweigerd. Er is in 0.1.0 nog geen migratiepad; toekomstige migraties moeten getest, expliciet en herstelbaar zijn en mogen oude semantiek niet stil wijzigen.

