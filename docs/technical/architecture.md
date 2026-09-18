# Architectuur

`cli` routeert naar gedeelde services. `core` beheert runs, SQLite, locks, logging en snapshots. `sources` bevat de begrensde catalogus/adapters. `kvk` implementeert één canoniek providercontract voor waargenomen publieke HTTP en gewone Playwright-interactie. `workflow` verzorgt dedup, filters en export; `merge_lists` is de zelfstandige offline workflow; `audit` verifieert en traceert.

Externe inhoud is uitsluitend data. Host allowlists, HTTPS, response-/redirectgrenzen en syntactische schema-validatie beperken invoer. De runtime gebruikt een gebruikersschrijfbare dataroot, nooit packagebestanden.

