# Ärende: PVL – PRICE_VAL-variabler (prisvärden)

## Bakgrund
Vi kör 96 perioder och pushar primärt **rankinglista** (PRICE_RANK(0..95)).
I `push_from_db.py` finns stöd för att även skriva **prisvärden** om PVL innehåller variabler `PRICE_VAL(n)`.

## Fakta (från Pi)
Script: `/home/runerova/smartweb/tools/arrigo/push_from_db.py`

Letar efter prisvärde-variabler med regex:
- `PRICE_VAL(<n>)` (case-insensitive)
- Kodrad ungefär 190–191:
  `re.search(r"PRICE_VAL\((\d+)\)$", ta, re.IGNORECASE)`

Loggar kartan:
- Rad 210: `Price_Val map: ...`
I drift ses ofta:
- `Price_Val map: []` => PVL innehåller inga `PRICE_VAL(n)` (inte fel om vi kör rank-only).

## Beslut att ta
- A) Rank-only (nuvarande): PVL behöver inte PRICE_VAL.
- B) Rank + pris (framtid): skapa PVL-variabler `PRICE_VAL(0..95)` och aktivera skrivning (om vi vill visa pris i Arrigo/Regin).

## Nästa steg (om vi vill utreda/utöka)
- Kontrollera PVL:s variabelnamn (read-sanity) och om prisvärden behövs i UI/EXOL.
- Om ja: definiera enhet (kr/kWh eller öre/kWh) och format + skapa variabler i PVL.
