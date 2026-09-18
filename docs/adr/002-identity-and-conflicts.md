# ADR-002 — Identiteit, UNKNOWN en mergeconflicten

Status: Accepted. Requirements: CH-DATA-001..005, CH-MERGE-001..006.

KVK is pas na verificatie definitieve ondernemingssleutel. Pre-verificatie wordt uitsluitend conservatief gecombineerd. Onbekende rechtsvorm/status wordt niet positief geïnterpreteerd. Merge gebruikt KVK-syntaxis zonder verificatie en bewaart alle naamvarianten; `exclude` is standaard, voorkeur lost alleen een intern eenduidige voorkeursbron op.

