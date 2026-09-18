# Datadictionary

| Veld | Betekenis |
|---|---|
| Bedrijfsnaam | Canonieke of expliciet gekozen weergavenaam; tekst. |
| KVK-nummer | Exact acht ASCII-cijfers; tekst, nooit automatisch aangevuld. |
| candidate_id | Stabiele hash van bronidentiteit voor requestjournalering. |
| source_relations | JSON-cel met bron-ID, URL en oorspronkelijke rij. |
| response_json | Verliesvrije lokaal bewaarde relevante providerresponse. |
| raw_legal_form/raw_status | Ongewijzigde publieke providerwaarden. |
| checked_at | Werkelijk verificatiemoment; cachegebruik verandert dit niet. |
| verification_status | Bij merge altijd `UNCONFIRMED_IMPORTED`, tenzij bestaand bewijs apart herleidbaar is. |

CSV-uitvoer is UTF-8, tabgescheiden en correct gequote. Leeg betekent onbekend. Logbestanden bevatten IDs, geen volledige responses. De minimale spreadsheet heeft exact de kolommen `Bedrijfsnaam`, `KVK-nummer`.

