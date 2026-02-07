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

✅ **Det du ska använda**
- Copilot Chat i VS Code
- frågor som:
  - *Why is this variable never written?*
  - *Does this handshake violate the stated rules?*
  - *Show where ACK can be written more than once.*

Copilot Chat:
- ser hela filen
- ser felmarkeringar
- respekterar projektets kontext
- ändrar inte kod om du inte ber den

👉 För detta projekt är Copilot Chat bättre än ChatGPT.

---

### 2️⃣ IDE:n ljuger inte

Det du gjorde helt rätt:
- skickade skärmdump
- litade på Visual Studio

IDE:n hade redan:
- flaggat indentation
- markerat unreachable code
- varnat för variabler

Detta är statisk analys:
- tråkig
- exakt
- pålitlig

För styrsystem och orchestrators:
**lita mer på IDE:n än på AI-text.**

---

### 3️⃣ GitHub Pro – vad du faktiskt får

Med GitHub Pro + Copilot:
- Copilot Chat i editorn
- inline-förklaringar
- diff-förslag istället för omskrivning
- större respekt för befintlig kod

I praktiken:
**Codex-liknande beteende, fast inne i VS Code.**

---

## Hur ChatGPT ska användas framåt

❌ Inte för:
- skriva ny kod
- fixa hela filer
- skicka kompletta versioner

✅ Använd ChatGPT som:
- arkitekt
- granskare
- regelpolis
- sanity check

### Bra frågor här:
- *Kan denna kod bryta regeln: ACK sätts bara en gång?*
- *Vilka signaler kan race:a?*
- *Finns implicit state machine?*
- *Beskriv flödet utan kod.*

Alltså: **analys, inte modifiering.**

---

## Canvas?

Ärligt: **nej, inte för detta projekt**.

Canvas är bra för:
- dokument
- resonemang
- struktur

Men:
- inte IDE-nära
- inte statiskt korrekt
- sämre än VS Code + Copilot för styrkod

---

## Rekommenderat arbetssätt (bindande)

### 🔧 Primärt
- VS Code + Copilot Chat
- IDE + analys först
- människa beslutar

### 🧠 Sekundärt (ChatGPT)
- arkitektur
- handshake-regler
- resonemang
- dokumentation

### 🚫 Undvik
- “skicka komplett kod”
- “fixa hela filen”
- långa chattar med produktionskod

---

## Status

Detta dokument är resultatet av flera dagars felsökning,
frustration och lärdomar.

Det är ett **skyddsdokument** för både människa och system.

Ändras endast medvetet.
