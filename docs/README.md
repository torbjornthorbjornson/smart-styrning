# Smartweb – Docs (index)

Målet med den här mappen är att samla **stabila kontrakt** och **drift/arkitektur-facit** så att:
- webben kan vara robust även när externa API:er ligger nere
- vi kan göra ändringar utan att tappa “hur allt hänger ihop”
- nya beteenden i backend blir dokumenterade och sökbara

## Princip: var ska information bo?

- **`docs/`** = stabil kunskap (kontrakt, arkitektur, drift). Ska gå att lita på om 3 månader.
- **`TODO/`** = pågående arbete (hypoteser, experiment, uppgifter, checklists).
- **kod-kommentarer** = endast när det är nära exekveringen (”varför just här?”), inte som ersättning för kontrakt.

## Snabbstart – viktiga dokument

### Arkitektur
- [ARCHITECTURE_BASELINE.md](ARCHITECTURE_BASELINE.md)

### Tidskontrakt (elpriser)
- [TIME_CONTRACT__ELECTRICITY_PRICES.md](TIME_CONTRACT__ELECTRICITY_PRICES.md)

### Kontrakt (bindande)
- [contracts/ARRIGO_LOGIN_TOKEN_CACHE_CONTRACT.md](contracts/ARRIGO_LOGIN_TOKEN_CACHE_CONTRACT.md)
- [contracts/WEB_RESILIENCE_CONTRACT.md](contracts/WEB_RESILIENCE_CONTRACT.md)
- [contracts/EXO_PUSH_CONTRACT.md](contracts/EXO_PUSH_CONTRACT.md)

### Drift / Ops
- [ops/README.md](ops/README.md)

### Arrigo/EXOL
- [arrigo/README.md](arrigo/README.md)
- [exol/README.md](exol/README.md)

## Äldre / blandat material

Det finns historiska anteckningar under `docs/Markdown/` och några filer utan `.md`.
Planen är att *inte* flytta allt på en gång, utan flytta in det som fortfarande är relevant när vi ändå jobbar i området.
