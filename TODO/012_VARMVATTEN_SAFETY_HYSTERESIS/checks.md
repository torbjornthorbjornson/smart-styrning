# Checks (012)

## Variabler
- [ ] VV_MIN_SAFE finns (R)
- [ ] VV_SAFE_HYST finns (R)
- [ ] VV_SAFE_ACTIVE finns (L)

## Logik i VVP_ApplyPlan
- [ ] VV_SAFE_ACTIVE sätts/släpps enligt latch-reglerna
- [ ] VV_ALLOWED tvingas till 1 när VV_SAFE_ACTIVE=1
- [ ] Körs i minut-gate (max 1 gång/minut)

## Test
- [ ] Simulera T_top strax under VV_MIN_SAFE -> VV_SAFE_ACTIVE går 1 och stannar
- [ ] Höj T_top över VV_MIN_SAFE + VV_SAFE_HYST -> VV_SAFE_ACTIVE släpper
- [ ] Bekräfta att VV_ALLOWED inte fladdrar
