# ADR-008 — Hervatbare publieke frontend-KVK-check

Status: Accepted (2026-09-19). Requirements: CH-PREKVK-009,
CH-KVK-001/003, CH-RES-002, CH-DATA-004, RD-001/004/008.

De eigenaar heeft op 2026-09-19 expliciet de publieke Web-API-route die de
KVK-frontend gebruikt aangewezen voor een beheerste, eventueel langlopende
controle. Dit is **niet** de officiële API-key-route en introduceert geen key,
betaalde API of omzeiling. De eerdere grens van tien verzoeken per opdracht
blijft als kleine batch bestaan, maar geldt niet meer voor de nieuwe,
afzonderlijk te kiezen `kvk pre-kvk-run`.

De langlopende opdracht vraagt een expliciete scope: `--max-requests N` of
`--until-complete`. Zij gebruikt precies één zoekpagina en één poging per
kandidaat, de bestaande hostallowlist, de providerlock, de cooldown en het
globale persistente pacingjournal. Verzoekstarts liggen minimaal twee
seconden uiteen. HTTP 401/403/429 stopt onmiddellijk, ook na een CLI-herstart;
er is geen browserrotatie of nieuwe run als automatische fallback. Andere
technische fouten stoppen de huidige sessie en blijven als onopgelost record.

`state.sqlite3` is de bron van waarheid per kandidaat. Iedere verzoekstart
wordt vóór de GET als `IN_FLIGHT` vastgelegd; een niet duurzaam afgeronde
aanroep wordt bij hervatten `SENT_OUTCOME_UNKNOWN` en nooit stil opnieuw
verstuurd. Een atomisch `pre_kvk_kvk_progress.json` toont inputhash,
voortgang, toestand en resterend aantal. Match-/unresolved-TSV's worden na
iedere uitkomst duurzaam aangevuld en bij iedere herstart uit de journal
gereconstrueerd. Alle bestanden blijven uitsluitend lokaal in de runmap.

Pas wanneer alle gefilterde kandidaten een terminale journaluitkomst hebben,
de inputhash nog klopt en er geen actieve toegangs-/rateblokkade is, worden
de twee TSV's als `COMPLETE` voor consolidatie geregistreerd. `COMPLETE`
betekent hier een gesloten kandidaatpartitie, niet dat iedere kandidaat
daadwerkelijk een KVK-match kreeg. Ook onzekere of technisch mislukte
verzoeken staan expliciet en niet-hervatbaar in `kvk_unresolved`; zij worden
niet automatisch herhaald. Een export met onopgeloste rijen vergt de
bestaande expliciete `--allow-partial`-keuze en kwaliteitscontrole.
Een bereikbare publieke route of toestemming van de eigenaar is op zichzelf
geen vaststelling over externe gebruiksvoorwaarden, schaalgeschiktheid of de
juistheid/volledigheid van status- en rechtsvormvelden. Er wordt in deze
codewijziging geen productieharvest automatisch gestart.
