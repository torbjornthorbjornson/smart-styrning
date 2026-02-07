# 015 – AI-arbetsmodell & arbetssätt

## Syfte
Skapa ett stabilt, repeterbart och förtroendebaserat arbetssätt mellan
människa, AI och utvecklingsmiljö – utan att kod förstörs eller tappas bort.

Detta dokument är **bindande referens** innan:
- ny arkitektur införs
- befintlig kod ändras
- större refaktorering sker

---

## Roller

### ChatGPT – Arkitekt & systempartner
Används för:
- idéarbete
- systemdesign
- flöden & handshakes
- regelverk & konstitutioner
- markdown & dokumentation
- logisk granskning

Får **inte**:
- skriva om hela kodfiler
- ändra fungerande kod
- felsöka syntax, indentation eller runtime-fel
- ersätta IDE, debugger eller statisk analys

---

### Människa (du)
Används för:
- faktisk kodning
- felsökning i IDE
- körning, test, verifiering
- beslut om när kod är redo att ändras

---

## Arbetsprinciper

1. **Fungerande kod är helig**
   - Den får inte ändras utan:
     - tydlig diff
     - rollback-plan
     - uttryckligt godkännande

2. **Små, isolerade ändringar**
   - En fil
   - Ett syfte
   - Ett test

3. **Markdown först**
   - Alla idéer, flöden och handshakes skrivs i markdown
   - Kod skrivs först när modellen är låst

4. **Chat-namn är kontrakt**
   Exempel:
   - Smart styrning – Orchestrator – Readback
   - Smart styrning – EXOL – Handshake
   - Smart styrning – UI – Hjälptexter

---

## Status
Detta dokument skapades efter flera dagars intensiv felsökning och är ett
resultat av lärdomar.

Ändras endast medvetet.
