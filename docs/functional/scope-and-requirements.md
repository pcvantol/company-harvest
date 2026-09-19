# Scope en requirements

Doel is circa 10.000 unieke, bij KVK gecontroleerde, actieve Nederlandse ondernemingen zonder bevestigde eenmanszaken. Rechtsvorm, Nederlandse vestiging en status zijn definitieve verificatiefilters; commerciële geschiktheid, medewerkers en sector zijn geen eindselectiefilters. Daarvóór beperkt een afzonderlijke heuristische pre-KVK-filter welke bronrecords naar de KVK-check gaan, zonder de brede bronmaster te verwijderen.

HARVEST bestaat uit bronnen inventariseren, bronrecords verzamelen, voorzichtig dedupliceren, via de publieke KVK-frontend verifiëren, canoniek consolideren, eenmanszaken uitsluiten, actieve ondernemingen selecteren en exporteren. MERGE_LISTS combineert twee bestaande lijsten offline zonder nieuwe verificatie of filters.

De actuele KVK-check vraagt uitsluitend een geldig direct bron-KVK-nummer
op. Een kandidaat zonder die hint blijft in de brede bronmaster, maar komt
niet in deze KVK-wachtrij. Nieuwe runs combineren vijf bronfamilies (IND,
GLEIF, ANBI, DUO en TenderNed); oudere vierbronnenruns houden hun gebonden
scope. De eindoutput heeft een minimale, een lichte zakelijke en een volledige
auditvariant. De lichte variant bevat bronwebsite/-sector als onbevestigde
bronvelden; zie [het outputcontract](output-files.md).

Requirement-ID's en bewijs staan in de [traceabilitymatrix](../traceability/requirements-matrix.md). `UNKNOWN`, technische fouten en niet-verwerkte kandidaten worden nooit als geldige eindbedrijven behandeld. Een onderdoel mag eerlijk worden opgeleverd; fictieve aanvulling niet.

De kleine publieke KVK-frontendmetingen leveren hoogstens voorlopig
identiteitsbewijs. De geïsoleerde [tien-querymeting van 2026-09-19](../measurements/20260919-kvk-frontend-batch10.md)
kwalificeert geen 500-recordbulk, definitieve rechtsvorm-/statusverificatie of
productieharvest. R7 staat in de roadmap op `IN_PROGRESS`; de volledige
productie- en gebruiksgates zijn nog open. De migratie naar de officiële
betaalde API is afzonderlijk geparkeerd.
