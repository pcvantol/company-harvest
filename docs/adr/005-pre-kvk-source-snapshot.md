# ADR-005 — Brede bronmomentopname vóór KVK

Status: Accepted (2026-09-19). Requirements: CH-PREKVK-001..003,
CH-DATA-001/004, CH-RES-001, RD-001/004/006/007.

De volledige pre-KVK-master wordt pas gepubliceerd wanneer de kandidaatlaag
van alle vijf actieve bronnen full-scope is ingenomen, de originele evidence
en bronoutputs byte-gebonden zijn en input→lijst-closure sluit. KVK-hints uit
een bron blijven hints, geen geverifieerde ondernemingssleutel. Alleen een
identieke genormaliseerde naam met dezelfde geldige directe KVK-hint wordt
automatisch samengevoegd. Naamgenoten zonder hint blijven gescheiden;
conflicterende hints blijven zichtbaar en vereisen review. Iedere lijstregel
bevat alle bijbehorende oorspronkelijke bronpayloads en bewijsverwijzingen.

Bij een ontbrekende of geblokkeerde bron mag geen vijfbronnenmaster ontstaan.
Een afzonderlijke offline preview van alleen aantoonbaar complete bronnen
is toegestaan, mits elke rij `BLOCKED_SOURCE_INCOMPLETE` draagt, het rapport
de uitgesloten bron noemt en de run geblokkeerd blijft. Een preview is nooit
een KVK-wachtrij. Een expliciete latere beslissing is nodig om een
providerblokkade opnieuw te benaderen. R7 blijft geparkeerd.

De Wikidata-SPARQL-route heeft geen transactionele snapshotgarantie:
zelfs een korte slotpagina bewijst slechts de volledige doorloop van de
waargenomen endpointantwoorden binnen het geregistreerde tijdvenster.
Deze beperking hoort bij iedere claim over volledigheid van die bron.
