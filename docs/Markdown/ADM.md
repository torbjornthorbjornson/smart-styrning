
# 📘 Adaptiv Drifttidsmodell — Dokumentation

## 🎯 Syfte
Bygga en **självlärande modell** som beräknar optimalt antal värmetimmar per dygn beroende på utetemperatur.  
Systemet använder en bas-kurva (`C0`) + en lärande del (`C1`) för att anpassa sig till varje byggnads unika beteende.

---

## 🔑 Centrala variabler

### Initiering
- `DT_MIN` (R) — lägsta ΔT (°C), –20.0  
- `DT_MAX` (R) — högsta ΔT (°C), +15.0  
- `IDX_MIN` (I) — minsta tabellindex (0)  
- `IDX_MAX` (I) — största tabellindex (35)  
- `adm_idx` (I) — loopindex för init/tabell  
- `init_loop` (I/L) — flagga för init-tabell (1 = aktiv, 0 = klar)  

### Driftid
- `H_used` (R) — summerad drifttid senaste dygnet (h)  
- `HOURS_CURVE[36]` (R) — kurva (C0 + C1) = slutliga timmar per dygn  
- `H_REQ` (I) — heltalsvärde, önskat antal timmar kommande dygn  
- `H_REQ_r` (R) — flyttalsvärde innan avrundning  
- `H_pred_d` (R) — prognostiserad timmar från kurva  

### Kurvtabeller
- `C0[36]` (R) — grundkurva, linjär från 16h (–20°C) till 2h (+15°C)  
- `C1[36]` (R) — lärande overlay (justeras dygn för dygn)  

### Lärlogik
- `LEARN_COUNT` (I) — antal dagar körda  
- `MIN_LEARN_DAYS` (I) — minsta dagar innan kurvan aktiveras  
- `ADM_READY` (L) — flagga: 0 = ej mogen, 1 = aktiv modell  

### Tider
- `PLAN_H` / `PLAN_M` (X) — tidpunkt för planering (t.ex. 13:05)  
- `TRAIN_H` / `TRAIN_M` (X) — tidpunkt för träning/inlärning (t.ex. 00:00)  
- `last_minute` (X) — för 1-min triggers  

### Temperaturer
- `OAT` (R) — utetemperatur (nu)  
- `OAT_mean` (R) — medeltemp senaste dygnet  
- `OAT_yday` (R) — gårdagens medeltemp (för träning)  
- `dT_now` / `dT_plan` / `dT_used` (R) — ΔT-värden mot kurvan  

---

## ⚙️ Funktioner

### Init-fas
- Fyller tabeller `C0[0..35]` med linjär grundkurva.  
- Sätter `C1[0..35]` = 0.0.  
- Tar ~36 cykler att fullföra (ett index per cykel).  

### Driftidräknare
- Varje minut:  
  - Om `HEAT_DEMAND = 1` → öka `H_used` med 0.0167 h.  
  - Beräkna aktuell indexplats från OAT (`CvR(dT_now - DT_MIN)`).  

### Planering (dagtid, t.ex. 13:05)
- Om `ADM_READY = 0` → `H_REQ = 0`.  
- Annars → beräkna `H_REQ` från medeltemperatur (`OAT_mean`) via kurvan.  
- `H_REQ` begränsas 0–24 h.  

### Träning (natt, t.ex. 00:00)
- Räkna upp `LEARN_COUNT`.  
- När `LEARN_COUNT >= MIN_LEARN_DAYS` → `ADM_READY=1`.  
- Beräkna index från gårdagens medeltemp (`OAT_yday`).  
- Jämför `H_used` (utfall) med `C0[adm_idx]`.  
- Skillnaden ska senare användas för att uppdatera `C1[adm_idx]`.  
- Nollställ `H_used` för nytt dygn.  

---

## 🚦 Nästa steg (STEG 2)
- Implementera **inlärning** i träningen:  
  - `C1[adm_idx] = C1[adm_idx] + justering` beroende på skillnad.  
  - T.ex. enkel proportional justering: `(H_used - C0[adm_idx]) * faktor`.  
- Testa modellen mot verkliga loggdata (Pi/MariaDB).  
- Trimma faktorer för stabil inlärning.  
