# Eenmalige offline pre-KVK-filtermeting (2026-09-19)

Execution ID: CH-2026-09-19-011. De bestaande volledige vierbronnenmaster
is lokaal, zonder bron- of KVK-netwerkverkeer, door regelversie
`pre-kvk-eligibility-7` verwerkt. Ruwe namen en rijdata staan uitsluitend
in de genegeerde lokale run.

| Overgang | Aantal |
|---|---:|
| Masterkandidaten | 289.916 |
| KVK-geschikt na filter | 119.801 |
| Uitgesloten met itemniveau-redenen | 170.115 |
| Sluiting | 289.916 = 119.801 + 170.115 |
| KVK-verzoeken tijdens deze uitvoering | 0 |

De tellingen hieronder zijn *overlappende* redenen: één kandidaat kan meer
dan één reden hebben. Daarom mogen de kolommen niet worden opgeteld tot het
uitsluitingstotaal. De primaire reden per kandidaat is apart in de lokale
metadata beschikbaar.

| Reden | Alle treffers |
|---|---:|
| ANBI-bron | 54.922 |
| DUO-onderwijsbron | 27.600 |
| Geen directe KVK-bronhint | 82.376 |
| Bronconflict/review | 8.170 |
| Holding/beheer(s)maatschappij/Beheer B.V./N.V. | 69.131 |
| Stichting/vereniging inclusief samenstellingen | 58.683 |
| School/onderwijs/universiteit | 11.899 |
| Bank | 265 |
| Pensioenfonds | 592 |
| Fonds/fund/equity-naamsignaal, niet geverifieerd | 6.712 |
| Religieuze organisatie | 6.406 |
| Politieke partij | 204 |

Alle 54.922 ANBI-kandidaten staan ook in de groep zonder directe KVK-hint.
Dat is een eigenschap van deze bronmomentopname, geen bewijs dat zij niet in
het Handelsregister staan. Ook buiten ANBI/DUO zijn er 2.137 kandidaten
waarvan het ontbreken van een hint de primaire uitsluitingsreden is.

De filter is doelbewust conservatief qua doorlaten, niet qua vaststelling van
feitelijke rechtsvorm. Bronrelatie en naamtermen zijn heuristiek. Vooral
`holding`, `stichting`, `vereniging`, `school` en `fonds` kunnen een relevante
onderneming uitsluiten; het besluit is daarom omkeerbaar en iedere rij blijft
in de volledige master met een aparte uitsluitingsreden zichtbaar.

SHA-256 van master: `c881bc127819244d3803890c049a8e4e505090690066ab75787646957691850d`.
SHA-256 van KVK-geschikte lijst: `7291708bf10808335df49fa8cee88fba7c28036855f8855b47849d7e5313a0fc`.
SHA-256 van uitsluitingsledger: `00fbdc6e998378f8776b0ce40e4aea9c13d9679cb3edd53a5dbff0dc2a8b451e`.
De lokale JSON-metadata bindt deze bestanden byte-exact aan de regelversie
en bevat de volledige criteria en verdere aantallen. Geen nieuwe release.
