# ⏱️ Tidskontrakt – `electricity_prices` (MariaDB)

Detta dokument beskriver den **bindande tidsmodellen** för hur elpriser lagras och läses i databasen `smart_styrning`.
Alla program som **läser eller skriver** till tabellen `electricity_prices` måste följa detta kontrakt.

## 1) Vad som lagras

- Kolumn: `electricity_prices.datetime` (MariaDB `DATETIME`)
- Fältet är **naivt** (ingen tidszon lagras i DB)
- Betydelse: värdet ska tolkas som ett **UTC-ögonblick**, lagrat som **UTC-naiv** `datetime`

Konsekvens:
- Databasen gör ingen tidszonskonvertering.
- All tolkning (UTC ↔ lokal tid) sker i applikationskod.

## 2) Lokal dag vs UTC-datum

Elpriser hämtas/visas per **lokalt svenskt dygn** (Europe/Stockholm).
Eftersom DB lagrar UTC, kan ett lokalt dygn spänna över **två UTC-datum**.

Exempel (normaldag):
- Vinter (UTC+1): lokalt 00:00 motsvarar UTC 23:00 föregående datum
- Sommar (UTC+2): lokalt 00:00 motsvarar UTC 22:00 föregående datum

Det är därför fel att anta att `DATE(datetime)` i DB motsvarar ett svenskt dygn.

## 3) Canonical implementation (facit)

All kod som behöver “svenskt dygn → DB-fönster” ska använda gemensamma helpers:

- `smartweb_backend.time_utils.local_day_to_utc_window(local_day)`
- `smartweb_backend.time_utils.utc_naive_to_local(dt_utc_naive)`
- `smartweb_backend.time_utils.utc_naive_to_local_label(dt_utc_naive)`

### 3.1) DB-fönster för en svensk kalenderdag

Ett lokalt dygn definieras som intervallet `00:00` till nästa dags `00:00` i Europe/Stockholm.
Det översätts till ett **UTC-naivt** fönster för DB-frågor:

- `[utc_start, utc_end)` där båda är `datetime` utan tzinfo men representerar UTC.

Obs om DST:
- På dagar med sommartidsskifte kan intervallet i UTC vara **23h eller 25h**.
- Det är korrekt. Kod som kräver exakt 96 perioder måste normalisera/resampla.

## 4) Tillåtna operationer

✔ Tillåtet i kod:

- Tolka DB-rad som UTC:
  - `dt_utc = row_datetime.replace(tzinfo=timezone.utc)`
- Konvertera till svensk tid för index/visning:
  - `dt_local = dt_utc.astimezone(ZoneInfo("Europe/Stockholm"))`
- Bygga index (15-min):
  - `idx = dt_local.hour * 4 + (dt_local.minute // 15)`

## 5) Otillåtna antaganden

❌ Inte tillåtet:

- Anta att `DATE(datetime)` i DB = svensk kalenderdag
- Behandla `datetime` i DB som lokal tid utan konvertering
- Anta att ett dygn alltid har 24h (DST-dagar kan vara 23/25h)

## 6) Varför modellen används

- Elpris-källor publicerar ofta “per lokalt dygn”.
- UTC-lagring är entydig och DST-säker.
- “Lokalt dygn”-logik hör hemma i applikationen (kontrakt + testbar kod), inte i SQL.
