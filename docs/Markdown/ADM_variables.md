# 📄 ADM_variables.md

Detta dokument beskriver alla variabler som används i **Adaptiv driftsmodell (ADM)**.  
Vi anger deras typ, roll och var de kommer ifrån.

---

## 🌡️ Utedata

### `R OAT`
- Typ: Real
- Beskrivning: Aktuell utomhustemperatur (°C).
- Källa: Befintlig variabel i Regin (givare Alafors).
- Roll i ADM: Används för att beräkna dT_now och diagnostik.

### `R OAT_mean`
- Typ: Real
- Beskrivning: Dygnsmedelprognos för nästa dygn (°C).
- Källa: Smartwebb/MariaDB → nytt API-projekt.
- Roll i ADM: Används vid planeringsögonblicket (13:05).

### `R OAT_yday`
- Typ: Real
- Beskrivning: Gårdagens faktiska dygnsmedeltemperatur (°C).
- Källa: Smartwebb/MariaDB → nytt API-projekt.
- Roll i ADM: Används vid inlärning (00:00).

---

## ⚖️ GM-status

### `R GM_true`
- Typ: Real
- Beskrivning: Husets aktuella gradminuter (balanstal).
- Källa: Regin (GM_Scheduler).
- Roll i ADM: Speglar husets värmebalans.

### `R GM_true_prev`
- Typ: Real
- Beskrivning: GM från föregående minut.
- Källa: Regin (GM_Scheduler).
- Roll i ADM: Används för att beräkna dGMdt.

### `R dGMdt`
- Typ: Real
- Beskrivning: Skillnad i GM per minut.
- Källa: Regin (GM_Scheduler).
- Roll i ADM: Diagnostik, kan användas för anomali-detektion.

---

## ⏱ Driftid

### `R H_used`
- Typ: Real
- Beskrivning: Antal timmar värme som körts idag.
- Källa: Räknas upp med +1/60 per minut då HEAT_DEMAND=1.
- Roll i ADM: Jämförs mot kurvans prognos vid midnatt.

---

## 📊 Prediktion/planering

### `R H_pred_d`
- Typ: Real
- Beskrivning: Prognos för antal timmar värme (decimal).
- Källa: Beräknas i ADM vid planeringen.
- Roll i ADM: Mellansteg innan avrundning.

### `I H_REQ`
- Typ: Integer
- Beskrivning: Avrundade driftimmar (0–24) för nästa dygn.
- Källa: Från H_pred_d via avrundning.
- Roll i ADM: Huvudutgång till övriga system.

### `R H_REQ_r`
- Typ: Real
- Beskrivning: Mellansteg vid avrundning.
- Källa: H_pred_d + 0.5.
- Roll i ADM: Hjälpvariabel.

---

## 📈 Kurvdata

### `R C0[36]`
- Typ: Real-array
- Beskrivning: Bas-kurva, långsam inlärning.
- Källa: Initieras i INIT, uppdateras vid midnatt.
- Roll i ADM: Husets långsiktiga “fingeravtryck”.

### `R C1[36]`
- Typ: Real-array
- Beskrivning: Overlay-kurva, snabba anpassningar.
- Källa: Initieras till 0, uppdateras varje dygn.
- Roll i ADM: Anpassar kurvan till snabba väderförändringar.

### `R HOURS_CURVE[36]`
- Typ: Real-array
- Beskrivning: Slutlig kurva = C0 + C1.
- Källa: Beräknas löpande.
- Roll i ADM: Används för H_pred_d.

---

## 🧠 Lärparametrar

### `R ETA_TAB`
- Typ: Real
- Beskrivning: Inlärningshastighet (% av felet/dygn).
- Förslag: 0.08.

### `R LAMBDA_SMOOTH`
- Typ: Real
- Beskrivning: Utjämning mellan grannpunkter.
- Förslag: 0.02.

### `R DELTA_HUBER`
- Typ: Real
- Beskrivning: Max fel (h) per dygn som används för inlärning.
- Förslag: 1.0.

### `R DECAY_C1`
- Typ: Real
- Beskrivning: Återgång för overlay (per dygn).
- Förslag: 0.005.

### `R TAB_STEP_MAX`
- Typ: Real
- Beskrivning: Max tillåten ändring per dygn (h).
- Förslag: 0.7.

---

## 📏 Tidsaxel/index

### `R dT_now`
- Typ: Real
- Beskrivning: Aktuell temperaturskillnad (0 – OAT).

### `R dT_plan`
- Typ: Real
- Beskrivning: Prognosens temperaturskillnad (0 – OAT_mean).

### `R dT_used`
- Typ: Real
- Beskrivning: Gårdagens temperaturskillnad (0 – OAT_yday).

### `I idx`
- Typ: Integer
- Beskrivning: Index i kurvan (0–35).

### `I idx_now`
- Typ: Integer
- Beskrivning: Index för dT_now.

### `I IDX_MIN`, `I IDX_MAX`
- Typ: Integer
- Beskrivning: Tabellgränser (0, 35).

### `R DT_MIN`, `R DT_MAX`
- Typ: Real
- Beskrivning: Temperaturgränser (–20, +15 °C).

---

## ⚙️ Feltermer

### `R eH`
- Typ: Real
- Beskrivning: Fel (timmar) = H_used – HOURS_CURVE[idx].

### `R e_clip`
- Typ: Real
- Beskrivning: Klippt fel (Huber).

### `R wL`, `R wR`
- Typ: Real
- Beskrivning: Viktning till vänster och höger grannpunkter.

---

## 🚨 Statusflaggor

### `L ANOM`
- Typ: Logic
- Beskrivning: Anomali-flagga, stoppar inlärning vid konstiga dygn.

### `I inivarden`
- Typ: Integer
- Beskrivning: Init-flagga (0 → kör INIT, sen 1).

### `I last_minute`
- Typ: Integer
- Beskrivning: Minutvakt (för 1-min uppdateringar).

---

# 📌 Sammanfattning

- **Finns redan i Regin/Exo:** OAT, GM_true, GM_true_prev, dGMdt, inivarden, last_minute.  
- **Måste skapas i ADM:** H_used, H_pred_d, H_REQ, H_REQ_r, C0, C1, HOURS_CURVE, dT_now, dT_plan, dT_used, idx, idx_now, IDX_MIN, IDX_MAX, DT_MIN, DT_MAX, eH, e_clip, wL, wR, ANOM, ETA_TAB, LAMBDA_SMOOTH, DELTA_HUBER, DECAY_C1, TAB_STEP_MAX.  
- **Kommer via API-projekt:** OAT_mean, OAT_yday.

---
