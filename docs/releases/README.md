# Releases

Releasebewijs wordt uitsluitend na werkelijke kwalificatie/publicatie toegevoegd. Lokale builds en geblokkeerde pogingen worden niet als release gepresenteerd.

De [geïsoleerde KVK-smoke van 2026-09-19](../measurements/20260919-kvk-frontend-batch10.md)
wijzigt geen productcode of versie en levert geen releasekwalificatie of assets op.

De [pre-KVK-bronmomentopname](../measurements/20260919-pre-kvk-source-snapshot.md)
bevat productcodewijzigingen maar is wegens Wikidata HTTP 429 slechts
gedeeltelijk uitgevoerd. Een lokale vierbronnenpreview en geslaagde
kwaliteitstest zijn geen releasekwalificatie; er is geen nieuwe tag of asset.

De [offline filtermeting](../measurements/20260919-pre-kvk-filter.md) werd
aanvankelijk alleen in `Unreleased` opgenomen, zonder nieuwe tag of asset.
Daarna is zij met de geslaagde macOS/Windows-Python-3.14-matrix en overige
releasegates in v1.0.0 gekwalificeerd; zie het
[publicatiebewijs](20260919-v1.0.0-evidence.md).

- [v0.1.0](v0.1.0.md) — historisch publicatie- en kwalificatiebewijs; het GitHub Release-object en de assets zijn op 18 september 2026 verwijderd, de lokale en `origin`-tag op 19 september 2026.
- [v1.0.0](v1.0.0.md) — historische release-inhoud en [publicatiebewijs](20260919-v1.0.0-evidence.md). De GitHub Release, vijf assets en lokale/remote tag zijn op 19 september 2026 verwijderd; broncommit en documenten blijven bewaard.
- [v2.0.0](v2.0.0.md) — vorige wheel met Python 3.14, vierbronnen-E2E-opdracht en auditfix; [geverifieerd publicatiebewijs](20260919-v2.0.0-evidence.md).
- [v3.0.0](v3.0.0.md) — actuele wheel met vijf bronfamilies, KVK-nummer-only, export zonder tweede afkap en een lichte zakelijke eindlijst; [geverifieerd publicatiebewijs](20260919-v3.0.0-evidence.md).

De 3.0.0-wheel bevat TenderNed als vijfde bron, onbeperkte export binnen
de gekozen KVK-cohort en `companies_delivery_light.xlsx`. Deze functies
horen niet bij de oudere 2.0.0-wheel; zie
[het huidige outputcontract](../functional/output-files.md).
