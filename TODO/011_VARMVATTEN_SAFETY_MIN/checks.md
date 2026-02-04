# Checks (snabbt)

## VV-min
- [ ] Vilken variabel är VV-temp? (TA / intern signal)
- [ ] Var skrivs VV-plan/enable? (TA / relä)
- [ ] VV_MIN / VV_TARGET bestämt och dokumenterat

## Fallback
- [ ] Hur avgör vi "ranking saknas"? (PRICE_OK / STAMP / DB)
- [ ] Finns "senast giltig plan" lagrad? (DB/variabel)
- [ ] Standardplan definierad (minimalt intrång)

## Fail-safe
- [ ] Hur är relä kopplat? NO/NC?
- [ ] Vad händer vid Pi/EXOL reboot?
- [ ] Vad händer om GraphQL dör / token dör?
