VERDICT: FIX-REQUIRED

# Round-5 closure audit — self-Council verification of `b863deb`

**Scope:** commit `b863deb` ("close the self-Council findings (round 4)") against the three items
`round4_closure.md` left open — B-5 (the sixth bypass), P2 mutation E4, and P3 (four weak
assertions) — plus the charter's real question: *has the loop ended?* Branch `1.6.0`, repo
`/Users/andrewstellman/Documents/QPB`.

**Method:** everything below was executed; no commit-message claim is taken on trust. I reviewed in
a detached `git worktree` at `b863deb` so nothing I did could perturb the working tree. I built an
independent probe harness driving `check_render_contract` over synthesized documents; attacked the
fence construct as a *grammar* (32 shapes, both directions); cross-checked every CommonMark claim
against a reference parser (`markdown_it`, `commonmark` preset) rather than against my own reading
of the spec; staged 18 manifest mutations against the real `ManifestUnchangedInvariantTests`;
AST-walked every `assertIn` in both new test modules against the gate's own PASS vocabulary; and
swept all 105 archived trees under `repos/` and `metrics/` at `3ef3a7e` and `b863deb`.

**Concurrency note.** The working tree was not quiescent during this review. At the start
`git status` was clean; ~60s later `quality_gate.py` carried 28 uncommitted lines adding HTML-block
handling; by the end that work had landed as **`4255002`** ("extend the suppressed-region rule to
HTML blocks"), which is now HEAD. I have therefore reported each finding against **both**
`b863deb` (my charter) and `4255002` (current HEAD). Both blocking findings below survive at
`4255002`.

---

## Summary table

| Round-4 item | Status |
|---|---|
| **B-5** — full CommonMark fence grammar | **CLOSED** — 19 bypass shapes, 0 bypasses; old `_RENDER_FENCE_RE` gone; one implementation |
| Unterminated fence = FAIL | **CLOSED** — fires on all 4 shapes, 0 false fires on 6 legitimate documents |
| **E4** (P2) — field deletion | **CLOSED** — 11 field-mutation shapes, all detected |
| **P3** — four weak assertions | **CLOSED for the four named**; 2 of the identical class remain (follow-up) |
| Full suite | **CONFIRMED** — 2531 at `b863deb`, 2534 at HEAD, 0 failures |
| Three fixtures FAIL=0 WARN=0 | **CONFIRMED** (15 PASS lines each, genuinely evaluated) |
| Archived sweep, 105 trees | **CONFIRMED** zero flips `3ef3a7e` → `b863deb` |
| Fixture inputs SHA-256 unchanged | **CONFIRMED** by hash, not mtime |
| Tree clean | **CONFIRMED** at end (after `4255002` landed) |
| **B-6 (new)** — fence info-string polarity inversion | **NEW — BLOCKING** (survives at HEAD) |
| **B-7 (new)** — HTML block types 2 and 6 | **NEW — BLOCKING** (survives at HEAD) |

---

## What genuinely closed

### B-5 — the fence grammar: **CLOSED**

`_RENDER_FENCE_RE` is gone (`grep` confirms zero references). There is exactly one fence
implementation: `_render_blank_fences_ex`, with `_render_blank_fences` a thin wrapper. Every
consumer routes through it — `_render_scan_internals`, `_render_req_headings`, the
`structure_text` slicing, and the new pre-flight check.

I attacked it as a grammar, not a list of shapes. **Nineteen** bypass-direction shapes, each a flat
requirement list trying to synthesize mandatory structure out of quoted material:

`~~~` · backtick 3/4/6 · tilde 6 · closer longer than opener · 1-space-indented opener with
unindented closer · unindented opener with 3-space-indented closer · 3-space indent both ·
4-space indent · tab indent · plain info string · info string with trailing space · nested fence
inside a fence · empty fence followed by a real fence · CRLF line endings · closer with trailing
text.

**Zero bypasses.** Seventeen scored FAIL=4 (all three MP-1 messages plus MP-2); the remaining two
scored FAIL=1 — for a different reason, discussed under B-6.

Thirteen false-positive-direction shapes (a conforming document quoting a block, which must score
FAIL=0 WARN=0): eleven clean. This is a real change in kind from rounds 2-4 — the construct was
enumerated rather than sampled, and the enumeration holds everywhere I pushed on it *within the
grammar the regex models*. Credit where due.

### Unterminated fence — the judgment is right, and it holds

Making this a FAIL rather than a blanking rule is the correct call. Per CommonMark everything after
an unterminated opener is inside the code block, so every downstream check would pass by default on
a document the contract cannot read. Passing-by-default is the failure mode this whole Council
exists to catch; refusing to certify is failure-safe.

Fires on all four unterminated shapes (plain, tilde, wrong-delimiter closer, short closer).
**No false fires** on six legitimate documents, including the case the charter specifically named —
an even number of fences where one *contains* a line that looks like a fence:

| Document | `unterminated` fires? |
|---|---|
| 4-backtick fence quoting a 3-backtick line | no — FAIL=0 WARN=0 |
| tilde fence quoting a whole backtick fence | no — FAIL=0 WARN=0 |
| backtick fence quoting a tilde line | no — FAIL=0 WARN=0 |
| two separate fences | no — FAIL=0 WARN=0 |
| fence as the very last line, closed, no trailing newline | no — FAIL=0 WARN=0 |
| closer with trailing whitespace | no — FAIL=0 WARN=0 |

The three regenerated fixtures are unaffected (FAIL=0 WARN=0, 15 PASS lines each).

### E4 / field presence — **CLOSED**

`test_no_record_loses_a_field_it_started_with` iterates every field of every paired record.
Mutation-bitten through a monkeypatched `_paired`, one record only:

| Mutation | Result |
|---|---|
| drop `title` on one record (express, virtio) | **detected** |
| blank `title` to `""` | **detected** |
| set `title` to `None` | **detected** |
| drop `functional_section` | **detected** (also caught by the E3-era check) |
| drop `references` / `use_cases` / `tier` / `specificity` / `conditions_of_satisfaction` | **detected** |
| drop `text` / `pattern` (chi) | **detected** |
| **add** a field to one record | **detected** |

Note for the record: my first sweep reported "UNDETECTED" for `title` — that was **my** harness
bug, not a defect. I had scoped the mutation to `chi`, whose records have no `title` field, so
nothing was mutated. Re-run against `express` and `virtio` it is detected. I flag this because an
unexamined "undetected" line here would have been a false accusation of exactly the kind this
Council is supposed to be careful about.

I could not find an E5 that still passes.

### P3 — the four named assertions: **CLOSED**

All four now assert phrasing that appears only in FAIL output. Verified by harvesting the gate's
complete PASS vocabulary (15 lines) from a clean run and checking each fragment against it:

| Was | Now | In PASS output? |
|---|---|---|
| `"tool-contract REQ"` | `"tool-contract REQ(s) rendered into the"` | no |
| `"intro prose"` | `"lack intro prose"` | no |
| `"terminal period"` | `"end with a terminal period"` | no |
| `"coverage-and-gaps statement"` | `"no coverage-and-gaps statement"` | no |

### Regression evidence

- **Suite:** 2531 tests at `b863deb`, 2534 at HEAD `4255002`, **0 failures**, skipped=13. (The
  worktree run showed 1 failure + 6 errors; all are `repos/`-baseline artifacts of an untracked
  directory absent from a worktree, not regressions. Confirmed by the clean run in the real tree.)
- **Archived sweep:** 105 trees under `repos/` and `metrics/`, `3ef3a7e` → `b863deb`: **zero**
  FAIL/WARN flips.
- **Fixture inputs:** all six preserved inputs SHA-256 **identical** to their introducing commits,
  verified by hash against `git show`, not by mtime. Untouched since `edc5cec` / `f9984ae`.
- **Tree clean** at end of review.

---

## BLOCKING — B-6: the fence info-string polarity inversion

`_RENDER_FENCE_OPEN_RE` models the info string as `[^`~]*`. CommonMark does not. A **backtick**
fence's info string may not contain backticks — but it **may** contain tildes; a **tilde** fence's
info string may contain anything at all, backticks included. Confirmed against the reference
parser, not inferred:

```
>>> md.parse("```text~ex\nexample code\n```\n\n### REQ-402: a real heading\n...")
fence           map=[0, 3] info='text~ex' content='example code\n'
heading_open    map=[4, 5]
inline          map=[4, 5] content='REQ-402: a real heading'
```

So ` ```text~ex ` **is** a valid opener. The scanner rejects it, and the fence pairing shifts by one
delimiter: the line CommonMark treats as the **closer** becomes the scanner's **opener**, and
everything CommonMark renders as live document prose after that block is blanked.

This is not merely the false-positive direction round 4 described. It is exploitable as a **bypass**,
because the blanked region is a region the reader sees as ordinary document text. Executed:

```
EXPLOIT (violations placed in the inverted region):  FAIL=0 WARN=0
CONTROL (identical violations, no fences):           FAIL=5 WARN=0
>>> 5 violations suppressed
```

The suppressed violations were a 200-character REQ title (C-6) and leaked derivation internals
(C-5). The document renders, in any conforming Markdown viewer, with those defects fully visible.
The gate certifies it clean.

**Still open at HEAD `4255002`** — `4255002` changed HTML handling only; the info-string regex is
untouched.

The fix is not another shape: `[^`~]*` should be `[^`]*` for backtick fences and unrestricted for
tilde fences, which is the actual grammar rule the current regex approximates.

## BLOCKING — B-7: HTML blocks, types 2 and 6

The charter asked whether a bypass *class* exists outside fences and headings. It does: **HTML
blocks**. `b863deb` handles none of them. `4255002`, landed mid-review, handles CommonMark HTML
block **type 1** only (`pre`, `script`, `style`, `textarea`). Types **2** (comments) and **6**
(block-level tags: `div`, `table`, and ~60 others) suppress Markdown structure identically and are
still open.

Reference parser, both cases:

```
div      heading_open present: False  tokens=['html_block']
table    heading_open present: False  tokens=['html_block']
comment  heading_open present: False  tokens=['html_block']
```

Executed exploit at **HEAD `4255002`** — a document whose three mandatory sections exist only
inside a `<div>`:

```
## Overview
...
<div>
## Actors and roles
## Use cases
## Traceability appendix
</div>

## Request routing
... two REQs ...
```

```
FAIL=0 WARN=0
   PASS: Actors & roles section present
   PASS: Use cases section present
   PASS: Traceability appendix section present
```

A reader of the rendered document sees **none** of those three sections — the `<div>` block is raw
HTML and produces no headings. The gate reports all three present. That is the §5.2 mandatory-part
list defeated in full.

The HTML-comment variant (`<!--` … `-->`) also defeats MP-1; it currently scores FAIL=2 only
because the *unrelated* derivation-internals check happens to notice a raw `<!--`. A guard held by
an unrelated check is not a guard.

I also tested and **cleared** four other candidates — 4-space-indented code blocks, tab-indented
headings, blockquoted headings (`> ## Actors`), and list-nested headings (`- ## Actors`). All are
correctly rejected, because `_RENDER_LEVEL2_RE` is anchored at `^##`. YAML front matter is a false
alarm on my part: CommonMark renders `---`-delimited content as `hr` + real headings, so the gate
and the renderer agree.

---

## Has the loop ended?

**Partly — and the honest answer is more interesting than yes or no.**

`b863deb` is genuinely structurally different in one dimension. Rounds 1-4 each patched the shape
they were shown; `b863deb` replaced a shape-matcher with a scanner over an enumerated grammar, and
that enumeration **held against all nineteen fence shapes I could construct**. That is not the next
patch. Within the fence construct, the loop did end.

But the loop did not end at the level the round-4 diagnosis identified, and the evidence is
unusually clean, because it happened *during this review*:

1. **The grammar was enumerated from the wrong source.** The scanner enumerates the fence grammar
   as the worker understood it, not as CommonMark defines it. The info-string rule was
   approximated — `[^`~]*` instead of the real asymmetric rule — and that single approximation is
   B-6, a full FAIL=0 bypass. The way to catch this was to check the enumeration against a
   reference parser. Neither side did that until this round.

2. **The construct boundary was drawn at "fences" when the real boundary is "regions where
   Markdown structure is suppressed."** Fences are one member of that class. HTML blocks are
   another, and were never considered by `b863deb` at all.

3. **Most tellingly: `4255002` reproduced the exact pattern in real time.** Shown HTML blocks as a
   concept, it implemented the four tags of type 1 — the shape — and stopped, leaving types 2 and 6
   open. A `<div>` still defeats the entire mandatory-part list at HEAD. The commit message for
   `b863deb` says enumerating the grammar once is "the way out of that loop"; `4255002`, written
   hours later, is another lap.

4. **A smaller instance of the same thing in the test code.** P3 named four weak assertions; all
   four are fixed. Two assertions of the *identical* class remain in the same file, at lines 903
   and 920 (`assertIn("RUN_CONTRACT.md", out)` as the only message assertion — a fragment that also
   appears in `PASS: RUN_CONTRACT.md carries all 1 tool-contract REQ(s)`). Fixed what was listed;
   did not sweep for the class. Non-blocking, but it is the same shape as everything above.

The generalizable lesson, offered without prescribing the fix: **the exit condition is not "cover
the grammar," it is "check the model against an authority."** Every bypass in rounds 3-5 has been a
gap between the gate's model of Markdown and Markdown itself, and every one would have been caught
in minutes by differential-testing `_render_blank_fences` against a reference CommonMark parser
over generated documents. That is a test one writes once, and it does not need to be re-derived
when the next construct appears.

---

## Non-blocking follow-ups

1. **P3 residue** — two assertions of the round-4 class remain (`test_render_contract_v160.py`
   lines 903, 920). Both are currently carried by their `assertGreaterEqual(fails, 1)`, so latent,
   not live. Same disposition round 4 gave the original four.
2. **`_render_blank_fences` has no direct unit tests.** It is exercised only end-to-end through
   `check_render_contract`. A direct table-driven test over `(input, expected_blanked_output)`
   would have made B-6 visible by inspection.
3. **Manifest field *addition* is detected but only incidentally** — the fixture for `virtio`
   already carries an `after`-only field (`conditions_of_satisfaction`), which the invariant
   tolerates by iterating `before` fields. Worth an explicit decision about whether the render may
   add fields.

---

## Verdict

**FIX-REQUIRED.** Two blocking bypasses, both executed and both open at current HEAD `4255002`:

- **B-6** — fence info-string polarity inversion: FAIL=0 WARN=0 on a document with five real
  violations (control: FAIL=5). CommonMark divergence confirmed against a reference parser.
- **B-7** — HTML block types 2 and 6: FAIL=0 WARN=0 on a document with none of the three §5.2
  mandatory sections, all three reported present.

Everything `round4_closure.md` asked for is genuinely closed — B-5, the unterminated-fence
judgment, E4, and the four P3 assertions all verified by execution, with no regressions across
2534 tests, 105 archived trees, and six SHA-256-pinned fixture inputs. `b863deb` is the strongest
commit of the five rounds. It is still not shippable, because the construct it enumerated so
carefully was enumerated against the wrong authority, and the class it belongs to is larger than
fences.
