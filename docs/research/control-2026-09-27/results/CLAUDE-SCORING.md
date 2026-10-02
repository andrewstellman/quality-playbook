# Claude control arm: scoring

**Status: not blind.** The orchestrating session knew the target defects when it scored these reviews. It scored each run in two steps: first it searched the review for the defect's identifiers, then it read every matching section. A blind adjudication and the GPT arm are still to come.

## Repeated runs (28 September 2026): 10 runs per model for five repositories

- **What was run.** 100 runs: aiohttp, chi, express, calibre and bionemo, each reviewed 10 times by Opus and 10 times by Sonnet.
  - Run 01 is the original single run described below (`<model>-<repo>.md`, copied to `-run01.md`).
  - Runs 02–10 used the same prompt, scope and clean checkout, delivered as a task file (`/tmp/control/TASK-<repo>.md`) that contains the verbatim `STANDARD_REVIEW_PROMPT.md` text and the `SCOPES.md` row.
- **How a hit is scored.** A run counts as a hit only if the review reports the defect as a finding. Mentioning the code, or considering the defect and then setting it aside, is not a hit; those runs are listed separately.
- **otel and assertj** were not repeated, so they are still at one run per model.

| Target defect (found by Quality Playbook) | Opus hits | Sonnet hits | Considered but not reported |
|---|---|---|---|
| aiohttp `readuntil` separator split across chunks | **4/10** (runs 04, 05, 07, 09) | **1/10** (run 09) | opus-run10 listed it under "not reported" because in-tree callers use a one-byte separator |
| chi `GetHead` inside a mounted sub-router | 0/10 | 0/10 | All 10 Opus runs cite `get_head.go` as the *correct* pattern for their SupressNotFound finding; several Sonnet runs list it as checked with no defect |
| express sub-second `maxAge` gives `Max-Age=0` | 0/10 | 0/10 | sonnet-run05 tested `maxAge: 60000`, got the right answer, and moved on |
| calibre `/opds/navcatalog` malformed hex → 500 | 0/10 | 0/10 | `opds.py` was mostly read only in part or skimmed |
| bionemo AMPLIFY `_pad_weights` dtype/device | **9/10** (all but run 09) | **6/10** (runs 02, 03, 04, 05, 07, 09) | |
| bionemo THD context-parallel remainder tokens | 0/10 | 0/10 | sonnet-run06 noticed the missing divisibility check, then declined to report it because shipped configs satisfy the precondition |

For the four targets with 0 hits:

- **Rule of three.** With 0 detections in 10 runs, the 95% upper bound on the per-run detection rate is about 26% for each model. With both models pooled (0 in 20), it is about 14%.
- **What this shows.** For these four defects, standard review at these generous scopes misses them consistently, not by bad luck on a single run.

For the two targets standard review did find:

- **bionemo AMPLIFY** is found most of the time.
- **aiohttp `readuntil`** is found sometimes: 4 of 10 Opus runs and 1 of 10 Sonnet runs. The original single-run table below recorded it as "no" for both models; with more runs it moves to "found sometimes".

### Protocol deviations in runs 02–10

The task file said not to use the web. Seven Sonnet runs broke that rule, and every Opus run followed it:

- **Fetched the published or upstream express code to diff against the checkout:** sonnet-express runs 02, 06 and 07 (each disclosed and discarded it), and runs 08 and 09 (used `npm pack` as a diff baseline).
- **An internal sub-agent fetched upstream copies:** sonnet-aiohttp runs 03 and 06, per their own reports.

None of these seven runs found its target defect, so the deviations don't change any number in the table. Access to upstream code could only have helped the control.

### Environment notes

- Several calibre Sonnet runs again reported the valid Python 3.14 `except A, B:` syntax (PEP 758) as three "high" syntax errors. They are false positives, because the sandbox has Python 3.10.
- Some Go runs hit "no space left on device" until they pointed `TMPDIR` at their work directory.

---

## Original single-run scoring (run 01)

## Setup

- 14 runs: one Claude Opus and one Claude Sonnet sub-agent per repository, 28 September 2026.
- Every run got the identical prompt in `../STANDARD_REVIEW_PROMPT.md`, the scope in `../SCOPES.md`, and a clean checkout at the pinned commit. The checkouts contained no fixes, no evidence and no hints.
- One run each, no repetitions.
- The Sonnet bionemo run first failed to launch (the session hit its concurrent-subagent limit) and was re-run afterwards. Its prompt was identical.

## Did standard review find the nine defects?

| Defect (found by Quality Playbook) | Opus | Sonnet | Notes |
|---|---|---|---|
| aiohttp `readuntil` separator split across chunks | no | no | Opus reported 7 other aiohttp defects and Sonnet 9; neither mentions `readuntil` |
| chi `GetHead` inside a mounted sub-router | no | no | Opus cites `get_head.go` only as the *correct* pattern for its SupressNotFound finding |
| express sub-second `maxAge` gives `Max-Age=0` | no | no | |
| otel `UrlParser` bracketed IPv6 | **yes** (Opus finding 2) | no | Opus also found the userinfo case and a `getPath` query bug |
| otel `ForwardedHostAddressAndPortExtractor` IPv6 | **yes** (Opus finding 3) | no | Opus also found the comma-list case |
| assertj `Percentage.toString()` overflow | **yes** (Opus finding 3) | no | Sonnet read `Percentage.java` and reported "no logic defects" |
| calibre `/opds/navcatalog` malformed hex → 500 | no | no | Opus read `opds.py` only in part |
| bionemo AMPLIFY `_pad_weights` dtype/device | **yes** (Opus finding 2) | no | Opus's impact statement (it trips the `apply_transforms` dtype assertion) is more accurate than the QPB-generated PR draft's "silently upcasts" |
| bionemo THD context-parallel remainder tokens | no | no | Opus found a different THD defect in `modeling_esm_te.py` |
| **Found** | **4 of 9** | **0 of 9** | |

## What this can and cannot show

- **Selection bias.** The nine defects were chosen *because* Quality Playbook runs found them, so Quality Playbook's recall on this set is 100% by construction. The table can only show which QPB findings standard review misses, not the reverse. A fair comparison needs the symmetric question too: of the defects standard review found, how many did the QPB runs find?
- **Standard review found things too.** For example:
  - aiohttp: `Forwarded` parsing, the multipart `_charset_` field, `Host` dropped on retry
  - calibre: `loop.py` closing the wrong connection, a ban list that never expires
  - express: typed-array body corruption
  - otel: `getPath` matching inside the query string
  - assertj: `TemporalUnitLessThanOffset` overflow

  None of these have been verified or checked against the QPB runs.
- **Models are not matched.** The QPB findings came from historical runs with various models and QPB versions (the gson run was GPT-5.4). This control used current Claude Opus and Sonnet. The research plan's §3 requires matched models; this doesn't meet that.
- **The scopes were generous to the control.** Each control run reviewed the directory containing the defect, which for assertj (8 files) and express (6 files) is close to pointing at it. The QPB runs reviewed whole repositories.
- **One run per cell.** Run-to-run variance is unknown.
- **Opus clearly outperformed Sonnet in this arm (4 vs 0),** a larger gap than any other factor here.
- **Two errors caused by the environment:**
  - `sonnet-calibre` reported three "high" syntax errors that are valid Python 3.14 syntax (PEP 758). The sandbox has Python 3.10, and calibre master requires 3.14. These are false positives.
  - The Sonnet review panel reviewer S7 made the same mistake.

## Findings from the five chi fixes QPB had already seen reported upstream

`opus-chi` independently found all five chi findings from the historical QPB run that had turned out to be already reported upstream: SupressNotFound, Compress `q=0`, AllowContentEncoding comma lists, ContentCharset quoted charset, and Recoverer `Upgrade`. Those defects are visible enough that other people had already reported them.

That doesn't generalise into "control finds only what's already known". The four target defects Opus did find (both otel, assertj, bionemo amplify) had no upstream report either. Among the nine unreported targets, the split is 4 found and 5 missed, one run each. The five missed are aiohttp, chi GetHead, express, calibre and bionemo THD.
