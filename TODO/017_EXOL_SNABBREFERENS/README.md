# 017 – EXOL snabbreferens (verifierad kunskap)

## Mål

- Samla det vi **vet** om EXOL baserat på:
  - våra `.tse`-filer
  - hur controllern beter sig
  - referensmaterial
- Minimera gissningar: allt här ska helst kunna pekas på som “observerat” eller “testat”.

## Status

- in-progress

## Nuläge

- `.tse` kompilerar → syntaxen är giltig.
- Ex: `ELSEIF` förekommer i våra filer och accepteras av compilern.
- Det betyder inte att logiken är perfekt; vi behöver en metod för att testa beteenden.

## Språkfrågor att bevisa

1) `IF/ELSEIF/ELSE/ENDIF`
   - Finns edge-cases? (t.ex. prioritet, bool-coercion, kortslutning)
2) Loopar (t.ex. `UpLoop` / `EndLoop`)
   - Exekvering per scan eller “kör klart”?
3) Variabeltyper
   - Hur representeras bool? (0/1, True/False)
   - Är numerik int/float? Finns avrundning?
4) Persistens
   - Behåller variabler värden mellan cykler? När nollställs?
5) Tid
   - Finns inbyggd tidsfunktion? Hur ofta körs tasks?

## Teststrategi (praktisk)

- För varje fenomen: skapa ett minimalt test-case i EXOL (en task) som sätter en tydlig signal (t.ex. en debug-flagga).
- Observera i controller/Arrigo: vad blev resultatet?
- Dokumentera: “Case”, “Förväntat”, “Observerat”, “Slutsats”.

## Nästa steg

- Samla alla `.tse` vi använder aktivt och lista vilka constructs de använder.
- Skapa 3–5 minimala testfall (ELSEIF, bool, loop, edge detect).
- Flytta bekräftade slutsatser till [docs/exol/README.md](../../docs/exol/README.md)
