# ADR-016 — Nummer-only KVK-check en holding als reviewlabel

Status: Accepted (2026-09-19). Requirements: CH-PREKVK-007/008/009,
CH-KVK-001/003, CH-DATA-004.

Voor nieuwe runs is `HOLDING_OR_MANAGEMENT` niet langer een toelatingsfilter.
Een naamtreffer wordt als reviewlabel in een afzonderlijke TSV vastgelegd met
kandidaat-ID en directe KVK-hint. De filtermetadata bindt de letterlijke regex,
het aantal labelrijen, bestandsgrootte en SHA-256. Een holding die om een andere
reden niet voldoet, blijft uitgesloten met die andere reden; een holding met
geldige hint en zonder andere uitsluitreden mag door naar de KVK-check. Het
label is via `candidate_id` te koppelen aan de volledige eindlijst; de minimale
leveringslijst houdt alleen naam en KVK-nummer. De historische vierbronnenmeting
onder filterversie 7 blijft een meting van de oude regel, niet van de nieuwe.
Een latere [ADR-017](017-light-business-export.md) voegt daarnaast een
afzonderlijke zakelijke lichte Excel toe zonder kandidaat-ID; deze vervangt
de minimale of volledige auditlijst niet.

De pre-KVK-check eist voortaan exact acht ASCII-cijfers als directe bronhint.
Ontbreekt die, dan wordt geen verzoek op naam verstuurd: de bestaande
`NO_DIRECT_KVK_HINT`-regel houdt het record buiten de huidige wachtrij. De
publieke zoekroute krijgt het nummer als zoekterm en het journal registreert
datzelfde nummer. Een resultaat telt alleen als geverifieerde match wanneer
het teruggegeven KVK-nummer exact gelijk is; de bedrijfsnaam is geen
identiteitsvoorwaarde. Rechtsvorm en status blijven apart te beoordelen:
ontbrekende/onbekende waarden worden niet positief geïnterpreteerd. Bestaande
toegangsblokkades, pacing en expliciete scope blijven ongewijzigd.

Ook de oudere `kvk resolve`-route stuurt voortaan alleen een geldig
bron-KVK-nummer; kandidaten zonder hint krijgen een expliciete onopgeloste
uitkomst zonder GET. De publieke HTTP-, browser- en autoprovider weigeren
niet-numerieke zoektermen al vóór netwerk/browseracties. De historische
R8-pilot selecteert juist kandidaten zonder hint; een nieuwe pilot kan nog
offline bronkoppelingen beoordelen, maar doet geen publieke naamzoeking meer.
Overige pilotrijen krijgen `NO_DIRECT_KVK_HINT` als afgeronde offline uitkomst,
met lege journalquery en nul live verzoeken. Oude naamquery-uitkomsten worden
door een gewijzigde fingerprint niet stil hergebruikt. Dit vervangt de oude
live R8-verwachting, zonder historische artefacten te wijzigen.

Een screenshot van de frontend toont nummerzoeking met een resultaat. Dat
bewijst de gebruikersfunctie, maar niet dat de directe Web-API-route met
nummerparameter live werkt of de gewenste velden steeds teruggeeft. Dit
besluit is daarom offline getest met de bestaande provider en synthetische
responses; live nummerzoeking staat als `NOT_TESTED` open. Geen automatische
productieharvest of omzeiling van een eerdere blokkade.
