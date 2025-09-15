## 2025-09-03 – GM_Sceduler: prisviktad catch-up (EXO-safe)
**Ändringar**
- Infört prisviktad följning för `GM_sched` (variabler: `BETA_GM`, `GM_diff`, `GM_diff_clip`, `STEP_UP_GM`, `STEP_DN_GM`).
- Fryser `GM_sched` vid `allow_heat=0` eller `EXTREME_EXP=1`.
- Snabbare catch-up vid billiga timmar (rank 0–3 → 0.5, rank 4–7 → 0.25), samt omedelbar vid `EXTREME_CHEAP=1` (1.0).
- Ratelimit/klipp per minut: `STEP_UP_GM` (uppåt) och `STEP_DN_GM` (nedåt).
- Rensat OR-uttryck (ersatt med sekventiella IF) för EXO-kompatibilitet.
- Lagt ASCII-säker torrsim-kommentar i filen.

**Motivering**
- Undvika att `GM_sched` rusar under dyra timmar.
- Köra ikapp kontrollerat när timmar är billiga, och extra hårt när de är extremt billiga/negativa.
- Minimera onödig elpanne-drift och respektera effekttak.

**Påverkade filer**
- `Normal.tse` (block: GM_Sceduler)
- `Varlista.tse` (nya R-variabler enligt ovan)
- (Init) befintligt startblock kompletterat med startvärden för de nya R-variablerna.

**Startvärden**
- `STEP_UP_GM = 20.0`
- `STEP_DN_GM = -40.0`
- `BETA_GM = 0.05` (skrivs över per timstatus)

**Torrsim (princip)**
- Start: `GM_true=-80`, `GM_sched=-80`
- Dyra timmar (`EXTREME_EXP=1`, `allow_heat=0`): `BETA_GM=0.0` → `GM_sched` fryser, `GM_true` driver nedåt.
- Billiga timmar (t.ex. rank 2): `BETA_GM=0.5` → kontrollerad catch-up.
- Extremt billigt (`EXTREME_CHEAP=1`): `BETA_GM=1.0` → snabb catch-up (begränsad av klippen).

**Test & resultat**
- Konvertering OK efter borttag av OR och ASCII-säkring av kommentarer.
- Beteende enligt design: frys på dyrt, följ på billigt, snabb följning vid extremt billigt.

**Återställning**
- Git: använd tidigare commit/branch/tagg eller egen arkivkopia i `backup/exo/`.

**Nästa steg**
- Fintrimma `STEP_UP_GM`/`STEP_DN_GM` och BETA-steg efter verklig drift.
- (Valfritt) Extra spärr i staging-blocken vid `EXTREME_EXP=1` för övertydlighet.

# Arbetslogg – Smart fastighetsstyrning

> Syfte: samla *varför* vi gjort ändringar, vad vi testat, och hur man kan rulla tillbaka.

## 2025-09-03 – Prisviktad catch-up i GM_Sceduler
**Ändringar**
- Infört prisviktad följning för `GM_sched` (BETA, STEP_UP, STEP_DN) med frys på dyra timmar och snabb ikapp vid EXTREME_CHEAP.

**Motivering**
- Undvika att `GM_sched` rusar under dyra timmar.
- Köra ikapp på billiga/negativa timmar utan onödig elpanna.

**Påverkade filer**
- `GM_Sceduler.tse` (logik)
- `Varlista.tse` (nya REAL: `BETA`, `diff`, `diff_clip`, `STEP_UP`, `STEP_DN`)

**Test & resultat**
- Torrsim visade kontrollerad ikapp utan effekttak- eller elpannestress.

**Återställning**
- `git revert <commit>` eller checka ut tidigare tagg/commit.

**Nästa steg**
- Fintrimma BETA/STEP_UP/STEP_DN med verklig driftdata.
