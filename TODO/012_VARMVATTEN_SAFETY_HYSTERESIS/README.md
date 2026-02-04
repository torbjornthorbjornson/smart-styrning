# Ärende: VV-säkerhet – hysteres + latch (anti-fladder)

## Varför (bakgrund)
När vi inför säkerhets-override (t.ex. VV_ALLOWED=1 vid låg T_top) kan VV_ALLOWED/DO_VV börja **fladdra** om temperaturen pendlar runt gränsen eller om flera block “drar” i samma signal.

Det här ärendet handlar ENBART om att göra säkerhetsläget stabilt.

## Mål
- Ingen fladder runt VV_MIN_SAFE
- När säkerhetsläget väl går in ska det ligga kvar tills VV tydligt återhämtat sig
- Prisplanen påverkas inte när VV-temp är stabil

## Föreslagen design (EXOL)
### Nya variabler (förslag på namn, i variabellistan)
- `R VV_MIN_SAFE`      (°C)  start för säkerhetsläge
- `R VV_SAFE_HYST`     (°C)  hysteresis (t.ex. 3.0)
- `L VV_SAFE_ACTIVE`   (0/1) latch som håller säkerhetsläge

### Latch-regler
- **Aktivera:** om `T_top < VV_MIN_SAFE` → `VV_SAFE_ACTIVE = 1`
- **Släpp:** om `T_top >= (VV_MIN_SAFE + VV_SAFE_HYST)` → `VV_SAFE_ACTIVE = 0`

### Var ska den ligga?
I samma minut-gate som VV_ALLOWED beräknas (VVP_ApplyPlan), så att:
- allt uppdateras **max 1 gång/minut**
- du får “lugn signal” i Arrigo

### Hur påverkar den VV_ALLOWED?
- Normal logik: VV_ALLOWED följer plan
- Säkerhetsläge: om `VV_SAFE_ACTIVE = 1` → `VV_ALLOWED = 1` (oavsett plan)

## Klart när
- VV_ALLOWED ligger stabilt även om T_top pendlar nära gränsen
- Inga snabba 0/1-ändringar syns i Arrigo när VV är “på gränsen”
