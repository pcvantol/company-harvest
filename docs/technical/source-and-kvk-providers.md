# Bron- en KVK-providers

De IND-adapter leest het actuele openbare register Arbeid. De Wikidata-adapter gebruikt deterministische, begrensde SPARQL-paginering voor Nederlandse organisaties met KVK-property; de veiligheidslimiet blokkeert een schijnbaar volledig resultaat. `sources collect` hergebruikt standaard het laatste complete bronartefact en `--refresh` maakt en registreert nieuwe evidence.

`sources import` voegt lokale CSV-, TSV-, XLSX- en HTML-tabellen met een expliciete naamkolom en optionele KVK-kolom toe. Iedere input krijgt eerst een unieke evidence-snapshot. Ontbrekende of ongeldige KVK-waarden blijven als kandidaten bewaard en worden afzonderlijk gemeten. Alle bronnen blijven biased en vormen geen gegarandeerd volledige populatie.

De broninventaris gebruikt catalogusschema 2. Legacy inventarissen worden bij lezen naar dit schema genormaliseerd zonder bestaande waarden te verliezen. Live aantallen en overlap blijven leeg of `NOT_MEASURED` totdat een werkelijke meting ze onderbouwt.

KVK gebruikt uitsluitend de functionaliteit achter `https://www.kvk.nl/zoeken/`. Op 2026-09-18 is tijdens een gewone naamzoekactie de publieke GET-route `https://web-api.kvk.nl/zoeken/v3/search` waargenomen, inclusief de door de frontend meegegeven publieke profiel-ID en parameters. Rechtstreekse reproductie en browserflow zijn elk met één kandidaat bewezen. `public-browser` blijft technische fallback. 401/403/429, CAPTCHA, actieve cooldown en toegangseisen veroorzaken stop/pauze, geen transportpendelen. De implementatie vraagt geen KVK-key en bevat geen geldbudget. Response-evidence wordt als gehasht audit-artefact geregistreerd.

Zowel de directe bron-/KVK-clients als de Playwright-browsercontext gebruiken `company-lookup/0.1`. De browsertest controleert de contextoptie expliciet; er wordt geen persoonlijke URL of gebruikersnaam meegestuurd.

Geraadpleegd 2026-09-18: KVK-gebruikersvoorwaarden (bijgewerkt 2026-06-17) vermelden aanvullende voorwaarden voor grootschalig opvragen/hergebruik; IND meldt maandelijkse actualisatie en op 2026-09-03 bijgewerkte data; Playwright documenteert response-observatie. Live veldsemantiek blijft `UNKNOWN` totdat gemeten.
