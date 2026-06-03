# 05 — Walk-time Gating Logic

**Source:** `bus_tracker.py::format_arrival` (CLI) and the HTML template's `render()` function (web). Both implement the same four-bucket state machine.

## The core math

For each upcoming arrival, bus-tracker computes:

```
need   = walk_minutes + cushion_minutes
buffer = minutes_away - need
```

`need` is the time from "now" until you'd need to have left the house. `buffer` is the slack: positive = time to spare, negative = already too late.

**`cushion_minutes`** comes from the top-level config (default 0) and is applied uniformly across all stops. It's a "safety margin" for users who want to leave earlier than the math strictly requires.

## Four states, in exact order

The code evaluates the buckets in this order (first match wins):

| Order | Condition | CLI label | Web label | Web color class |
|---|---|---|---|---|
| 1 | `buffer < 0` | `✗ already too late` | `Too late` | `action-late` (muted + strikethrough) |
| 2 | `buffer < 2` | `⚡ leave NOW` | `⚡ Leave NOW` | `action-now` (red, bold) |
| 3 | `buffer < 5` | `⏳ leave in ~{buffer:.0f} min` | `Leave in ~{round(buffer)} min` | `action-soon` (yellow) |
| 4 | else | `✓ plenty of time ({buffer:.0f} min to spare)` | `{round(buffer)} min to spare` | `action-go` (green) |

**Thresholds are hardcoded** as `0`, `2`, and `5` minutes. There is no config override — the design decision is that these thresholds are semantic to the product ("NOW" ≠ "soon" ≠ "plenty") and shouldn't drift per-deployment.

## The `minutes_away` special cases

Before the gating math runs, the CLI and web paths both handle these cases:

- **`minutes_away is None`** (no arrival time in the SIRI response) → display "time unknown" (CLI) / "Time unknown" (web). No hurry label, no buffer math.
- **`minutes_away < 1`** → display "arriving now" (CLI) / "Now" (web). Gating math still applies with `minutes_away = 0ish`, so these will almost always hit bucket 1 ("too late") unless `need` is 0.
- **`minutes_away is None` combined with non-None `need`** → no hurry label is attached. This is correct: we can't compute a buffer without an ETA.

Minutes are formatted with `:.0f` (CLI) or `Math.round` (web) — both effectively truncate to whole minutes for display.

## Bucket-1 subtlety

`buffer < 0` means the bus will arrive **before** you could walk to the stop. The label is rendered with a strikethrough in the web UI (`text-decoration: line-through`), so the whole row looks visually "canceled." The build chat specifically wanted this — a "don't bother chasing" signal rather than hiding the bus entirely.

## Up to 4 arrivals per stop

Both the CLI (`stop['arrivals'][:4]`) and web (`stop.arrivals.slice(0, 4)`) cap the display at the nearest 4 arrivals. Beyond that, the next bus is far enough away that the immediate leave-vs-wait decision is already determined.

## Spec-auditor focus

- **Bucket order must be evaluated top-down.** If the code evaluates `buffer < 2` before `buffer < 0`, the "leave NOW" message would steal from "too late" — wrong. The current implementation uses `if`/`elif`/`elif`/`else`, which guarantees top-down.
- **`cushion_minutes` must be added uniformly**, not conditionally. If the CLI adds cushion but the web doesn't (or vice versa), the two UIs disagree — a user-visible inconsistency.
- **Thresholds of 0 / 2 / 5 must match between CLI and web.** Any drift is a parity bug.
- **`minutes_away is None`** must not crash the renderer. Current code short-circuits to "time unknown" before reaching the buffer math.
- **Negative `walk_minutes`** is nonsense input but would currently shift the bucket boundaries into the future (you'd always have time to spare). Input validation at config-load time would be a reasonable hardening.
- **`cushion_minutes` of zero vs absent** should be equivalent (both evaluate as 0). The current code uses `.get("cushion_minutes", 0)` which handles both.

## What's NOT in the gating

- No persistence — the gating is recomputed from scratch on every refresh. Flicker across bucket boundaries as `minutes_away` ticks down is visible in the UI.
- No "you've already left" state tracking. The user starting to walk doesn't change what bucket the next arrival falls into.
- No per-stop threshold customization. Every stop uses the same `need = walk_minutes + cushion_minutes` formula.
