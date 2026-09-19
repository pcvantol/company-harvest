# Versies en migraties

Packageversie is gezaghebbend in `pyproject.toml`; CLI/changelog/tag gebruiken dezelfde waarde. Vanaf 1.0.0 verhogen incompatibele publieke contractwijzigingen MAJOR, nieuwe compatibele functies MINOR en fixes PATCH. Tool-, run-/databaseschema-, export- en providerschemaversies zijn afzonderlijk.

De actuele **4.0.0-broncode** heet Company Lookup. Installatie- en
importnamen zijn `company-lookup` en `company_lookup`; het consolecommando
is `company-lookup`. Dit is een MAJOR-wijziging ten opzichte van de oude
`company-harvest`-distributie en de lokaal gebouwde 3.1.0-wheel. De nieuwe
omgevingsvariabele heet `COMPANY_LOOKUP_DATA_DIR`; zonder `--data-dir` of die
variabele is de standaardmap nu `~/.local/share/company-lookup`. Oude
installaties, snelkoppelingen en scripts schakelen niet automatisch over.
Zet de nieuwe variabele bewust op de bestaande datamap of geef het absolute
oude runpad met `--run-dir` mee; de tool verplaatst of herschrijft bestaande
runs niet. Installeer in een **nieuwe** virtuele omgeving om de oude en
nieuwe distributies niet te mengen. Bestaande run-/database-/outputschema's
blijven leesbaar via een expliciet pad, onder de gewone integriteitschecks.
Er is nog geen publieke 4.0.0-wheel of migratie van historische releaseassets.

De voorgaande bronversie **3.1.0** was een niet gepubliceerde compatibele
minorversie boven de publieke 3.0.0-wheel. Zij bevat de eveneens nog niet
gepubliceerde 3.0.1-parserfix: de begrensde CSV-veldparser en foutmelding wijzigen,
en drie in een begrensde live proef waargenomen zakelijke KVK-veldpaden
worden gericht toegelaten in de lichte export. Ontbrekende optionele
exportvelden worden voor de eindaudit expliciet leeg geprojecteerd. Run-, database- en
outputsetschema blijven gelijk. Een v3.0.0-run
die vóór KVK op de veldgrens stopte kan met 3.0.1 dezelfde runmap hervatten
na de gebruikelijke hash-/configvalidatie; maak geen nieuwe run als omweg
voor een echte KVK-toegangsblokkade. Zie [ADR-018](../adr/018-bounded-csv-field-size.md).
Nieuw in de 3.1.0-broncode is `run pre-kvk`, een additieve eencommando-route
die vóór KVK stopt en dezelfde run-/artefactstructuur gebruikt. Er is geen
schema- of migratiewijziging; de 3.1.0-wheel is alleen lokaal gebouwd en
op import/CLI-help gecontroleerd, niet gepubliceerd of als volledige
releasekandidaat gekwalificeerd. Zie [ADR-019](../adr/019-one-command-pre-kvk.md).

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
