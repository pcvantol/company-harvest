# Workflow en bedrijfsregels

1. Broncatalogusschema 2 legt eigenaar, bronfamilie, URL, toegang, voorwaarden, actualiteit, identifierprofiel, bias, herkomstkwaliteit, kandidaatlaag en meetstatus vast.
2. Per bron blijft ruwe herkomst behouden. Een ontbrekend of ongeldig initieel KVK-nummer blijft expliciet `MISSING` of `INVALID` en verwijdert de kandidaat niet.
3. Pre-KVK-deduplicatie is conservatief. Naam alleen voegt nooit records samen; identifierloze/ongeldige naamgenoten blijven apart en verschillende geldige KVK-hints bij dezelfde naam worden conflict. KVK wordt pas na verificatie de definitieve sleutel.
4. De publieke zoekfunctie wordt sequentieel bevraagd. HTTP mag alleen na observatie van de gewone frontend; Playwright is technische fallback, nooit omzeiling.
5. De canonieke lijst bevat alleen een onderbouwde Nederlandse vestiging en uniek geldig nummer.
6. Alleen geverifieerde rechtsvormwaarden bepalen uitsluiting; onbekend gaat naar review.
7. Alleen expliciete ondernemingsstatus bepaalt actief/inactief; onbekend gaat naar review.
8. Selectie boven het doel gebruikt een stabiele hash vóór alfabetische sortering. Partiële export vereist toestemming.
9. Offline merge valideert syntaxis, groepeert op KVK, bewaart naam-/veldconflicten en verifieert niet opnieuw.
10. Outcome-rapportage telt de laatste complete artefacten per bron en sluit iedere beschikbare overgang afzonderlijk: raw→dedup, kandidaat→KVK-terminal, match→canoniek, rechtsvorm, status en delivery/reserve. Een gedeeltelijke, open of nog niet beschikbare closure wordt nooit als volledig gesloten gepresenteerd.
