# EXOL notes (project-specific)

This file captures the recurring "gotchas" and conventions used in this project.

## 1) Cv* naming (often feels "backwards")

In EXOL, `CvI` / `CvR` / `CvX` are named by the **input type** (source), not the output.

- `CvI(IExp)` = convert **from Integer**. Output depends on context (assignment / surrounding expression).
- `CvR(RExp)` = convert **from Real**.
- `CvX(XExp)` = convert **from Index/Long**.

Practical rule: Use the `Cv*` that matches the expression you already have.

## 2) Cmp* functions and typing

`CmpI`, `CmpR`, `CmpX`, `CmpT`, `Cmp$` are **typed comparisons**.

- Use `CmpI(...)` for Integer comparisons.
- Use `CmpR(...)` for Real comparisons.
- Use `CmpX(...)` for Index/Long comparisons.

Important: Some tooling/converters are stricter than EXOL runtime.

## 3) Logic (L) vs Integer (I)

A frequent source of converter errors:

- If a variable is Logic (`L`), test it as logic: `IF flag` (or `IF flag <> 0` only if the toolchain accepts it).
- Don’t feed a Logic variable into `CmpI(...)`.

## 4) Avoid new temp vars in planner blocks (VeryFast converter)

The Windows VeryFast conversion step may fail if it cannot deduce types for new temporaries.

Project convention:
- Prefer reusing already-declared integer temporaries in `EXOL_Variabels.tse`.
- If you must introduce a new temp, declare it explicitly in `EXOL_Variabels.tse`.

## 5) Non-ASCII characters can break compilation

Avoid smart quotes, long dashes, special symbols in comments/strings.

Use plain ASCII: `-` instead of `–`, `"` instead of smart quotes.

### 5a) “ASCII-only” policy (recommended)

Treat all `.tse` files as **ASCII-only**.

Avoid characters like:
- arrows: `→`, `⇒`, `<=` written as `≤`
- degree symbol: `°`
- smart quotes: `“”`, `‘’`
- long dashes: `–`, `—`
- other typography: `…`

Safe replacements:
- `→` / `⇒` / `≤` / `≥`  → use plain ASCII: `->`, `=>`, `<=`, `>=`
- `°` → write `deg` (e.g. `54 deg`) or just omit
- `“text”` → `"text"` or `"` depending on editor
- `–` / `—` → `-`
- `…` → `...`

### 5b) Quick check: find non-ASCII in EXOL files

Run from `EXOL_Filer`:

```bash
python - <<'PY'
from pathlib import Path
bad = []
for p in Path('.').glob('*.tse'):
	text = p.read_text(errors='replace')
	for i, line in enumerate(text.splitlines(), 1):
		if any(ord(ch) > 127 for ch in line):
			bad.append((str(p), i, line))

for p, i, line in bad[:200]:
	print(f"{p}:{i}: {line}")

if not bad:
	print("OK: no non-ASCII found")
else:
	print(f"Found {len(bad)} lines with non-ASCII")
PY
```

## 6) Planner behavior: keep “price choice” logic simple

Be careful adding constraints (like `MAX_INROW`) inside *anchor top-up* steps.
That can cause skipping cheap periods and selecting more expensive ones.

Where `MAX_INROW` is expected to apply in this project:
- GAP-fill
- SLACK-add

Where it should NOT be applied (unless explicitly requested):
- Anchor top-up / budget recheck anchor top-up

## 7) IF formatting: keep it multi-line

Some EXOL toolchains are sensitive to layout. Project rule:

- Don’t write one-line IF statements.
- Use separate lines for `IF`, the action(s), and `ENDIF`.

Preferred:

```text
IF cond
	Action = 1
ENDIF
```

Avoid:

```text
IF cond Action = 1 ENDIF
```

## 8) Variable declarations live in EXOL_Variabels.tse

Project rule:

- Do not declare variables inside runtime code files.
- Add new variables (temps, flags, diagnostics) in `EXOL_Variabels.tse`.

Reason: the Windows VeryFast conversion and/or EXOL compiler may fail when variables are introduced ad-hoc in code blocks.
