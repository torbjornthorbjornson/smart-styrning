# Arrigo / Project Builder – "api"-sidan som PVL (VariableList)

Det här beskriver **mekaniken du använder** i Project Builder:

- Du bygger en webbsida (t.ex. "api") med widgets/link-icons.
- När du lägger en **länk/widget som refererar en variabel** (från valfri controller / technical address) på den sidan så blir variabeln med i en **Variable List** i Arrigo.
- Pi:n (det här repo:t) läser/skriver sedan *hela den listan* via Arrigos GraphQL-API.

I koden kallar vi det oftast **PVL** (path to variable list).


## 1) Viktig idé: "Exponera" variabler genom att lägga dem på api-sidan

Arrigo/Project Builder blir då en *whitelist*:

- **Finns variabeln som widget/länk på api-sidan?** → då kommer den med i PVL och Pi kan läsa/skriva den.
- **Finns den inte på sidan?** → då syns den inte i PVL-svaret och Pi kan varken läsa eller skriva den via den här kanalen.

Det är precis därför din "api"-sida är central: du styr åtkomst genom UI-konfiguration snarare än kod.


## 2) PVL-path: text → base64

Arrigo GraphQL vill ha `path` som **base64 av en klartext-sökväg**.

Exempel (från sanity-scripten):

- Klartext (PVL_CLEAR):
  - `APIdemo.AreaFolderView.File.APIVaribleList.File`
- Base64 (PVL_B64) = `base64(UTF-8(PVL_CLEAR))`

I Python stöds båda:

- Sätt `ARRIGO_PVL_PATH` till klartext
- eller sätt `ARRIGO_PVL_B64` direkt

Se hur det normaliseras i orchestratorn: [smartweb/tools/arrigo/orchestrator.py](../orchestrator.py)


## 3) Läsa variabler (GraphQL)

Vi läser PVL:n med en query som returnerar en lista av:

- `technicalAddress`
- `value`

Det ser ut så här i orchestratorn:

- Query: `data(path:$p){ variables{ technicalAddress value } }`
- `p` = `ARRIGO_PVL_B64` (eller base64 av `ARRIGO_PVL_PATH`)


## 4) Skriva variabler: nyckel = "<pvl_b64>:<index>"

Arrigo skriver inte med technicalAddress direkt, utan med en **key** som består av:

- PVL-path (base64) +
- indexpositionen i den returnerade listan.

Alltså:

- `key = f"{pvl_b64}:{index}"`

Där `index` tas fram genom att först läsa PVL och bygga en mapping:

- `technicalAddress -> index`

Det är därför scripts alltid börjar med en READ, bygger index, och gör WRITE efteråt.


## 5) Snabb verifiering (utan att ändra logik)

### A) PowerShell (på PC)

Kolla någon/några värden:

- [smartweb/tools/arrigo/docs/arrigo_sanity.ps1](arrigo_sanity.ps1)

Skriva testvärden (om du vill sanity-testa write):

- [smartweb/tools/arrigo/docs/arrigo_sanity_write_2.ps1](arrigo_sanity_write_2.ps1)
- [smartweb/tools/arrigo/docs/arrigo_sanity.wright_96.ps1](arrigo_sanity.wright_96.ps1)

### B) Python (på Pi)

Det finns ett probe-script som visar hur PVL tolkas och om API-svaret innehåller variables-listan:

- [smartweb/tools/arrigo/pvl_probe.py](../pvl_probe.py)

Körning (förutsätter att du har `.arrigo.env` laddad eller env satt):

- `python3 pvl_probe.py`

Det finns också ett litet list-script som visar vilka technicalAddress som din Project Builder “api”-sida just nu exponerar:

- [smartweb/tools/arrigo/list_pvl_vars.py](../list_pvl_vars.py)

Exempel:

- `python3 list_pvl_vars.py --limit 200 --filter PRICE_`


## 6) Konfig (env)

Minsta som behövs:

- `ARRIGO_LOGIN_URL`
- `ARRIGO_GRAPHQL_URL`
- `ARRIGO_USER` / `ARRIGO_PASS`
- `ARRIGO_PVL_PATH` (klartext) **eller** `ARRIGO_PVL_B64`

Orchestratorn använder dessutom prefix för handshake-signaler (TA_REQ/ACK etc):

- `ARRIGO_REF_PREFIX` (default: `Huvudcentral_C1`)


## 7) Vanliga problem

- **401 → relogin**: token expired → orchestratorn försöker logga in igen.
- **Timeout mot arrigo.svenskastenhus.se**: nätproblem/DNS/brandvägg/tjänsten nere.
  - Kolla `ARRIGO_HTTP_CONNECT_TIMEOUT_SEC` / `ARRIGO_HTTP_READ_TIMEOUT_SEC`.
  - Se också om PVL-path pekar på rätt objekt (då får du annars ofta ett tomt/konstigt svar).

## 8) Kontrakt: orchestrator gör login (token-cache)

För att undvika att flera logins invaliderar varandras tokens (konflikt) skriver orchestratorn en token-cache:

- Default: `smartweb/tools/arrigo/.arrigo_token.json`
- Kan styras med env: `ARRIGO_TOKEN_CACHE_FILE`

Webbens `/exo`-sida använder token-cachen och gör **inte** egen login mot Arrigo.


---

Om du vill kan jag även lägga till ett litet script som tar en PVL_CLEAR och spottar ut base64 (och tvärtom) samt listar vilka technicalAddress som just nu exponeras via din api-sida.
