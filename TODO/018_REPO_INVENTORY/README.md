# 018 – Repo-inventering (fil-för-fil)

## Mål

- Gå igenom Smartweb fil för fil och avgöra:
  - körs i drift / importeras av `app.py`
  - är legacy / kan arkiveras
  - bör flyttas (t.ex. till `tools/`, `docs/`, `smartweb_backend/`)
  - kan raderas utan att påverka drift

## Status

- in-progress (pass 1 klar: entrypoint + blueprints + direkta beroenden)

## Output vi vill ha

1) En lista “production surface area” (det som faktiskt används)
2) En lista “kandidater att arkivera”
3) En lista “kandidater att radera” (med verifieringssteg)
4) En mappstruktur som är lätt att förstå

## Metod

- Börja med `app.py` och följ imports/anrop.
- Skriv ner beslut i en tabell (fil → status → motivering).
- Flytta/arkivera i små steg och verifiera att `smartweb` fortfarande startar.

### Verifiera att allt fortfarande fungerar (smoke test)

- Kör: `smartweb/scripts/verify_runtime.sh`
- Den testar:
  - Python import av `app` (snabbt fel om något gick sönder i imports)
  - HTTP GET mot `/`, `/styrning`, `/elprisvader` och `/exo` (200 eller 401 om Basic Auth är på)
  - DB-sanity: `SELECT 1` via `smartweb_backend.db.connection` (använder `/home/runerova/.my.cnf`)

## Nästa steg

- Ta en andra pass: gå route-för-route och markera tabeller/procedurer/externa beroenden.
- Ta en tredje pass: inventera toppnivåfiler (legacy/backup/engångsskript).

---

## Pass 1 – Production surface area (det som faktiskt körs)

### Entry points / drift

| Fil | Status | Varför |
| --- | --- | --- |
| smartweb/app.py | PROD | Gunicorn entrypoint: skapar Flask-app och registrerar blueprints |
| smartweb/smartweb_backend/web/__init__.py | PROD | `register_blueprints(app)` – kopplar in routes |
| smartweb/smartweb_backend/web/main.py | PROD | Huvudsidor (`/`, `/styrning`, `/elprisvader`, `/vattenstyrning`, m.fl.) |
| smartweb/smartweb_backend/web/api_exo.py | PROD | `/exo` adminpanel + API endpoints för payload/push |
| smartweb/systemd/gunicorn.service | PROD | systemd-unit för webben |
| smartweb/run.sh | PROD | wrapper till scripts/run.sh |
| smartweb/scripts/run.sh | PROD | aktiverar venv + startar gunicorn på port 8000 |

### Web routes → templates

| Route (Blueprint) | Template |
| --- | --- |
| `/` (main) | `templates/home.html` |
| `/styrning` (main) | `templates/styrning.html` |
| `/haltorp244/utfall` (main) | `templates/haltorp244_utfall.html` |
| `/elprisvader` (main) | `templates/elpris_vader.html` |
| `/vattenstyrning` (main) | `templates/vattenstyrning.html` |
| `/gitlog` (main) | `templates/gitlog.html` |
| `/github_versions` (main) | `templates/github_versions.html` |
| `/vision` (main) | `templates/vision.html` |
| `/roadmap` (main) | `templates/roadmap.html` |
| `/dokumentation` (main) | `templates/dokumentation.html` |
| `/exo` (exo) | `templates/exo.html` |

### Services (business logic)

| Modul | Status | Används av |
| --- | --- | --- |
| smartweb/smartweb_backend/services/prices_service.py | PROD | `main.styrning`, `main.haltorp244_utfall` |
| smartweb/smartweb_backend/services/elprisvader_service.py | PROD | `main.elprisvader` |
| smartweb/smartweb_backend/services/utfall_service.py | PROD | `main.haltorp244_utfall` |
| smartweb/smartweb_backend/services/exo_service.py | PROD | `web/api_exo.py` |

### DB repositories

| Modul | Status | DB-objekt |
| --- | --- | --- |
| smartweb/smartweb_backend/db/connection.py | PROD | ansluter mot MariaDB via `/home/runerova/.my.cnf` |
| smartweb/smartweb_backend/db/prices_repo.py | PROD | tabell `electricity_prices` |
| smartweb/smartweb_backend/db/weather_repo.py | PROD | tabell `weather` |
| smartweb/smartweb_backend/db/water_repo.py | PROD | tabell `water_status` |
| smartweb/smartweb_backend/db/plan_repo.py | PROD | tabell `arrigo_plan_cache` |
| smartweb/smartweb_backend/db/sites_repo.py | PROD | tabell `sites` |
| smartweb/smartweb_backend/db/exo_repo.py | PROD | tabell `exo_payloads`, proc `exo_build_payload(...)` |

### External clients

| Modul | Status | Kommentar |
| --- | --- | --- |
| smartweb/smartweb_backend/clients/arrigo_client.py | PROD (admin read-only) | Webben läser token-cache och gör read-only GraphQL (ingen login i web UI) |

### Shared utilities

| Modul | Status | Kommentar |
| --- | --- | --- |
| smartweb/smartweb_backend/time_utils.py | PROD | tidskontrakt: lokal dag ↔ UTC-naivt DB-fönster |

---

## Pass 1 – Första “legacy”-kandidater

| Fil | Förslag | Varför |
| --- | --- | --- |
| smartweb/app_legacy_monolith.py | ARKIV (behåll tills verifierat) | Ser ut som tidigare monolit med routes; används inte av nuvarande gunicorn entrypoint |
| smartweb/backend/simulera_vatten.py | FLYTTA till tools/ eller ARKIV | Namn tyder på simulering/dev, inte web-runtime |

---

## Pass 2 – Bakgrundsskript (hämtar data → MariaDB)

Detta matchar resiliens-kontraktet: webben läser DB och klarar API-nedtid.

| Fil | Status | Skriver till | Kommentar |
| --- | --- | --- | --- |
| smartweb/spotpris.py | PROD-SUPPORT | `electricity_prices` | Hämtar elpris från elprisetjustnu API, sparar som UTC-naiv tid |
| smartweb/weather.py | PROD-SUPPORT | `weather` | Hämtar MET API (met.no) och upsert:ar forecast-rader |
| smartweb/check_prices.py | DIAG | (read-only) | Kontrollerar att svenska dygn har 23/24/25 timmar (DST-kvalitet) |
| smartweb/scripts/importera_eldagar.sh | SUPPORT | kör `spotpris.py` | Fyller flera dagar bakåt via loop |

### Arrigo/EXOL tools

`smartweb/tools/arrigo/` innehåller orchestrator och relaterade scripts som pratar Arrigo och/eller skriver plan-cache i DB.
De är inte en del av Flask runtime, utan körs som tools/systemd.

---

## Pass 3 – Toppnivå (mappar/filer i smartweb/)

Målet med denna pass är att göra “städning” möjlig utan att råka ta bort driftvägen.

### Klassificering (förslag)

| Objekt | Status | Varför | Verifieringssteg innan flytt/radering |
| --- | --- | --- | --- |
| smartweb_backend/ | PROD | All backend-kod som Flask + tools importerar | `grep -R "smartweb_backend" -n app.py tools scripts smartweb_backend/web` |
| templates/ | PROD | Jinja-templates för webben | Starta webben + ladda `/`, `/styrning`, `/exo` |
| static/ | PROD | CSS/JS/ikoner | Ladda webben och kontrollera att styling/ikoner finns |
| systemd/ | PROD | units för webben (och ev. andra tjänster) | `systemctl cat gunicorn.service` / `systemctl status gunicorn` |
| scripts/ | PROD | runtime-wrapper (`scripts/run.sh`) + stödscript | `cat run.sh` och se att den pekar hit |
| run.sh | PROD | ExecStart-wrapper används av systemd | `systemctl cat gunicorn` och se ExecStart |
| app.py | PROD | gunicorn entrypoint | `grep -R "app:app" -n scripts/run.sh` |
| docs/ | KEEP | Stabil dokumentation/kontrakt | Inga |
| TODO/ | KEEP | Pågående arbete/checklistor | Inga |
| tools/ | PROD-SUPPORT | verktyg/orchestrators (Arrigo/EXO/backup) | Inventera `tools/arrigo/` separat |
| tools/arrigo/ | PROD-SUPPORT (delvis) | orchestrator + readback + diagnostik | `ls tools/arrigo/orchestrator.py` + kontrollera systemd-unit (arrigo-orchestrator.service) |
| spotpris.py | PROD-SUPPORT | hämtar elpriser → DB | Kontrollera att cron/systemd fortfarande kör den |
| weather.py | PROD-SUPPORT | hämtar väder → DB | Kontrollera att cron/systemd fortfarande kör den |
| check_prices.py | DIAG | felsökning DST/dygn | Kan ligga kvar eller flyttas till tools/diag/ |
| logs/ | KEEP (ops) | webb/cron/loggar | Kan roteras/komprimeras, men inte raderas blint |
| out/ | KEEP (ops) | output från jobb | Innehållet kan rensas, men behåll mappen om den används |
| backup/ | KEEP (arkiv) | historiska snapshots/zip/html etc | Flytta äldre till `_archive/` om du vill städa toppnivån |
| _archive/ | KEEP | avsedd arkivplats | Inga |
| backend/ | CANDIDATE (flytta/arkiv) | innehåller `simulera_vatten.py` (ser ut som dev/diag) | Sök referenser: `grep -R "simulera_vatten" -n .` |
| app_legacy_monolith.py | ARKIV | gammal monolit (inte entrypoint) | Sök referenser: `grep -R "app_legacy_monolith" -n .` |
| venv/ | KEEP (lokal) | virtualenv i repo | Om du vill: ersätt med standard `./.venv` men gör inte mitt i drift |
| __pycache__/ | DELETE | cache | safe delete |
| = (fil) | DELETE? | ser ut som skräp/artefakt | `file "="` och kontrollera om tom |
| SELECT / FROM / ORDER / LIMIT | DELETE | tomma artefakt-filer | `ls -l SELECT FROM ORDER LIMIT` (bekräfta 0 byte) |
| UTC-intervall | DELETE | tom artefakt-fil | `ls -l UTC-intervall` |
| Skräp/ | ARKIV/DELETE | ser ut som experiment/sparade filer | Kör separat inventering innan radering |
| 2025-08-28 | ARKIV | tidsstämplad mapp/artefakt | Kolla innehåll och flytta till `_archive/` |
| elpris_vader.html, index.html, image.png, fyll_symboler_framat.sql | CANDIDATE | toppnivå artefakter; vissa kan vara legacy | Sök om de används av templates eller scripts |

### Rekommenderad “städ-ordning” (säkert)

1) Radera uppenbart säkra artefakter: `__pycache__/` och tomfilerna `SELECT/FROM/ORDER/LIMIT` + `UTC-intervall`.
2) Flytta gamla experiment till `_archive/` (ingen radering direkt).
3) Först därefter: börja omstrukturera `backup/` och `Skräp/`.

### Utfört (logg)

- 2026-02-09: rensade tomma toppnivå-artefakter (0 byte) och toppnivå `__pycache__/`.
- 2026-02-09: arkiverade toppnivå-filerna `elpris_vader.html`, `index.html`, `image.png`, `fyll_symboler_framat.sql` till `_archive/cleanup_20260209_205757/top_level/`.

