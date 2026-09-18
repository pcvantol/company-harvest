# Blijvende uitvoerregels

Deze repository volgt het contract in `docs/prompts/20260918T103746Z_ch-2026-09-18-001_request.md`.

- Werk rechtstreeks op `main`; geen force-push, destructieve reset of PR zonder nieuwe opdracht.
- Registreer elke hoofdprompt met stabiele execution-ID, plan, resultaat, requirementrelaties en versie-impact.
- Gebruik een echte onafhankelijke read-only subagentreview per hoofdprompt en los blokkerende bevindingen op.
- Houd echte bedrijven, imports, runs, logs, cookies, browserbewijs en secrets lokaal en buiten Git/assets.
- Voer geen productieharvest automatisch uit; live tests zijn klein, sequentieel en respecteren blokkades.
- Bouw uitsluitend op de publieke KVK-frontend: waargenomen HTTP eerst, Playwright als technische fallback; nooit de betaalde API of omzeiling.
- Bewijs capabilities; markeer onbekend, niet getest en geblokkeerd expliciet.
- Eis strikt meer dan 80% statementcoverage per eigen uitvoerbaar Pythonbestand plus kritieke branchtests.
- Update Nederlandse functionele/technische documentatie, ADR's, traceability, changelog en releasebewijs.
- Publiceer alleen gekwalificeerde, gescande, byte-identieke assets; nooit een bestaande releaseversie overschrijven.
- Een geïnstalleerde wheel moet zonder checkout, Git, GitHub-login of agent werken.

