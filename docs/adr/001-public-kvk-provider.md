# ADR-001 — Publieke KVK-provider en browserfallback

Status: Accepted. Requirements: CH-KVK-001..006.

Context: gratis publieke frontend is vereist; een endpoint is vooraf onbewezen. Alternatieven waren betaalde API, endpoint raden of frontendobservatie. Keuze: observeer gewone Playwright-interactie; gebruik alleen waargenomen HTTP, anders browser. 429/blokkade/CAPTCHA stopt beide routes. Consequentie: velden/capaciteit kunnen onbekend blijven en Chromium is voor fallback apart nodig.

Roadmapnotitie 2026-09-18: de bestaande keuze blijft de huidige implementatiebasis, maar migratie naar een andere KVK-route en bulkgebruik zijn op expliciet gebruikersbesluit `PARKED`. Alleen begrensde smokes blijven toegestaan. Zie [RD-001 en R7](../../ROADMAP.md#rd-001--kvk-routemigratie-is-geparkeerd). Dit is nog geen vervanging van deze ADR; bij hervatting en een andere providerkeuze is een nieuwe, superseding ADR vereist.
