# ADR-007 — Reproduceerbare toelatingsfilter vóór de KVK-batch

Status: Accepted (2026-09-19). Requirements: CH-PREKVK-007/008,
CH-DATA-004, CH-RES-002, RD-006/007/009.

De vierbronnenmaster blijft een verliesvrije, niet-gefilterde verzameling.
Een aparte offline overgang maakt daaruit een KVK-geschikte lijst en een
uitsluitingsledger. De filter kiest op directe KVK-hint, volledige ANBI- en
DUO-bronrelaties, conflictreview en zorgvuldig afgebakende naamtermen voor
holdings/beheer(s)maatschappijen en naamvorm `Beheer B.V./N.V.`,
stichtingen/verenigingen inclusief Nederlandse samenstellingen op deze
eindwoorden, scholen (ook samengestelde `…school`-eindwoorden),
banken via zelfstandige woorden of benoemde banktypen (niet ieder `…bank`),
pensioen-/beleggingsfondsen en kerken via expliciete kerksoorten (niet
iedere plaatsnaam op `…kerk`),
overige religieuze organisaties en politieke
partijen. `NO_DIRECT_KVK_HINT` betekent uitsluitend *geen bronhint*, niet
*geen inschrijving*. De filterclassificatie is heuristisch en geen juridisch
oordeel over ondernemingsvorm of ANBI-status buiten de ANBI-bron. Het woord
`vereniging` is opgenomen omdat de aangeleverde screenshot een historische
vereniging als ongewenst voorbeeld toont. Dit raakt ook 410 anders geschikte
rijen en is daarom bewust zichtbaar, omkeerbaar en herzienbaar.

De lokale JSON-metadata benoemt regelversie, criteria en de letterlijk
uitgevoerde reguliere expressies inclusief hoofdlettervlag,
input-/outputpaden en SHA-256, aantallen en tellingen per primaire én alle
overlappende redenen. De TSV-ledger bevat elke uitgesloten kandidaat-ID,
naam, bron-IDs en alle redenen; de volledige rij/payload blijft in de
master. Masterrijen = geschikte rijen + uitgesloten rijen. Daardoor kan een
eigenaar later criteria verruimen en dezelfde bronmomentopname hergebruiken
zonder stil verlies.

`FUND_OR_EQUITY_NAME` is bewust een *naamsignaal*: ook een los `fonds`,
`fund` of `equity` kan een andere organisatievorm aanduiden. De filter
prioriteert de huidige KVK-batch en stelt geen beleggingsfonds vast.

De KVK-batch leest uitsluitend een COMPLETE-geregistreerde filterset die
byte-identiek en regelversiegebonden is aan de actuele master. Bij een
ontbrekende/gewijzigde set faalt zij vóór het netwerk. Een bestaande
requestjournal verhindert herfilteren zonder expliciet migratiebesluit.
Dit is een toelatingsregel voor de huidige kleine vierbronnen-KVK-route,
geen terugwerkende wijziging van de R8-pilot of een algemeen verbod op
latere no-hint-matching. RD-001/R7 blijven bulk-KVK blokkeren.
