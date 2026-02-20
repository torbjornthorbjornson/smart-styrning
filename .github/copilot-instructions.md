# Copilot instructions for this repo (EXOL_Filer)

When working on EXOL code in this repository:

1) **Before changing semantics**, search/read `Referens_guide` for the relevant function(s), especially `Cv*` and `Cmp*`.
2) Prefer **minimal, localized changes**; do not add new constraints/optimizations unless explicitly requested.
3) Be conservative with **typing**:
   - Declare new temporaries in `EXOL_Variabels.tse`.
   - Avoid introducing new undeclared temps in planner blocks used by the Windows VeryFast conversion.
4) Keep source **ASCII-only** (avoid smart quotes/dashes/symbols).
5) If there is a choice between making something "clever" vs "predictable", choose **predictable**.

If the user reports a Windows conversion error, prioritize matching the converter’s typing rules over stylistic refactors.
