# Ärende: Varmvatten-säkerhet (miniminivå + fallback + fail-safe)

## Problem (prio)
- Dusch = kallt → oacceptabelt.
- Vi behöver "lugn och ro": varmvatten ska alltid kunna produceras även om pris/ranking/plan fallerar.

## Mål
1) **Absolut miniminivå VV**:
   - Om VV-temp < VV_MIN => kör varmvatten OAVSETT pris och tid.
2) **Fallback om ranking/plan saknas**:
   - Om inga nya rankinglistor/plan kan skapas => använd senast kända plan eller en säker standardplan.
3) **Fail-safe i relälogik**:
   - Undvik läget där "inget signal" => ingen VV/ingen värme.

## Designidé (förslag, ska beslutas)
### A) VV_MIN override
- Parameter: VV_MIN (t.ex. 45°C) och ev VV_TARGET (t.ex. 50°C).
- Logik:
  - VV_TEMP < VV_MIN => VV_FORCE=1 (kör tills VV_TEMP >= VV_TARGET)
  - VV_FORCE ska vinna över prisplan.

### B) Fallback (när data saknas)
- Trigger: ranking saknas / PRICE_OK=0 / PRICE_STAMP gammal / DB saknar dygn.
- Åtgärd:
  - Återanvänd senaste giltiga plan (inom X timmar/dygn), annars standard (ex 2–4 korta körfönster/dygn).
- Logga tydligt: "FALLBACK ACTIVE".

### C) Fail-safe (relä)
Två huvudlägen:
1) **Fail-closed** (som idag): måste dra relä för att tillåta drift.
   - Fördel: säkrare mot oönskad drift.
   - Nackdel: vid fel => ingen VV/ingen värme (det ni upplever).
2) **Fail-open** (rekommenderat för komfort): default tillåt drift, och styrsystemet *blockerar aktivt* när det inte ska köra.
   - Fördel: vid systemfel får ni fortfarande VV/värme (”graceful degradation”).
   - Nackdel: vid fel kan drift ske när det inte är optimalt (men hellre det än kallt).

## Nästa steg (första chatten på detta ärende)
1) Fastställ var VV-temp läses och var VV-plan/relä styrs (EXOL / Arrigo-variabler).
2) Bestäm VV_MIN & VV_TARGET (startvärden).
3) Implementera override + loggning.
4) Test: simulera "ingen ranking in" + bekräfta VV fortfarande fungerar.

## Status
- [ ] Påbörjad
- [ ] Implementerad i test
- [ ] Verifierad i drift
