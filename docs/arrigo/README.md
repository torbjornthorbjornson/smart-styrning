# Arrigo – dokumentation

## Syfte

Samla Arrigo-specifika detaljer (PVL, GraphQL, variabelnycklar) på ett ställe.

## Referens

- Driftstrategi/anteckningar finns idag även här:
  - [tools/arrigo/docs/Strategi](../../tools/arrigo/docs/Strategi)

## PVL (Project Builder “api”-sidan)

- Variabler exponeras genom att du lägger widgets/länkar på Arrigos “api”-sida.
- Läsning sker via GraphQL `data(path)`.
- Skrivning sker med nyckel `"{pvl_b64}:{index}"` (index från listan som Arrigo returnerar).

## Kontrakt

- Se [docs/contracts/ARRIGO_LOGIN_TOKEN_CACHE_CONTRACT.md](../contracts/ARRIGO_LOGIN_TOKEN_CACHE_CONTRACT.md)
