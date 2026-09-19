# Changelog

## Unreleased

- Bronversie 3.0.1 herstelt de CSV-/TSV-parser voor verliesvrije
  bronbewijsvelden boven Python's standaardgrens: één begrensde limiet van
  1.048.576 tekens per veld geldt voor master, filter, cohort, KVK-snapshot en export.
  Een grotere of ongeldige invoer geeft een recordvrije validatiefout.
  Synthetische volledige E2E- en grensregressies toegevoegd
  (CH-2026-09-19-040, ADR-018). Een begrensde live proef ontdekte daarnaast
  drie zakelijke KVK-veldpaden die de lichte export nog afwees:
  `bezoeklocatie.huisnummerToevoeging`, `oudeHandelsnamen` en `oudeNamen`.
  Die zijn gericht aan de exportallowlist en regressietests toegevoegd;
  onbekende metadata blijft geblokkeerd. De lichte rijprojectie vult
  ontbrekende optionele velden nu expliciet met leegte, zodat de afsluitende
  audit ook bij ongelijke veldsets per KVK-hit slaagt. Nog niet gepubliceerd.

- Live proef van de ongewijzigde publieke 3.0.0-wheel met vijf volledige
  bronnen en maximaal tien KVK-checks stopte vóór de KVK-fase: één
  `source_payloads_json`-veld in de master overschrijdt Python's standaard
  CSV-veldgrens. Geen KVK-aanvraag of eind-Excel; `audit verify` gold alleen
  voor bron-/masterartefacten. Een toekomstige versie moet dit begrensd
  verhelpen en opnieuw E2E toetsen (CH-2026-09-19-039).

- Distributiebeheer zonder software- of pakketversiewijziging: op
  eigenaarsverzoek zijn alle GitHub Releases en lokale/remote tags onder
  3.0 verwijderd. Alleen `v2.0.0` bestond nog; haar vijf publieke assets
  en tag zijn ingetrokken. `v3.0.0`, broncommits en historische bewijzen
  blijven intact (CH-2026-09-19-038).

## 3.0.0 - 2026-09-19

- v3.0.0-distributie kwalificeert de vijfbronnenketen en lichte export voor
  een nieuwe wheel. De assetscan faalt gesloten bij archiefleden boven 5 MiB;
  lokale test en macOS-/Windows-CI blijven verplichte publicatiepoorten
  (CH-2026-09-19-037).

- Documentatie voor de 3.0.0-release samengebracht:
  actuele macOS-/PowerShell-E2E-instructies, een canoniek zevenbestands-
  outputcontract, veldherkomst van de lichte Excel, schema-1-compatibiliteit,
  veilige foutpaden en expliciet onderscheid met de oude 2.0.0-wheel.
  Historische releasebewijzen blijven historisch (CH-2026-09-19-036).

- De 3.0.0-code levert afzonderlijk
  `companies_delivery_light.csv`/`.xlsx`: zakelijke velden uit de publieke
  KVK-zoekhit plus herkenbare bronwebsite/-sector, zonder ruwe JSON of
  technische metadata. Exacte kandidaat-ID/nummerjoin en schema-2-manifest
  met zeven hashgebonden bestanden zijn auditbaar; oude vijfbestandssets
  blijven leesbaar. Onbekende KVK-responsvelden stoppen veilig; samengevoegde
  bronrijen leveren de eerste beschikbare website/sector. Offline E2E en
  regressietests
  (CH-2026-09-19-035, ADR-017).

- Voor nieuwe runs is `HOLDING_OR_MANAGEMENT` een auditbaar reviewlabel in
  een hashgebonden TSV, geen automatische pre-KVK-uitsluiting meer. Alle
  KVK-checks vragen uitsluitend een geldige directe bron-KVK-hint op en
  vergelijken het teruggegeven nummer exact, ook bij afwijkende naam. Zonder
  hint wordt geen naamverzoek verstuurd: de oude R8-no-hint-pilot werkt daarom
  voortaan offline-only. De publieke providers weigeren naamquery's aan de
  transportgrens. Tegenspraak tussen status-/rechtsvormvarianten van hetzelfde
  nummer wordt niet als match geaccepteerd. Offline tests PASS; live
  nummerzoeking en nieuwe volledige run nog niet getest (CH-2026-09-19-034,
  ADR-016). Geen bestaande release gewijzigd.

- Hervatgedrag van `run e2e --run-dir` expliciet gedocumenteerd en offline
  getoetst na een onderbreking tijdens de KVK-check: intacte bron- en
  pre-KVK-artefacten worden hergebruikt, eerdere of onzekere KVK-verzoeken
  worden niet dubbel verstuurd en de partiële export blijft auditbaar.
  Geen runtimewijziging binnen die afzonderlijke uitvoering
  (CH-2026-09-19-033).

- Broncode 3.0.0: `run e2e --export-limit` en `export --limit` verwijderd.
  Alle actieve, geverifieerde bedrijven uit de gekozen KVK-scope worden
  geleverd; de schema-1-reserve blijft leeg. Oudere runs met een mogelijk
  bindende exportlimiet worden niet stil gemigreerd. De publieke CLI-wijziging
  is incompatibel, daarom MAJOR-versie
  (CH-2026-09-19-032, ADR-015).

- TenderNed toegevoegd als vijfde bron voor nieuwe volledige
  voorbereidings- en E2E-runs. Historische XLSX en meest recente JSON worden
  zonder jaaroverlap gecombineerd; alleen Nederlandse gegunde leveranciers
  worden kandidaat. Ruwe nummers blijven KVK-bronhints. Lokale evidence,
  rejected-/reviewledger, hashbinding, downloadgrenzen en offline CI-E2E zijn
  toegevoegd. Bestaande vierbronnenruns blijven hervatbaar
  (CH-2026-09-19-031, ADR-014).

- TenderNed-bron verder gekwalificeerd zonder tool- of releasewijziging:
  de officiële XLSX-leeswijzer bevestigt `ON kvknummer` als KVK-bronveld
  en koppelt het aan JSON `awards/suppliers/id`. In 2021–2026 Q1/Q2 zijn
  11.147 unieke achtcijferige nummers bij Nederlandse gegunde ondernemingen
  gemeten, waarvan 9.380 niet als directe nummerhint in de huidige master
  staan. GO voor een afzonderlijk begrensd lokaal adapterontwerp, met
  JSON/XLSX-reconciliatie destijds als resterende poort; inmiddels uitgevoerd
  (CH-2026-09-19-030, ADR-014).

- Distributiebeheer zonder code- of pakketversiewijziging: op expliciet
  eigenaarsverzoek zijn alle tags en GitHub Releases onder 2.0 verwijderd.
  Concreet is `v1.0.0` met vijf publieke assets en lokale/remote tag
  ingetrokken; `v0.1.0` was al verwijderd. `v2.0.0`, de bronhistorie en
  historische bewijsdocumenten blijven behouden (CH-2026-09-19-029).

## 2.0.0 - 2026-09-19

- Incompatibele Python-supportwijziging: na v1.0.0 (Python 3.11–3.14)
  accepteert de tool alleen Python 3.14.x. Daarom verschijnt deze broncode
  als 2.0.0 en niet als een compatibele 1.x-release; gebruik Python 3.14
  voor installatie en uitvoering.

- GitHub Actions gebruikt de actuele v7-versies van `checkout` en
  `setup-python` op Node 24; de Python 3.14/macOS+Windows-matrix en de aparte
  offline E2E-poort blijven ongewijzigd.
- Alle CLI-routes tonen nu veilige, ANSI-gekleurde fase-, resultaat- en
  foutmeldingen op stderr, zonder recordinhoud. De E2E-keten en langlopende
  KVK-check geven tussentijdse stappen/checkpoints; machineleesbare stdout,
  exitcodes en hervatten blijven behouden. `NO_COLOR` en `FORCE_COLOR`
  worden ondersteund.
- Interne gedragsbehoudende refactor: CLI-routering per commandofamilie en
  pre-KVK-streamingpartitie los van metadata-/artefactpublicatie. Extra
  route-/optie- en naambehoudtests; geen nieuwe fuzzy filter of datamigratie.
- Read-only naamsvariantenmeting op de 119.801 pre-KVK-geschikte kandidaten:
  283 schrijfwijze-/`BV`-botsingsgroepen en 285 hypothetische overschotregels,
  maar telkens verschillende opgegeven KVK-nummers. Geen fuzzy filter of
  automatische uitsluiting toegevoegd; besluit daarover staat open.
- Beide Python-3.14-CI-platformjobs hebben nu een apart zichtbare offline
  E2E-integratieproef: CLI vanaf lege run, gesimuleerde broncollectors en
  KVK-check, echte filtering/export/audit en hervatten; netwerkverkeer is in
  deze proef voor niet-lokale bestemmingen verboden.
- De audit van het nieuwste PARTIAL-outputmanifest eist
  een expliciete, met de run overeenkomende status en vijf bestanden met
  dezelfde registratiestatus. Gerichte regressies bewijzen een geldige
  partiële levering en weigeren ontbrekende status, gewijzigd bestand of een
  manifest dat niet met de afgeronde runstatus overeenkomt.
  v1.0.0 blijft ongewijzigd.
- De tool accepteert uitsluitend Python 3.14.x:
  packagingmetadata, runtime, hostpreflight, installers en ontwikkelinstellingen
  wijzen andere minorversies af. De gepubliceerde v1.0.0 blijft ongewijzigd.
- Expliciet `run e2e`-commando voor volledige
  vierbronnenvoorbereiding, publieke KVK-check, canonisering, filters, export,
  rapport en audit. `--limit-kvk-check N` bindt een onveranderlijke cohort van
  maximaal N kandidaten aan de run; hervatten kan de grens niet verhogen.
  Als kandidaten buiten de cohort vallen, blijft de levering zichtbaar PARTIAL
  ten opzichte van de volledige pre-KVK-lijst; zij bevat altijd maximaal N
  unieke KVK-nummers. Onopgeloste kandidaten binnen de cohort eisen afzonderlijk
  `--allow-partial`.
- Partiële outputsets worden nu door `audit verify` inclusief manifest,
  bestandshashes, cohortbinding en count-closure gevalideerd. De oude
  `MISSING_REQUIRED:outputset_manifest`-valspositieve melding is in de
  broncode opgelost; release v1.0.0 blijft ongewijzigd.
- Nieuwe run-, artefact-, evidence- en snapshotnamen beginnen met een leesbare
  UTC-tijd `yyyy.mm.dd_hhMMss` plus een korte willekeurige suffix, zonder de
  lange nanosecondeprefixed waarde. Bestaande runs en bestandsnamen blijven
  ongewijzigd en leesbaar.
- De historische Git-tag `v0.1.0` is op eigenaarsverzoek uit de lokale
  checkout en van `origin` verwijderd; broncommit en releasebewijs blijven.
- Korte functionele v1.0.0-snelstart met exacte commando's, hervatpad en
  outputgates naast de uitgebreide commandotabel; geen uitvoerbare wijziging.

## 1.0.0 - 2026-09-19

- Sluit het tijdelijke SQLite-spoolbestand van de pre-KVK-master expliciet vóór
  opruimen, zodat de workflow ook op Windows werkt.
- Expliciete hervatbare `kvk pre-kvk-run` voor de publieke frontend-Web-API:
  minimaal twee seconden tussen verzoekstarts, per-kandidaatjournal,
  atomische voortgang, duurzame tussentijdse TSV's en pas na een gesloten
  kandidaatpartitie COMPLETE-artefacten voor de vervolgworkflow.
- Herzienbare offline toelatingsfilter tussen vierbronnenmaster en KVK-batch:
  behoud van de volledige master, afzonderlijke KVK-geschikte lijst en
  uitsluitingsledger met alle redenen, criteria, hashes en gesloten aantallen.
  Ontbrekende/stale filtersets en onverenigbare KVK-journals blokkeren requests.
- Zelfstandige vierbronnenvoorbereiding (IND, GLEIF, ANBI, DUO), zonder
  automatische Wikidata-download, met volledige evidencecontrole en één
  gededupliceerde master; expliciete hervatbare KVK-Web-API-batches van
  maximaal tien kandidaten publiceren uitsluitend partiële uitkomsten.
- Eenmalige brede pre-KVK-bronmomentopname met full-scope/evidence-gates,
  verliesvrije conservatieve disk-dedup en aparte geblokkeerde preview bij
  onvolledige bron; Wikidata HTTP 429 verhindert de vijfbronnenmaster.
- Bron-HTTP leest begrensd als stream en valideert ook redirectdoelen;
  Wikidata-paginering pauzeert tussen publieke requests.
- Geïsoleerde, niet-gepubliceerde tien-GET-capabilitymeting via de publieke
  KVK-frontend-Web-API; ten tijde van die meting bleven R7 en bulkgebruik geparkeerd.
- GitHub Release-object `v0.1.0` en de vijf assets op eigenaarsverzoek verwijderd; op dat moment bleven de Git-tag en historische kwalificatie-evidence behouden.
- Doorlopende CI teruggebracht tot Python 3.14 op macOS en Windows; Ubuntu en Python 3.11–3.13 gelden voor nieuwe wijzigingen als `NOT_TESTED`.
- Broncatalogusschema 2 met expliciete identifier-, toegang-, voorwaarden-, actualiteits-, bronfamilie-, herkomst- en laagprofielen.
- Verliesvrije lokale bronimport zonder verplichte KVK-kolom; ontbrekende en ongeldige nummers blijven meetbare kandidaten.
- Machineleesbaar outcome-rapport met count-closure, per-bronopbrengst, deduplicatie, review, diversiteit en resourcegebruik.
- Uitgaande bron- en KVK-requests, runmetadata en rapportage gebruiken `company-lookup/0.1` zonder persoonlijke verwijzing.
- Begrensde live capabilitymeting voor IND en Wikidata met terminale foutstatussen,
  identifierclosure, duplicaten, exacte overlap, bronactualiteit en request-/rate-limitobservaties.
- GLEIF Level 1 Golden Copy-feasibility met `GO`: officiële CC0-bulkroute, actuele
  omvang en begrensde Nederlandse identifier-/rechtsvorm-/statusmeting vastgelegd.
- Streaming GLEIF Golden Copy-adapter met begrensde download/ZIP-gates, immutable
  evidence, Nederlandse filtering, verliesvrije identifier-review, resume/refresh en
  zichtbare opbrengst plus exacte KVK-overlap in het outcome-rapport.
- Zes aanvullende bronfeasibilitykaarten en een vijf-familiesportfolio; expliciete
  streaming ANBI- en DUO-adapters met veilige ZIP/XML/CSV-verwerking, immutable evidence,
  volledige historie-/identifierclosure en behoud van kandidaten zonder KVK-nummer.
- Beveiligde ANBI XML-verwerking via vastgepinde `defusedxml`; oudere broninventarissen
  worden uitsluitend via expliciete migrerende acties verliesvrij aangevuld; pure reads
  veranderen historische runs niet.
- Deterministische R6-sampling over bronfamilie en identifierstatus met een gesloten
  500-record dedupmeting, expliciete reviewimport, resourcebaseline en reproduceerbare
  50-recordselectie plus metriekcontract voor de R8-matchingpilot.
- Begrensde R8-identiteitsmatching met offline-first sterke-veldenbewijs, sequentiële
  publieke frontendfallback, exact hervatjournal, vijf terminale uitkomsten,
  transactionele reviewlifecycle en reviewgestuurde R9-thresholds zonder naam-onlymerge.

## 0.1.0 - 2026-09-18

- Eerste implementatie van HARVEST-stappen 1–8 en zelfstandige MERGE_LISTS-stap 9.
- Lokale runstate, logging, locks, snapshots, checksums, audit verify/trace en herstelbare KVK-journalering.
- Publieke bronadapters, publieke KVK HTTP-/Playwright-contracten, filtering en veilige CSV/XLSX-export.
- Host/installatie/runwrappers, quality- en releasehulpmiddelen en Nederlandse documentatie.
