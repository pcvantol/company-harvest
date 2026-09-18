# Bron- en KVK-providers

De IND-adapter leest het actuele openbare register Arbeid. De Wikidata-adapter gebruikt deterministische, begrensde SPARQL-paginering voor Nederlandse organisaties met KVK-property; de veiligheidslimiet blokkeert een schijnbaar volledig resultaat. `sources collect` hergebruikt standaard het laatste complete bronartefact en `--refresh` maakt en registreert nieuwe evidence.

`sources import` voegt lokale CSV-, TSV-, XLSX- en HTML-tabellen met expliciete naam- en KVK-kolommen toe. Iedere input krijgt eerst een unieke evidence-snapshot. Alle bronnen blijven biased en vormen geen gegarandeerd volledige populatie.

KVK gebruikt uitsluitend de functionaliteit achter `https://www.kvk.nl/zoeken/`. Op 2026-09-18 is tijdens een gewone naamzoekactie de publieke GET-route `https://web-api.kvk.nl/zoeken/v3/search` waargenomen, inclusief de door de frontend meegegeven publieke profiel-ID en parameters. Rechtstreekse reproductie en browserflow zijn elk met één kandidaat bewezen. `public-browser` blijft technische fallback. 401/403/429, CAPTCHA, actieve cooldown en toegangseisen veroorzaken stop/pauze, geen transportpendelen. De implementatie vraagt geen KVK-key en bevat geen geldbudget. Response-evidence wordt als gehasht audit-artefact geregistreerd.

Geraadpleegd 2026-09-18: KVK-gebruikersvoorwaarden (bijgewerkt 2026-06-17) vermelden aanvullende voorwaarden voor grootschalig opvragen/hergebruik; IND meldt maandelijkse actualisatie en op 2026-09-03 bijgewerkte data; Playwright documenteert response-observatie. Live veldsemantiek blijft `UNKNOWN` totdat gemeten.
