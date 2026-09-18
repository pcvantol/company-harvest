# ADR-001 — Publieke KVK-provider en browserfallback

Status: Accepted. Requirements: CH-KVK-001..006.

Context: gratis publieke frontend is vereist; een endpoint is vooraf onbewezen. Alternatieven waren betaalde API, endpoint raden of frontendobservatie. Keuze: observeer gewone Playwright-interactie; gebruik alleen waargenomen HTTP, anders browser. 429/blokkade/CAPTCHA stopt beide routes. Consequentie: velden/capaciteit kunnen onbekend blijven en Chromium is voor fallback apart nodig.

