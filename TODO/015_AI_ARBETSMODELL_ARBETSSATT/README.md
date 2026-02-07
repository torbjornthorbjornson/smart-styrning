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


# 015 – AI-arbetsmodell & arbetssätt

## Var du är just nu (min tolkning)

Du är:

- systemtänkare ✔️  
- stark på logik, flöden, kontrakt, regler ✔️  
- jobbar i Visual Studio / VS Code ✔️  
- har Copilot, men litar inte riktigt på den ✔️  
- vill ha hjälp nära koden, inte i ett chattflöde ✔️  
- vill att verktyget:
  - pekar på fel  
  - respekterar existerande kod  
  - inte hittar på nytt  

Det är exakt den profilen där ChatGPT i fri text är sämst lämpad.

---

## Vad som faktiskt funkar bättre (idag)

### 1️⃣ GitHub Copilot – men rätt använt

Copilot har två personligheter:

❌ **Det man hatar**
- autocomplete som gissar
- fyller i hela funktioner
- “hjälpsam men farlig”

EOFras endast medvetet.ment** för både människa och system.
runerova@raspberrypi:/home $ cat > ~/smartweb/TODO/015_AI_ARBETSMODELL/README.md <<'EOF'
# 015 – AI-arbetsmodell & arbetssätt

## Var du är just nu (min tolkning)

Du är:

- systemtänkare ✔️  
- stark på logik, flöden, kontrakt, regler ✔️  
- jobbar i Visual Studio / VS Code ✔️  
- har Copilot, men litar inte riktigt på den ✔️  
- vill ha hjälp nära koden, inte i ett chattflöde ✔️  
- vill att verktyget:
  - pekar på fel  
  - respekterar existerande kod  
  - inte hittar på nytt  

Det är exakt den profilen där ChatGPT i fri text är sämst lämpad.

---

## Vad som faktiskt funkar bättre (idag)

### 1️⃣ GitHub Copilot – men rätt använt

Copilot har två personligheter:

❌ **Det man hatar**
- autocomplete som gissar
- fyller i hela funktioner
- “hjälpsam men farlig”

EOFras endast medvetet.ment** för både människa och system.