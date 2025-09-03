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
