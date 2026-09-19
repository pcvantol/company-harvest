# Persistence en herstel

Elke run bevat `run.json`, SQLite in WAL-modus, append-only eventlogs, snapshots, bewijs en immutable geregistreerde artefacten. Een exclusief `run.lock` staat één schrijver toe. KVK-taken doorlopen `IN_FLIGHT`, `SUCCEEDED`, `UNRESOLVED` of `FAILED`; cooldowns overleven processen. Een crash na verzending kan geen exactly-once garanderen; herhaling van leesacties wordt op candidate-ID en uiteindelijk KVK gereconcilieerd.

Exports worden naast de bestemming geschreven en atomisch verplaatst. SQLite-commit en filesystemswap zijn geen enkele transactie; `audit verify` detecteert ontbrekende/hashafwijkende outputs. Netwerk- en syncmappen zijn ongeschikt voor actieve state.

## Leesbare namen vanaf de onuitgegeven 1.0.1-broncode

Nieuwe run-ID's en namen van artefacten, evidence en snapshots beginnen met
`yyyy.mm.dd_hhMMss` in **UTC**, gevolgd door 12 willekeurige hextekens tegen
naamconflicten binnen dezelfde seconde. Voorbeeld:
`2026.09.19_103917_ab12cd34ef56_03_pre_kvk_master.tsv`. De oude lange
nanoseconde-/microsecondeprefixed naam wordt niet meer gegenereerd. Bestaande
runs en bestanden worden niet verplaatst of hernoemd: `open_run` leest de
runmetadata en SQLite-padregistratie zonder de mapnaam te ontleden.
