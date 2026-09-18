# Configuratie en security

Precedentie: CLI `--data-dir`, `COMPANY_HARVEST_DATA_DIR`, platformonafhankelijke gebruikersdefault. Provideropties zijn `auto`, `public-http`, `public-browser`. Secrets zijn niet nodig. TLS-validatie blijft aan; redirects, hosts, responses en requestaantallen zijn begrensd.

Echte data, runs, logs, browserstate, imports en builds staan in `.gitignore`. Git- en assetscans blijven nodig omdat ignore geen reeds gevolgde data verwijdert. CSV behoudt canonieke tekst; XLSX schrijft tekstcellen en neutraliseert formule-uitvoering met een apostrof zonder de canonieke CSV te wijzigen.

