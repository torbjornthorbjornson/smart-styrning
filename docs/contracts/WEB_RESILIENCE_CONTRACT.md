# Kontrakt – Webben är DB-first (resiliens)

Det här kontraktet beskriver hur Smartweb ska vara robust även när externa system (Arrigo/EXO/Weather/Elpris) är nere.

## Grundregel

Webb-UI ska hämta allt som behövs för rendering från **MariaDB**.

- Externa API:er får endast användas av bakgrundsjobb/agents/orchestrators.
- Dessa processer skriver ner resultat till DB så fort data är tillgänglig.
- Webben visar alltid ”senast kända data” och kan visa historik.

## Konsekvens

- Om Arrigo/API går ner ska webb-sidorna fortfarande fungera.
- Det som påverkas är endast ”hur färsk data är”.

## Rekommenderat statusmönster

När en agent hämtar extern data bör den också skriva:
- `last_ok_ts`
- `last_error_ts`
- `last_error_message`

så att webben kan visa:
- ”Data uppdaterad för X minuter sedan”

## Acceptanskriterier

- Sidor som inte kräver live-API fungerar helt utan nät.
- Historik kan visas (igår, förra veckan, 2 månader sedan) från DB.
- Adminvyer som gör API-read-only ska degradera snyggt (timeout => varning, ingen crash).
