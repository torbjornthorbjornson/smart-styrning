# Ärende: Hältorp-sidan – graf för T_top (VV-temp) + indikator för katastrofläge

## Mål
På Hältorp 244-sidan (utfall/plan-vy) visa en graf (ovan eller under prisgrafen) som visar:
- `T_top` = varmvattentemperatur över dygnet
- tydlig koppling till när VV laddas/”laddas ur”
- samt visa om "katastrofläget" (safety override) är aktivt

## Bakgrund
Vi vill snabbt se varför man får kallt VV och få lugn och ro:
- T_top trend över dygnet (sjunker / laddas)
- när VV laddas i relation till valda perioder + elpris
- när safety override tvingar VV oavsett pris

## Safety override (EXOL-logik som ska synas i UI)
; --- Safety override: force VV if T_top below safe min ---
IF T_top < VV_MIN_SAFE
  VV_ALLOWED = 1
ENDIF

## UI – vad som ska visas
1) **Linjegraf T_top** över tid (96 punkter/dygn om vi har 15-min, annars det vi har).
2) **Horisontell linje** för `VV_MIN_SAFE` (så man ser när den underskrids).
3) **Katastrofläge aktivt**:
   - antingen en tydlig badge/text: "Katastrofläge: AKTIVT"
   - och/eller markering i grafen (t.ex. röd bakgrund/markörer där override är aktiv)

## Datakrav
- Källa för `T_top` (var kommer den från? Arrigo readback/Regin/DB?)
- Källvärde för `VV_MIN_SAFE`
- Källvärde/flagga för `katastrofläge` (t.ex. VV_ALLOWED-forcering eller separat bool)

## Definition av "katastrofläge aktivt" (förslag)
- Aktivt när `T_top < VV_MIN_SAFE` (direkt härledd)
- eller aktivt när EXOL sätter en flagga (rekommenderat på sikt): `VV_FORCE_ACTIVE` / `VV_SAFETY_ACTIVE`

## Implementationsidé (webb)
- Lägg till dataset i endpoint som renderar Hältorp-sidan:
  - `ttop_series[]` (timestamp + temp)
  - `vv_min_safe` (float)
  - `safety_active_series[]` eller bool per period
- Rendera med Chart.js:
  - Line chart för T_top
  - Annotation/threshold-linje för VV_MIN_SAFE
  - Markera perioder där safety är aktiv (dataset eller bakgrundsband)

## Status
- [ ] Identifiera datakälla för T_top
- [ ] Plocka ut tidsserie per dygn
- [ ] Lägg till i backend-output till templaten
- [ ] Rita graf i frontend
- [ ] Lägg till katastrof-indikator
- [ ] Verifiera med ett dygn
