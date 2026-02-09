# 018 – Repo-inventering (fil-för-fil)

## Mål

- Gå igenom Smartweb fil för fil och avgöra:
  - körs i drift / importeras av `app.py`
  - är legacy / kan arkiveras
  - bör flyttas (t.ex. till `tools/`, `docs/`, `smartweb_backend/`)
  - kan raderas utan att påverka drift

## Status

- not-started

## Output vi vill ha

1) En lista “production surface area” (det som faktiskt används)
2) En lista “kandidater att arkivera”
3) En lista “kandidater att radera” (med verifieringssteg)
4) En mappstruktur som är lätt att förstå

## Metod

- Börja med `app.py` och följ imports/anrop.
- Skriv ner beslut i en tabell (fil → status → motivering).
- Flytta/arkivera i små steg och verifiera att `smartweb` fortfarande startar.

## Nästa steg

- Ta en första pass: lista alla imports från `app.py` och `smartweb_backend/web/*`.
- Markera vad som är:
  - web routes
  - DB-repos
  - clients
  - tools
