# Kontrakt – Arrigo login & token-cache

Detta är ett bindande kontrakt som ska förhindra driftstörningar och “token-konflikter” mellan processer.

## 1) Roller

### Orchestrator (enda som får logga in)
- Kör i bakgrunden och är **ensam ansvarig** för Arrigo-login.
- Skriver ner en återanvändbar token-cache på disk.

### Web UI (får inte logga in)
- Ska **aldrig** göra Arrigo-login.
- Får endast läsa token-cache för att kunna göra read-only operationer (t.ex. lista PVL-variabler i adminvy).

Motiv: flera samtidiga logins riskerar att invalidera varandras tokens och skapa svårdebuggade 401-loopar.

## 2) Token-cache filformat

Cachefil: `tools/arrigo/.arrigo_token.json` (eller `ARRIGO_TOKEN_CACHE_FILE`)

JSON-nycklar:
- `token` (str)
- `ts` (epoch seconds)
- `login_url` (str)
- `graphql_url` (str)
- `pvl_b64` (str)

Krav:
- Skrivning ska ske **atomärt** (tmp + `os.replace`).
- Rättigheter bör vara `0600`.

## 3) Felhantering

- Om Arrigo/API är nere: orchestrator får **inte** dö; den ska backoff:a och försöka igen.
- Om token-cache saknas (t.ex. raderad): orchestrator ska återskapa den när den har en giltig token.
- Vid 401: orchestrator gör relogin och skriver ny cache.

## 4) Konfig (miljövariabler)

Orchestrator använder:
- `ARRIGO_LOGIN_URL`
- `ARRIGO_GRAPHQL_URL`
- `ARRIGO_USER` / `ARRIGO_PASS`
- `ARRIGO_PVL_B64` eller `ARRIGO_PVL_PATH`
- `ARRIGO_TOKEN_CACHE_FILE` (valfri)

Web UI använder (read-only):
- `ARRIGO_TOKEN_CACHE_FILE` (valfri, annars default)

## 5) Acceptanskriterier

- Webben fungerar även om Arrigo är nere (max: visar ”senast uppdaterad …” eller tom lista).
- Endast orchestratorn gör login (inga web-login endpoints som råkar användas).
- Token-cache skrivs/uppdateras automatiskt vid behov.
