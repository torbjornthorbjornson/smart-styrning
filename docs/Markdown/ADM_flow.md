# 📄 ADM_flow.md

Detta dokument beskriver **flödet i Adaptiv driftsmodell (ADM)**.  
Här framgår när varje block körs, vilka inputs de använder, vilka interna variabler de berör och vilka outputs de producerar.

---

## 🔄 Blocköversikt

| Block              | När körs det      | Inputs (utifrån)        | Interna variabler (ADM)          | Outputs/resultat         |
|--------------------|------------------|--------------------------|----------------------------------|--------------------------|
| **INIT**           | Vid uppstart     | –                        | `C0`, `C1`, `ETA_TAB`, `DECAY_C1`, mm. | Färdigstartad bas-kurva |
| **INIT-loop**      | Efter INIT       | –                        | `idx`, `C0[idx]`, `C1[idx]`      | Tabell fylld (0–35)      |
| **Driftidsräknare**| Varje minut      | `HEAT_DEMAND` (Regin), `OAT` (Regin) | `H_used`, `dT_now`, `idx_now`    | Uppdaterad driftid       |
| **Planering**      | Kl 13:05         | `OAT_mean` (API)         | `dT_plan`, `H_pred_d`, `H_REQ`   | Antal timmar (H_REQ) för nästa dygn |
| **Lärning**        | Kl 00:00         | `OAT_yday` (API), `GM_true` (Regin) | `eH`, `e_clip`, `C1[idx]`        | Uppdaterad kurva (C1)    |
| **Smoothing-loop** | Efter Lärning    | –                        | `C1[idx]`, `LAMBDA_SMOOTH`       | Utjämnad kurva           |
| **Decay-loop**     | Efter Smoothing  | –                        | `C1[idx]`, `DECAY_C1`            | Stabil overlay           |

---

## 📌 Blockbeskrivning

### 1. INIT
- Körs en gång vid uppstart.  
- Sätter gränser för temperatur och index.  
- Initierar kurvorna `C0` (bas) och `C1` (overlay).  
- Laddar in parametrar för inlärning (`ETA_TAB`, `DECAY_C1`, etc.).  

### 2. INIT-loop
- Fyller hela tabellen `C0` och `C1` punkt för punkt (index 0–35).  
- Innehåller även specialpunkter (exempel på standardkurva).  

### 3. Driftidsräknare
- Körs varje minut.  
- Räknar upp `H_used` med +1/60 timme om `HEAT_DEMAND=1`.  
- Beräknar aktuell temperaturskillnad `dT_now` och index `idx_now`.  

### 4. Planering (13:05)
- Slår upp prognosens dygnsmedel `OAT_mean`.  
- Beräknar antal timmar som behövs (`H_pred_d`).  
- Avrundar till heltal (`H_REQ`).  
- Detta är **huvudoutput** som systemet styr mot nästa dygn.  

### 5. Lärning (00:00)
- Jämför gårdagens verkliga timmar (`H_used`) med kurvans värde vid `OAT_yday`.  
- Beräknar fel (`eH`), klipper till max ±1 timme (`e_clip`).  
- Uppdaterar overlay-kurvan `C1[idx]` med felet.  
- Sprider även lite till grannpunkterna (`wL`, `wR`).  

### 6. Smoothing-loop
- Körs direkt efter lärningen.  
- Går igenom hela C1-tabellen punkt för punkt.  
- Jämnar till varje punkt så att kurvan inte blir hackig.  

### 7. Decay-loop
- Körs direkt efter smoothing.  
- Går igenom hela C1-tabellen punkt för punkt.  
- Multiplicerar med `(1 - DECAY_C1)` för att overlay ska avta långsamt.  
- Ger en långsiktigt stabil modell.  

---

## 🌐 Inputs från andra system

- **Från Regin-systemet:**  
  - `HEAT_DEMAND` – styrsignal om värme körs.  
  - `OAT` – aktuell utetemperatur.  
  - `GM_true` – aktuella gradminuter (balans).  

- **Från API-projektet:**  
  - `OAT_mean` – prognosens dygnsmedel (nästa dygn).  
  - `OAT_yday` – gårdagens verkliga dygnsmedel.  

---

## 🛠 Outputs

- **Interna outputs:**  
  - `H_pred_d`, `H_REQ`, `HOURS_CURVE` – modellens beräknade driftid.  
  - `C0`, `C1` – tabeller som utvecklas över tid.  

- **Externa outputs:**  
  - `H_REQ` – antal timmar värme som krävs nästa dygn (0–24).  
  - Detta används av styrsystemet för att planera drifttiden.  

---
