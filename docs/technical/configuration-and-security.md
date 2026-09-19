# Configuratie en security

Precedentie vanaf bronversie 4.0.0: CLI `--data-dir`,
`COMPANY_LOOKUP_DATA_DIR`, daarna `~/.local/share/company-lookup`.
De vroegere env-var wordt niet stil overgenomen; kies de oude datamap
expliciet bij migratie. Provideropties zijn `auto`, `public-http`,
`public-browser`. Secrets zijn niet nodig. TLS-validatie blijft aan;
redirects, hosts, responses en requestaantallen zijn begrensd.

Echte data, runs, logs, browserstate, imports en builds staan in `.gitignore`. Git- en assetscans blijven nodig omdat ignore geen reeds gevolgde data verwijdert. CSV behoudt canonieke tekst; XLSX schrijft tekstcellen en neutraliseert formule-uitvoering met een apostrof zonder de canonieke CSV te wijzigen.
