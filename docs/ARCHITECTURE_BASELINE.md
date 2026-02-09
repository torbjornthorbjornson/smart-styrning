# Smartweb – Architecture baseline (2026-02-09)

Detta är en *nulägeskarta* för att kunna refaktorera stegvis utan driftstopp.

## Production path (vad som körs)

- Systemd unit: `smartweb/systemd/gunicorn.service`
- `ExecStart=/home/runerova/smartweb/run.sh`
- Wrapper: `smartweb/run.sh` → `smartweb/scripts/run.sh`
- `smartweb/scripts/run.sh` kör:
  - aktiverar venv: `/home/runerova/myenv/bin/activate`
  - startar gunicorn: `gunicorn -w 4 -b 0.0.0.0:8000 app:app`
- Flask entrypoint: `smartweb/app.py` (variabeln `app`)

## Frontend (server-renderad)

- Templates: `smartweb/templates/`
- Static: `smartweb/static/`

## Databas (MariaDB)

- Connection använder `/home/runerova/.my.cnf`
- DB: `smart_styrning`

Tabeller som används direkt i `app.py`:
- `electricity_prices`
- `weather`
- `arrigo_plan_cache`
- `water_status`
- `sites`
- `exo_payloads`

SQL-procedurer som används i `app.py`:
- `CALL exo_build_payload(site_code, day_local, top_n, cheap_pct, exp_pct)`

## Externa beroenden utanför repo

- `/home/runerova/.my.cnf` (DB credentials)
- `/home/runerova/myenv/` (Python environment för gunicorn/flask)
- `/home/runerova/.arrigo.env` (Arrigo/EXOL miljövariabler för tools/orchestrator)

## Core responsibilities (mål för clean arkitektur)

- Web/API (Flask routes + templates)
- DB access (repositories)
- Services (business logic): pris/väder/utfall/payload
- External clients: Arrigo/EXOL/Weather/Elpris

## Nästa steg

1) Inventera vilka moduler som är aktiva i drift (imports/anrop från `app.py`).
2) Skapa målstruktur (t.ex. `smartweb_backend/` package) utan att flytta kod än.
3) Flytta *en* route i taget till blueprint + service + repository.
