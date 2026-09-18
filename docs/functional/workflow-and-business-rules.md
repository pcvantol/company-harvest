# Workflow en bedrijfsregels

1. De broncatalogus legt eigenaar, URL, voorwaarden, bias en meetstatus vast.
2. Per bron blijft ruwe herkomst behouden; ontbrekende verrijking blijft leeg.
3. Pre-KVK-deduplicatie is conservatief. KVK wordt pas na verificatie de definitieve sleutel.
4. De publieke zoekfunctie wordt sequentieel bevraagd. HTTP mag alleen na observatie van de gewone frontend; Playwright is technische fallback, nooit omzeiling.
5. De canonieke lijst bevat alleen een onderbouwde Nederlandse vestiging en uniek geldig nummer.
6. Alleen geverifieerde rechtsvormwaarden bepalen uitsluiting; onbekend gaat naar review.
7. Alleen expliciete ondernemingsstatus bepaalt actief/inactief; onbekend gaat naar review.
8. Selectie boven het doel gebruikt een stabiele hash vóór alfabetische sortering. Partiële export vereist toestemming.
9. Offline merge valideert syntaxis, groepeert op KVK, bewaart naam-/veldconflicten en verifieert niet opnieuw.

