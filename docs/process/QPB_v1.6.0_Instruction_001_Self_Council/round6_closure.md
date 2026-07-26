VERDICT: FIX-REQUIRED

# Round-6 closure audit — self-Council verification of `94c7e3d`

**Scope:** commit `94c7e3d` ("close B-6/B-7 and end the loop with a differential test") against the
two blocking findings `round5_closure.md` left open — B-6 (fence info-string polarity inversion) and
B-7 (HTML block types 2 and 6) — plus the charter's real question: **has the loop ended?** Branch
`1.6.0`, repo `/Users/andrewstellman/Documents/QPB`, HEAD confirmed `94c7e3d`.

**Method:** everything below was executed. No commit-message claim is taken on trust. I built an
independent probe harness driving `check_render_contract` over synthesized documents (reusing the
suite's own `RenderContractBase` fixture so the baseline is the shipped one); reproduced both round-5
exploits; mutation-bit the differential test three ways against a `shutil.copy2` pristine snapshot
with scoped `__pycache__` purges; measured the case list's discriminating power against two
degenerate models; attacked the case list's own coverage with 35 constructs it does not contain; and
swept all 105 archived `quality/` trees at three commits.

The tree was clean at start and at end, and `quality_gate.py` is byte-identical (SHA-256
`616cefc9…`) to the committed version after every mutation bite.

---

## Summary table

| Round-5 item | Status |
|---|---|
| **B-6** — fence info-string polarity inversion | **CLOSED** — exploit region no longer blanked; exploit FAIL == control FAIL |
| **B-7** — HTML block types 1, 2, 6 | **CLOSED for the types it models** — all four wrappers FAIL, no false PASS |
| C-5 interaction (comment blanked for structure, visible for C-5) | **CONFIRMED** — both halves hold |
| Differential test genuinely runs | **CONFIRMED** — `markdown_it` 4.2.0, 6 tests, 0 skipped |
| Differential test is mutation-bitten | **CONFIRMED** — 3 bites, all RED, all restore green |
| Differential cases discriminate | **CONFIRMED** — 31 of 33 discriminate against a degenerate model |
| `INTENTIONAL_DIVERGENCES` honest | **CONFIRMED** — both conservative, both guarded |
| Full suite | **CONFIRMED** — 2540 tests, 0 failures, skipped=13 |
| Three fixtures FAIL=0 WARN=0 | **CONFIRMED** — 15 PASS lines each, genuinely evaluated |
| Archived sweep, 105 trees | **CONFIRMED** — 0 render-contract FAILs; 0 flips `4255002` → HEAD |
| Fixture inputs SHA-256 unchanged | **CONFIRMED** by hash against `edc5cec` |
| Tree clean | **CONFIRMED** |
| **B-8 (new)** — HTML block **type 7** | **NEW — BLOCKING**, full FAIL=0 bypass |

---

## What genuinely closed

### B-6 — fence info-string polarity inversion: **CLOSED**

`_RENDER_FENCE_OPEN_RE` is now per-delimiter — `[^`]*` for a backtick fence, unrestricted for a
tilde fence — which is the actual CommonMark rule, not an approximation of it.

I rebuilt round 5's exploit shape: a violating region (an over-120-character REQ-004 title plus a
C-5 derivation-internals line) bracketed by two ` ```text~ex ` fences, so that under the old regex
both openers are rejected and the pairing inverts onto the closers.

```
CONTROL (identical violations, no fences):  FAIL=1 WARN=0
EXPLOIT (B-6 info-string inversion):        FAIL=1 WARN=0
>>> 0 violations suppressed
```

At the model level the region is no longer blanked — both `"Handler panics"` and the
`"TODO: ask the user"` C-5 line survive `_render_blank_fences` — and a reference parser confirms all
eight `###` headings remain live in that document. The inversion is gone.

### B-7 — HTML blocks: **CLOSED for types 1, 2 and 6**

I moved all three §5.2 mandatory sections (`Actors and roles`, `Use cases`,
`Traceability appendix`) inside four different HTML wrappers and checked the reference parser and
the gate against each other:

| Wrapper | CommonMark type | Mandatory `h2`s the reader sees | Gate |
|---|---|---|---|
| `<pre>` | 1 | none | **FAIL=3** |
| `<!-- -->` | 2 | none | **FAIL=4** |
| `<div>` | 6 | none | **FAIL=3** |
| `<table>` | 6 | none | **FAIL=3** |

No false PASS on any of the three mandatory sections in any variant. Round 5's `<div>` exploit,
which scored FAIL=0 with all three reported present, now scores FAIL=3 and names all three as
missing. The type-2 case FAILs 4 — three MP-1 messages **plus** C-5 — so it is no longer a guard
held by an unrelated check; the MP-1 guard fires on its own.

`<div>` block termination is correct in both directions:

- `<div>\nquoted\n</div>\n\n## Actors and roles` — reference sees the heading, so do we (the block
  ends at the blank line, not at the closing tag).
- `<div>\nquoted\n## Actors and roles\n\n## Use cases` — **no closing tag**; reference sees only
  `Use cases`, and so do we. The blank-line termination rule, not a tag-matching rule, is what is
  implemented, which is what CommonMark specifies.

### The C-5 interaction: **both halves hold**

This was the part of the commit message most likely to be a rationalization, and it is not.

- A document carrying `<!-- cluster: heterogeneous -->` still **FAILs C-5**:
  `derivation internals leaked into the rendered document: HTML comment at line 6; cluster:
  annotation at line 6`. The `blank_html_comments=False` argument threaded into
  `_render_scan_internals` does exactly what it claims.
- A document whose mandatory headings live inside an HTML comment does **not** get them counted as
  structure — FAIL=4, all three reported missing.

The asymmetry is principled, not convenient: a comment is invisible to the reader (so it cannot
supply structure) and is itself the defect C-5 reports (so it must stay visible to that scan).

### The differential test: **it works, and it is bitten**

It is not silently skipping. `markdown_it` 4.2.0 is installed; all 6 tests run and pass, 0 skipped.

**Mutation bites** — each re-introduces one real historical defect, runs the differential test, and
restores from a pristine `shutil.copy2` snapshot with a scoped `__pycache__` purge:

| Bite | Differential test | Restored |
|---|---|---|
| B-6: info-string regex back to `[^`~]*` | **RED** | green |
| B-7: type-6 HTML handling disabled | **RED** | green |
| B-7: type-2 (comment) handling disabled | **RED** | green |

The test detects all three. It is a real guard, not decoration.

**Discriminating power** — 35 cases, 2 allowlisted, **33 tested** (the commit message says 34; minor,
see below). I re-scored every case against two degenerate models:

| Model | agree | disagree |
|---|---|---|
| the real `_render_blank_fences` | 33 | **0** |
| identity (blank nothing) | 12 | **21** |
| blank everything | 23 | **10** |

The two disagreement sets are disjoint, so **31 of 33 cases discriminate against at least one
degenerate model** — 21 pin the suppression direction, 10 pin the "don't over-blank" direction. Only
two (`fence_backtick_indented`, `indented_code_block`) discriminate against neither; both are
negatives the probe regex rejects on indentation alone. This is a genuinely load-bearing case list,
not 34 rows that trivially agree.

**`INTENTIONAL_DIVERGENCES` is honest.** `blockquoted` and `list_item` are both conservative — we
decline to see a heading the reference parser sees, so the mandatory-part checks FAIL rather than
pass. Neither can be exploited: seeing *less* structure cannot manufacture a §5.2 section that isn't
there. And the classification is defended by two tests that a lazier author would not have written:
`test_every_intentional_divergence_still_diverges` fails when a row goes stale, and
`test_divergences_are_conservative_not_permissive` fails if a row ever becomes a bypass. This is
allowlisting done right.

### Regression evidence — clean

- **Suite:** 2540 tests, **0 failures**, skipped=13. Matches the claim exactly.
- **Three regenerated fixtures:** chi, express, virtio each **FAIL=0 WARN=0**, 15 PASS lines each,
  genuinely evaluated (not inert).
- **Archived sweep, 105 trees** under `repos/` and `metrics/`: 47 inert (pre-v1.6.0), 58 evaluated,
  **0 render-contract FAILs**. `4255002` → `94c7e3d`: **0 flips**. The 5 WARNs present are identical
  at both commits, so they are not this commit's doing. (The pre-work baseline `39cc939` has no
  `check_render_contract` at all, so a function-level diff against it is degenerate; round 5 already
  established the whole-gate exit-code baseline.)
- **Fixture inputs:** all six `REQUIREMENTS.before.md` / `requirements_manifest.before.json`
  SHA-256 **identical** to `edc5cec`, verified by hash against `git show`.
- **Tree clean**; gate SHA-256 unchanged after all three mutation bites.

---

## BLOCKING — B-8: CommonMark HTML block **type 7** is a full FAIL=0 bypass

`94c7e3d` models HTML block types 1, 2 and 6 and **deliberately excludes type 7**, in a code
comment:

> `type 7 (any complete tag on its own line) is excluded on purpose because it would swallow
> ordinary inline HTML an adopter might legitimately use.`

Type 7 is *any* complete tag alone on a line, preceded by a blank line, running until the next blank
line. It suppresses Markdown structure exactly as types 1, 2 and 6 do. Executed at HEAD `94c7e3d` —
the three §5.2 mandatory sections wrapped in `<span>`:

```
<span>
## Actors and roles
Application developers mount routers; operators deploy behind proxies.
...
<span>
## Use cases
### UC-01: Developer mounts a sub-router
...
<span>
## Traceability appendix
UC-01 → REQ-001, REQ-002, REQ-003
```

```
reference parser h2 headings:  Overview, Request routing, Error handling, Cross-cutting concerns
mandatory sections the READER sees:  []

GATE RESULT: FAIL=0 WARN=0
   PASS: Actors & roles section present
   PASS: Use cases section present
   PASS: Traceability appendix section present
```

This is round 5's B-7 verbatim, one type later: a reader of the rendered document sees **none** of
the three mandatory sections, and the gate certifies the document clean with all three reported
present. The §5.2 mandatory-part list is defeated in full. `<mytag>`, `</span>` and `<a href="x">`
all work identically — I confirmed four type-7 shapes, all bypasses.

**The stated rationale for the exclusion is factually wrong**, and I checked it against the same
authority the commit chose rather than against my reading of the spec:

| Document | Reference parser |
|---|---|
| `Some prose with <span>inline</span> markup.` | `paragraph` — **not** an HTML block |
| `Some prose <span>` mid-paragraph | `paragraph` — **not** an HTML block |
| `<br>` alone on a line after a blank line | `html_block` |
| `<img src="x.png">` alone on a line | `html_block` |

Type 7 **cannot interrupt a paragraph**, so it never swallows the ordinary inline HTML the comment
is worried about — that case is a paragraph in CommonMark and would stay a paragraph for us. And a
lone `<br>` or `<img>` on its own line genuinely *is* an HTML block, so blanking it is **agreement**
with CommonMark, not an over-fire. The cost the exclusion was purchased with does not exist.

Two things make this worse than an ordinary missed construct:

1. **It is a permissive divergence, which this module's own test forbids.**
   `test_divergences_are_conservative_not_permissive` exists precisely to fail when a divergence
   lets us see structure the reference parser does not. Type 7 is exactly that — yet it is not in
   `INTENTIONAL_DIVERGENCES`, so the guard never sees it. The divergence lives in a code comment,
   where no test can reach it. An allowlist that a divergence can route around is not an allowlist.

2. **The case list has no type-7 case.** The commit's central claim is that it "stops hand-modelling
   CommonMark" and checks the model against an authority. But the authority is only consulted on the
   34 documents someone chose to write down, and the one construct that was consciously excluded
   from the model was also, necessarily, excluded from the cases. The hole in the coverage is
   exactly aligned with the hole in the model — which is the round-5 pattern reproduced inside the
   very artifact built to end it. Types 3/4/5 are excluded on the same footing (defensibly — they
   are genuinely implausible in a requirements document — but likewise with no case and no
   allowlist row).

**Commit-message accuracy.** "stops hand-modelling CommonMark and differentially tests
`_render_blank_fences` against markdown_it's commonmark preset across 34 constructs" is materially
overstated in its first half: four block types remain hand-excluded by a comment, one of them
exploitably, and none of the four appears in the case list. ("34 constructs" is also 35 cases / 33
tested — trivial, noted only for the record.) Everything else in the message I checked held.

---

## Non-blocking follow-ups

1. **The differential test does not test the gate's real heading predicate.**
   `_our_model_has_heading` applies its own `^##\s+(.+)$` regex to the blanked text, not the gate's
   `_RENDER_LEVEL2_RE`. So the test covers `_render_blank_fences` plus a hand-rolled proxy for the
   half of the model that decides what a heading *is*. Demonstrated: `## Actors and roles ##`
   (closing-hash ATX, valid CommonMark) shows up as a differential disagreement, but the real gate
   handles it correctly (FAIL=0 on a document whose mandatory headings all carry closing hashes). A
   spurious signal today; the same gap would hide a real divergence in the heading regex tomorrow.
   Routing the probe through the production predicate would close it.

2. **Setext headings are a genuine (conservative) divergence, undocumented.** A document whose three
   mandatory headings are setext (`Actors and roles\n---`) scores **FAIL=3** — the reference parser
   sees all three `h2`s, we see none. Failure-safe and arguably intended, but it is a real
   divergence from the authority and belongs in `INTENTIONAL_DIVERGENCES` with a reason, not
   undiscovered.

3. **Dead code.** `_RENDER_HTML_BLOCK_OPEN_RE` and `_RENDER_HTML_BLOCK_CLOSE_RE` (lines 6950, 6953)
   survive with zero references, along with a duplicated explanatory comment block. `4255002`'s
   implementation was superseded, not removed.

4. **Two non-discriminating cases.** `fence_backtick_indented` and `indented_code_block` agree with
   both degenerate models; they document intent but pin nothing.

---

## Has the loop ended?

**Not yet — but it is close, and the reason it is close is worth stating as precisely as the reason
it is not.**

`94c7e3d` is the first commit in six rounds that changed the *kind* of evidence available. Rounds
1-5 each patched the shape they were shown; this one installs an authority, and the authority is
real: it runs, it is mutation-bitten three ways, 31 of its 33 cases discriminate, and its allowlist
is defended by two tests that make a stale or permissive row fail loudly. Every finding round 5 named
is genuinely closed, verified by execution, with no regressions across 2540 tests, 105 archived
trees and six SHA-256-pinned inputs. B-6 and B-7 are not coming back.

But the loop did not end, and it failed in a specific and instructive way. The commit correctly
diagnosed that enumerating harder does not terminate, built the right instrument — and then wrote
the instrument's case list **from the same model it was meant to audit**. A differential test whose
inputs are chosen by the author of the model under test inherits that author's blind spots exactly.
Type 7 was not overlooked; it was consciously excluded, for a reason that ninety seconds with the
reference parser would have refuted — the same parser sitting in the same file. The authority was
installed and then not asked the one question that mattered.

That is a smaller failure than round 5's, and it has a structural fix rather than another lap:
generate the case documents rather than hand-listing them (all ~60 type-6 tags, the type-7 shapes,
each fence variant crossed with each context), so that coverage stops being a function of what the
model's author thought to include. That, plus moving every deliberate exclusion out of code comments
and into `INTENTIONAL_DIVERGENCES` where the existing permissive-divergence test can see it, would
make the next construct a test failure instead of a seventh round.

On the honest weighing the charter asks for: this is a quality gate for a self-audit tool, not a
security boundary, and the realistic failure mode is an LLM renderer accidentally producing a flat
document rather than an adversary crafting an evasion. A renderer is not likely to emit `<span>`
around its mandatory sections. If B-8 were the only open item and the contract were otherwise
authority-checked, I would ship it as a follow-up. It is not, for two reasons: the fix is a
one-line addition to a tag list the code already has, and — decisively — the commit's central claim
is that the loop is over. Shipping a permissive, comment-documented divergence that defeats the
entire §5.2 mandatory-part list, under a commit message asserting the model is now checked against
an authority, would make the acceptance record for Feature C say something that is not true. The gap
between B-7 and B-8 is one line of code; the gap between "we hand-model CommonMark" and "we check
against an authority" is the whole claim.

---

## Verdict

**FIX-REQUIRED.** One blocking bypass, executed at HEAD `94c7e3d`:

- **B-8** — CommonMark HTML block **type 7**: FAIL=0 WARN=0 on a document in which a reader sees
  **none** of the three §5.2 mandatory sections, all three reported present. Deliberately excluded
  from the model on a rationale the reference parser refutes; absent from both the case list and
  `INTENTIONAL_DIVERGENCES`, so neither guard can see it.

Everything `round5_closure.md` asked for is genuinely closed — B-6, B-7 for types 1/2/6, and the
C-5 interaction all verified by execution — and the differential test is a real, bitten,
discriminating instrument that will keep them closed. `94c7e3d` is the strongest commit of the six
rounds and the first one that changed the shape of the argument. It is not yet shippable as Phase 2
acceptance for Feature C, because the instrument built to end the loop was aimed by the model it was
built to audit, and the one construct that aiming excluded is a full bypass.
