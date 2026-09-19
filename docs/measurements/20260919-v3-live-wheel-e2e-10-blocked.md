# Live E2E-proef met publieke wheel v3.0.0 — geblokkeerd vóór KVK

Uitvoering: CH-2026-09-19-039, 19 september 2026. Dit is een meting van de
**ongewijzigde** publieke `company_harvest-3.0.0-py3-none-any.whl`, niet van
een checkout of synthetische fixture. Een anonieme download kwam overeen met
de gepubliceerde SHA-256
`5fd0ea883b190e4c35e93d2f6d8783979094bac59b58b1d22e03c0e3734b76ba`.
De wheel is buiten de repository geïnstalleerd in een nieuwe Python 3.14.7-
omgeving; import kwam uit `site-packages`. De run gebruikte een lokale
datamap buiten Git, `--limit-kvk-check 10 --interval 2`, zonder API-key.

De tool verzamelde de vijf bronfamilies volledig: IND 12.980, GLEIF
197.163, ANBI 54.922, DUO 27.601 en TenderNed 55.928 bronkandidaten.
De samengevoegde master bevat 317.806 rijen uit 348.594 bronrijen. De run
stopte daarna bij de **pre-KVK-filter**, vóór cohortbinding of een KVK-GET.
Directe reproductie met dezelfde geïnstalleerde wheel en dezelfde run geeft
`_csv.Error: field larger than field limit (131072)` op
`pre_kvk_filter._partition_master` bij het lezen van de master-TSV.
Een afzonderlijke read-only scan met verhoogde parsergrens vond precies één
overschrijdend veld: `source_payloads_json` van 159.763 tekens. Er is geen
bronrecord aangepast, afgekapt of uitgesloten om de fout te omzeilen.

Het SQLite-journal bevat **0 KVK-verzoeken**. Er is geen stap-8-artefact of
eind-Excel. `audit verify` gaf `valid=true` voor de 33 bestaande bron- en
masterartefacten; dat is **geen E2E- of eindexport-PASS**. De eind-Excel kan
daarom niet worden gevalideerd. Een nieuw runnummer, gemanipuleerde master
of runtime-monkeypatch zou de gevraagde kale-machineproef niet bewijzen.

Vervolg vereist een begrensde, geteste CSV-parsercorrectie in een **nieuwe**
wheelversie; v3.0.0 blijft ongewijzigd. Daarna kan de bestaande run op
integriteit en hervatbaarheid worden beoordeeld en mag alleen binnen haar
oorspronkelijke maximaal-tien-KVK-scope worden doorgegaan. Live
KVK-nummerzoeking blijft in deze meting onbeproefd.
