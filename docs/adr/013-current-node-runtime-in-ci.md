# ADR-013 — Actuele Node-runtime voor officiële CI-acties

Status: Accepted. Requirements: CH-GOV-001/002.

De Python-tool gebruikt Node niet als applicatieruntime. De GitHub Actions-
workflow voert wel JavaScript-acties uit. `actions/checkout@v7` en
`actions/setup-python@v7` zijn op 19 september 2026 de actuele majorversies;
hun `action.yml` specificeert `node24`. De oude v4/v5-verwijzingen met
Node 20-waarschuwing vervallen. `@v7` volgt correcties binnen major v7.

De bestaande matrix (Python 3.14, macOS/Windows) en de offline E2E-poort
blijven gelijk. Een statische workflowtest bewaakt de verwijzingen en matrix;
de twee gehoste CI-jobs bewijzen uitvoerbaarheid. Dit besluit installeert
geen aparte Node-versie voor de Python-code.

Bronnen: [checkout v7-action](https://github.com/actions/checkout/blob/v7/action.yml),
[setup-python v7-action](https://github.com/actions/setup-python/blob/v7/action.yml),
[checkout releases](https://github.com/actions/checkout/releases),
[setup-python releases](https://github.com/actions/setup-python/releases).
