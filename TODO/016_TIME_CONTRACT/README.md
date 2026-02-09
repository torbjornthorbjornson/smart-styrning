1️⃣ MARKDOWN – TIDSKONTRAKT FÖR MariaDB (slutgiltig, korrekt)

Det här är en rättad och exakt version, baserad på hur systemet faktiskt fungerar (inte hur det “brukar” fungera i andra projekt).

Du kan spara den som t.ex.:

docs/TIME_CONTRACT__ELECTRICITY_PRICES.md

# ⏱️ Tidskontrakt – electricity_prices (MariaDB)

Detta dokument beskriver den **bindande tidsmodellen** för elpriser i databasen
`smart_styrning`.  
Alla program som **läser eller skriver** till tabellen `electricity_prices`
MÅSTE följa detta kontrakt.

---

## 1. Översikt

Tabell:

```sql
electricity_prices


Relevant kolumn:

datetime DATETIME NOT NULL


Kolumnen är naiv (ingen tidszon lagras i databasen).

2. Vad som faktiskt lagras

electricity_prices.datetime innehåller UTC-tidpunkter, lagrade som naiv
DATETIME.

Det innebär:

Värdet representerar ett verkligt UTC-ögonblick

Databasen gör ingen tidszonskonvertering

All tolkning sker i applikationskoden

3. Samband mellan lokalt dygn och UTC

Elpriser hämtas per lokalt svenskt dygn (Europe/Stockholm):

00:00 – 23:45 lokal tid


Dessa tider konverteras till UTC innan lagring.

Konsekvens

Ett lokalt dygn (96 perioder) lagras som:

Några perioder på föregående UTC-datum

Resterande perioder på aktuellt UTC-datum

Antalet perioder som hamnar på föregående datum beror på:

Vintertid (UTC+1): 4 perioder

Sommartid (UTC+2): 8 perioder

Detta är korrekt och avsiktligt.

4. Viktig konsekvens

Ett lokalt dygn motsvarar INTE ett enskilt DATE(datetime) i databasen.

Exempel:

SELECT COUNT(*)
FROM electricity_prices
WHERE DATE(datetime) = '2026-02-07';


kan ge:

92 perioder (vintertid)

88 perioder (sommartid)

Detta är inte ett fel.

5. Hur ett komplett lokalt dygn byggs

Ett komplett lokalt dygn (96 perioder) byggs genom att:

ta slutperioder från föregående UTC-datum

ta huvudperioder från aktuellt UTC-datum

sammanfoga dessa i applikationskod

All dygnslogik sker i kod – inte i SQL.

6. Tillåtna operationer i kod

✔ Tillåtet:

# UTC-tolkning
dt_utc = row.datetime.replace(tzinfo=UTC)

# konvertering till lokal tid för index/visning
dt_local = dt_utc.astimezone(EUROPE_STOCKHOLM)


✔ Tillåtet:

index = dt_local.hour * 4 + dt_local.minute // 15

7. Otillåtna antaganden

❌ Anta att:

DATE(datetime) = lokalt dygn


❌ Anta att ett datum alltid innehåller 96 perioder

❌ Behandla datetime som lokal tid utan konvertering

8. Varför denna modell används

Elpris-API:er publicerar priser per lokalt dygn

UTC-lagring är:

DST-säker

entydig

framtidssäker

# 016 – Time contract

Det bindande tidskontraktet för elpriser ligger nu som “riktig” docs-fil:

- [docs/TIME_CONTRACT__ELECTRICITY_PRICES.md](docs/TIME_CONTRACT__ELECTRICITY_PRICES.md)

## Kod-facit (ska användas överallt)

All kod som gör “svenskt dygn ↔ DB-fönster” ska använda:

- `smartweb_backend.time_utils.local_day_to_utc_window(local_day)`
- `smartweb_backend.time_utils.utc_naive_to_local(dt_utc_naive)`
- `smartweb_backend.time_utils.utc_naive_to_local_label(dt_utc_naive)`

Detta är nu inkopplat i både webben och Arrigo-agenten.