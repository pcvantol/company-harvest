# ADR-006 — Vierbronnenmaster in de tool, KVK uitsluitend in kleine batches

Status: Accepted (2026-09-19). Requirements: CH-PREKVK-004..006,
CH-DATA-001/004, CH-KVK-001/003, CH-RES-002, RD-001/004/008.

De gebruiker heeft Wikidata voor deze workflow uitgesloten. De tool verzamelt
daarom uitsluitend IND, GLEIF, ANBI en DUO in de nieuwe `pre_kvk_master`.
Ieder bronartefact moet volledige scope, intacte geregistreerde evidence en
gesloten aantallen aantonen. Een ontbrekende of beperkte bron verhindert de
master. Een directe KVK-hint blijft ongeverifieerd; onzekere samenvoegingen
blijven aparte kandidaten of vereisen review. Historische vijfbronnenreviews
en de geblokkeerde preview blijven als auditgeschiedenis bewaard.

De master werd oorspronkelijk door een expliciete kleine KVK-stap gelezen.
ADR-007 vervangt dit invoerpad: voortaan leest de stap uitsluitend de
filterset die aan de volledige master is gebonden. De KVK-stap gebruikt
alleen de waargenomen publieke frontend-HTTP-route, maximaal tien nieuwe
kandidaten per opdracht en minimaal twee seconden tussen requests/pagina's.
De tool bewaart het starttijdstip vóór iedere GET in een lokaal gedeeld
pacingjournal, zodat ook twee directe opeenvolgende CLI-batches de interval
respecteren.
De oorspronkelijke naam-zonder-hint-matchvoorwaarde blijft historisch in de
matchingcode, maar ADR-007 laat zulke kandidaten in deze batchroute niet meer
door. Bronconflicten worden evenmin bevraagd. De requestjournal verhindert
stil opnieuw versturen, en toegangs-/rate-/netwerkfouten stoppen de batch.
De outputsoorten dragen status `PARTIAL` en zijn geen input voor canonieke
consolidatie of export. Een volledige frontenddoorloop is niet vrijgegeven.

De reden voor deze grens is zowel technisch als gebruiksrechtelijk: een
bereikbare openbare zoekroute is geen bewijs voor systematische bulktoegang.
De [KVK-gebruikersvoorwaarden](https://www.kvk.nl/over-het-handelsregister/gebruikersvoorwaarden-handelsregistergegevens/)
vermelden aanvullende voorwaarden voor grootschalig gebruik; de
[gepubliceerde gebruiksvoorwaarden](https://developers.kvk.nl/cms/api/uploads/Gebruiksvoorwaarden_Verstrekking_en_Gebruik_Handelsregistergegevens.pdf)
behandelen geautomatiseerd systematisch uitlezen afzonderlijk. Dit is een
operationele gate, geen definitieve juridische beoordeling.
R7 blijft daarvoor geparkeerd, in overeenstemming met RD-001 en RD-004.
