# Workflow en bedrijfsregels

1. Broncatalogusschema 2 legt eigenaar, bronfamilie, URL, toegang, voorwaarden, actualiteit, identifierprofiel, bias, herkomstkwaliteit, kandidaatlaag en meetstatus vast.
2. Per bron blijft ruwe herkomst behouden. Een ontbrekend of ongeldig initieel KVK-nummer blijft expliciet `MISSING` of `INVALID` en verwijdert de kandidaat niet.
3. Pre-KVK-deduplicatie is conservatief. Naam alleen voegt nooit records samen; identifierloze/ongeldige naamgenoten blijven apart en verschillende geldige KVK-hints bij dezelfde naam worden conflict. KVK wordt pas na verificatie de definitieve sleutel.
4. De publieke zoekfunctie wordt sequentieel en uitsluitend met een geldige directe KVK-bronhint bevraagd. De teruggegeven nummerwaarde moet exact overeenkomen; een afwijkende naam verhindert die match niet. Zonder hint gaat geen naamverzoek naar KVK. HTTP mag alleen na observatie van de gewone frontend; Playwright is technische fallback, nooit omzeiling.
5. De canonieke lijst bevat alleen een onderbouwde Nederlandse vestiging en uniek geldig nummer.
6. Alleen geverifieerde rechtsvormwaarden bepalen uitsluiting; onbekend gaat naar review.
7. Alleen expliciete ondernemingsstatus bepaalt actief/inactief; onbekend gaat naar review.
8. Alle actieve, geverifieerde bedrijven uit de gekozen KVK-scope worden geleverd, alfabetisch gepresenteerd. Een doelgetal of exportlimiet kapt niets af. Partiële export wegens overgeslagen/onopgeloste KVK-kandidaten blijft expliciet gemarkeerd en vereist waar nodig toestemming.
9. Offline merge valideert syntaxis, groepeert op KVK, bewaart naam-/veldconflicten en verifieert niet opnieuw.
10. Outcome-rapportage telt de laatste complete artefacten per bron en sluit iedere beschikbare overgang afzonderlijk: raw→dedup, kandidaat→KVK-terminal, match→canoniek, rechtsvorm, status en delivery/reserve. Een gedeeltelijke, open of nog niet beschikbare closure wordt nooit als volledig gesloten gepresenteerd.
11. Een nieuwe pre-KVK-master vereist aantoonbaar volledige inname van IND, GLEIF, ANBI, DUO en TenderNed. Oudere runs met gebonden vierbronnenscope blijven hervatbaar. Wikidata maakt geen deel meer uit van deze route. Een onvolledig bronresultaat blijft voor KVK geblokkeerd; de historische vijfbronnenpreview met Wikidata is geen actuele master.
12. Een aparte, regelversiegebonden filter splitst de volledige master in KVK-geschikte kandidaten en een lokale uitsluitingsledger. Geen directe KVK-hint, ANBI-/DUO-bronrelatie, bronconflict of expliciet niet-gewenst naamtype betekent uitsluiting van deze KVK-wachtrij, niet verwijdering uit de bronlaag. `HOLDING_OR_MANAGEMENT` is alleen een reviewlabel en sluit op zichzelf niet uit.
13. Iedere uitsluiting bewaart kandidaat-ID en alle redenen; een aparte label-TSV bewaart kandidaat-ID en holding-signaal. De metadata legt exacte criteria, aantallen en hashes voor alle drie bestanden vast. Alleen de actuele COMPLETE-gefilterde lijst mag in een expliciete KVK-batch worden gelezen.
14. Stap 8 schrijft naast de minimale en volledige auditexport een lichte
    zakelijke CSV/XLSX. De KVK-velden komen uit de exact gematchte publieke
    zoekhit; in de geïntegreerde pre-KVK-route komen website en sector
    herkenbaar uit de eerste niet-lege samengevoegde bronwaarde. Een bronjoin vereist kandidaat-ID en exact
    hetzelfde KVK-nummer. `response_json`, `source_relations` en technische
    metadata staan alleen in de volledige auditexport. Onbekende nieuwe
    responsvelden met inhoud stoppen de lichte export tot review. Het schema-2-manifest
    bindt zeven bestanden; oude schema-1-sets met vijf blijven auditbaar.
