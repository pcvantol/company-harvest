# Persistence en herstel

Elke run bevat `run.json`, SQLite in WAL-modus, append-only eventlogs, snapshots, bewijs en immutable geregistreerde artefacten. Een exclusief `run.lock` staat één schrijver toe. KVK-taken doorlopen `IN_FLIGHT`, `SUCCEEDED`, `UNRESOLVED` of `FAILED`; cooldowns overleven processen. Een crash na verzending kan geen exactly-once garanderen; herhaling van leesacties wordt op candidate-ID en uiteindelijk KVK gereconcilieerd.

Exports worden naast de bestemming geschreven en atomisch verplaatst. SQLite-commit en filesystemswap zijn geen enkele transactie; `audit verify` detecteert ontbrekende/hashafwijkende outputs. Netwerk- en syncmappen zijn ongeschikt voor actieve state.

