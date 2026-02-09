# EXOL / Regin – dokumentation och arbetssätt

Målet här är att samla *det vi faktiskt vet* om EXOL-språket och hur våra `.tse`-filer beter sig i controllern.

## Nuläge

- `.tse`-filerna kompilerar, så syntaxen är giltig.
- Det betyder inte att logiken är optimal eller robust.

## Viktiga saker att bevisa (utan att gissa)

1) Vilka kontrollstrukturer stöds exakt (t.ex. `IF`, `ELSEIF`, loopar).
2) Hur variabeltyper beter sig (bool/int/float/string).
3) Exekveringsmodell: cykeltid, ”scan”, och vad som händer vid villkorsväxling.
4) Hur ”tasks” triggas: tid, flaggor, latch, edge-detect.

## Rekommenderat arbetssätt för förbättring

- För varje misstänkt beteende: skapa ett *minimalt test-case* (1 fil / 1 fenomen).
- Dokumentera resultatet i `TODO/017_EXOL_SNABBREFERENS/README.md`.
- Flytta stabila slutsatser hit när de är bekräftade.

## Nästa steg

- Skapa en “snabbreferens” (syntax + fallgropar) baserat på våra faktiska `.tse`-filer och referenstext.
- Lista vilka signaler som är kontrakt mellan EXOL ↔ Arrigo ↔ Pi.
