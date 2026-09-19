# ADR-012 — Veilige CLI-voortgang op stderr

Status: Accepted (2026-09-19). Execution ID: CH-2026-09-19-026.

Alle CLI-commandofamilies tonen een menselijk start-, fase-, resultaat- en
foutsignaal. De bestaande machineleesbare stdout blijft ongewijzigd: scripts
kunnen bijvoorbeeld `run init --print-path` blijven opvangen. De nieuwe
voortgang gaat naar stderr, ook als stderr geen terminal is. ANSI-kleur wordt
alleen op terminals getoond of bij `FORCE_COLOR=1`; `NO_COLOR` wint altijd.

Een expliciete allowlist bepaalt welke numerieke/boolse resultaatvelden en
run-events zichtbaar zijn. Bedrijfsnamen, KVK-nummers, zoekvragen, headers,
responses, secrets en recordinhoud worden niet naar de voortgangsstroom
gekopieerd. De E2E-route toont fasegrenzen voor broncatalogus, vier bronnen,
master/filter, KVK-cohort en -check, consolidatie, filters, export en audit.
De langlopende KVK-route toont alleen aantallen en checkpointstatus: bij een
queue van maximaal 10 na ieder verzoek, maximaal 100 na iedere 10, daarboven
na iedere 100; het eerste, laatste en mislukte verzoek verschijnen altijd.

Dit is presentatie boven bestaande diensten en journalen. Er zijn geen
wijzigingen aan KVK-requestpacing, resume, outputschema, exitcodes of
runmetadata. De expliciet opgevraagde gestructureerde resultaten op stdout
(waaronder `audit trace`) houden hun oude contract en zijn **geen**
voortgangslog. CLI-diagnostiek bij bekende fouten wordt tot een veilige
categorie en exitcode beperkt; bij parserfouten wordt hoogstens een herkende
optienaam getoond. Onverwachte uitzonderingen behouden shell-exitcode 1 en
tonen alleen het type, geen traceback of recordinhoud.
