# Checks

## Data
- [ ] Var finns T_top just nu? (DB-tabell? Arrigo readback? direkt från Regin?)
- [ ] Upplösning: 15-min (96) eller annan?
- [ ] Finns VV_MIN_SAFE i systemet som variabel? (var?)
- [ ] Ska safety_active vara härledd (T_top < VV_MIN_SAFE) eller explicit flagga?

## UI
- [ ] Placering: ovan eller under prisgrafen (bestäm)
- [ ] Threshold-linje för VV_MIN_SAFE
- [ ] Tydlig badge: "Katastrofläge AKTIVT/AV"
- [ ] Markera safety-perioder i graf (valfritt men önskat)

## Test
- [ ] Välj datum där T_top tydligt sjunker och laddas
- [ ] Verifiera att safety slår till när T_top < VV_MIN_SAFE
- [ ] Kontrollera att grafen matchar verklig drift
