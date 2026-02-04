# Ärende: Readback sker inte vid dygnsövergång (plan ev. ej uppdaterad)

## Symptom
- Vid dygnsövergång (natt) uppdateras elpriser och ny plan *ska* skapas.
- Readback triggas inte (eller ger ingen ny data).
- UI visar fortsatt val av timmar som inte stämmer med nya priser.
- Misstanke: **planen uppdateras inte alls**, trots att prislistan gör det.

(Bild bifogad i chatten visar valda timmar som inte matchar billigaste perioder.)

## Hypoteser att undersöka
1) Plan skapas inte i Arrigo vid dygnsövergång.
2) Plan skapas men:
   - readback körs inte
   - eller körs men läser fel dag/plan
3) Readback triggas på fel signal (tid / flagga / PRICE_OK / STAMP).
4) UI visar gammal plan (cache / datum / fel vy).

## Viktiga frågor
- Vad är den *faktiska* triggern för planändring?
- Vad är den *faktiska* triggern för readback?
- Finns logg som visar att plan verkligen ändras?

## Datapunkter som behövs
- Logg runt midnatt:
  - arrigo-push (price)
  - plan-generator
  - readback-service/timer
- Jämförelse:
  - Billigaste perioder enligt pris
  - Faktiskt valda perioder i plan

## Första mål
Fastställa med säkerhet:
- Uppdateras planen ja/nej?
- Om ja: varför läses den inte tillbaka?
- Om nej: varför triggas inte planändring?

## Status
- [ ] Identifiera exakt vad som inte sker
- [ ] Reproducera felet
- [ ] Åtgärda trigger/logik
- [ ] Verifiera över ett dygn
