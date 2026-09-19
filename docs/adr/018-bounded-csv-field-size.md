# ADR-018 — Begrensde CSV-veldlimiet voor bronbewijs

Status: aangenomen voor bronversie 3.0.1 (CH-2026-09-19-040).

## Context

De publieke v3.0.0-wheel voltooide in een echte vijfbronnenproef de master,
maar kon die niet filteren. Eén `source_payloads_json`-veld bevatte 159.763
tekens, boven de standaardlimiet van Python's `csv`-parser (131.072). De
master, filterlijst en cohort worden op meerdere plekken opnieuw gelezen;
een plaatselijke verruiming in alleen de filter zou de fout kunnen verplaatsen.

## Besluit

Bij import van de gedeelde `core` wordt de procesbrede `csv.field_size_limit`
op **1.048.576 tekens per veld (2^20)** gezet. Iedere CLI- en directe
Python-route importeert deze module vóór het lezen van run-CSV/TSV en gebruikt
dezelfde begrensde parser. Deze grens ligt ruim boven het waargenomen
bewijsveld maar laat geen onbeperkt veld toe. CSV-fouten bereiken de CLI als
gecontroleerde validatiefout zonder de veldinhoud te tonen. Er wordt niets
afgekapt, herschreven of uit de bronlijst weggelaten.

## Bewijs en gevolgen

Synthetische tests dekken het exact behouden van een 159.763-tekens veld,
de volledige offline filter→cohort→KVK-mock→exportketen en afwijzing boven
die grens. Het run- en outputsetschema veranderen niet; een met v3.0.0
begonnen, nog niet gecheckte run kan na integriteitscontrole met een nieuwe
wheel hervatten. De publieke v3.0.0-release zelf blijft ongewijzigd.
