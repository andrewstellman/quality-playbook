# v1.6.0 Instruction 030 — Worker Self-Council synthesis

**Subject:** the end-of-Phase-1 documentation classification review — show the operator
how each gathered document was classified, and let them confirm or correct it, before
Phase 2 derives anything against it.

**Commits reviewed:** `823feec` (feature) → `f89e8b3` → `1aeee87` → `7fbce6b` → `a5517c9`
(four fix-up rounds), branch `1.6.0`, local only.

**Terminal verdict: unanimous SHIP after five rounds.**

| Round | A — operator-authored only, and bounded | B — show always present, plain-language, correct | C — straight-through flow, round trip, scope |
|---|---|---|---|
| 1 | FIX-REQUIRED (4) | FIX-REQUIRED (P0 + 2×P1) | FIX-REQUIRED (4×P1) |
| 2 | FIX-REQUIRED (1) | **SHIP** | **SHIP** |
| 3 | FIX-REQUIRED (1) | **SHIP** | FIX-REQUIRED (1) |
| 4 | FIX-REQUIRED (1) | **SHIP** | FIX-REQUIRED (1) |
| 5 | **SHIP** | **SHIP** | **SHIP** |

Panelist artifacts (gitignored): `runner/quality-playbook/reviews/030_self_council/`
— 916 / 952 / 705 lines, each preserving all five rounds.

---

## Why this instruction existed

Classification is an LLM judgment, and it **varies**: the same
`virtio-spec-behavioral-contracts.md` classified citable in one live run and all-Tier-4
in another. The operator only learned of a bad classification from the `zero_citable`
tripwire *after* Phase 2 had already derived 18 code-only requirements. The fix is the
mirror image of the Feature D interview, one boundary earlier — **end of Phase 1:
confirm the classification; end of Phase 2: confirm the requirements** — each operator
validation placed immediately before the work that depends on it.

## What the Council changed

Every round found something real. Ordered by what they teach:

### 1. A show that reassures while misdescribing is worse than no show (B, round 1, P0)

`classification_review` split the operator-facing list on the **classified tier**, but
the pipeline decides citability with `_formal_tier`, which honors `cite/` placement
*over* the classifier (an untagged `cite/` file resolves to Tier 1 via
`_parse_tier_marker`) and refuses any record the floor left `promotable: false`. B
reproduced it: a real Tier-1 `FORMAL_DOC` existed for `reference_docs/cite/the-spec.md`
while the operator was shown it under "Background context" **and** told in bold that
none of their documents were authoritative.

Fixed both directions: `classification_review` takes `formal_records` (the
`formal_docs_manifest.json` ground truth) and, without it, applies `_is_authoritative()`,
which mirrors `_formal_tier` exactly. B's closing check mattered — with and without
`formal_records` the output is **byte-identical**, so correctness does not depend on the
agent remembering to pass the argument. The prose is a belt; the predicate is the braces.

### 2. A decision the operator cannot revoke is not a decision (A, rounds 1–3)

Three separate surfaces claimed the operator's consent and none of them could be
withdrawn, because a content-keyed cache hit reused the record:

- `operator_decision` / the instr-030 rules (round 1) — deleting the line from
  `qpb_authoritative.txt` left the promotion standing, and the show echoed *"you told me
  this one is a source I should use"* for consent already withdrawn.
- `RULE_SIDECAR` (round 2) — the show renders it *"you told me to use this one even
  though it looks like source code"*, yet a stale or forged `sidecar-promotion` record
  survived with no `qpb_promote.txt` behind it.
- `advisory_rescued` (round 3) — not a floor rule, so `_OPERATOR_RULES` missed it. A
  forged `advisory_rescued: true` on a document with **no advisory signal at all**
  became byte-citable and made the review say *"you confirmed this is your real
  specification…"* about a document the operator never saw. The writer of that field is
  the derivation agent refining the manifest — precisely the party that must never
  manufacture the operator's consent.

`git log -S` confirmed that the sentences making each claim were introduced by
instruction 030 itself, which is what made these in-scope rather than pre-existing.

### 3. …and an override the operator cannot apply is equally useless (C, round 3)

The opposite half of the same asymmetry, and the one no one had looked for. The cache
bypass existed for `qpb_authoritative.txt` **alone**; `rescued` and `sidecar_set` were
both in scope on that line and neither was consulted. A line added to `qpb_promote.txt`
or `qpb_advisory_rescue.txt` after a first ingest was reused from cache and became a
**permanent silent no-op**. For the instr-025 rescue that is not a corner case: its
documented workflow (`phase1_exploration_guide.md`) tells the operator to copy the sha
and reason out of the manifest *a prior ingest wrote*, so the cache always exists by the
time the file is authored — **as shipped, that rescue could never fire.** Pre-existing
(instr 011/025 era), but the exact defect class this instruction fixes, in the guard the
prior fix-up had just edited.

### 4. The obvious fix for (3) would have destroyed (2) — and then did (A, round 3; A+B+C, round 4)

A caught, before it landed, that bypassing the cache whenever a rescue is live
**destroys a legitimate rescue**: a rescue only *un-floors* and does not force a tier,
so re-deriving a settled, agent-tiered rescued document with no classifier in play drops
it to Tier 4 and its `FORMAL_DOC` disappears. So application became keyed to whether the
override is **new** (`_newly_overridden()`), giving each operator file the clause its
semantics need.

Fix-up 3 then reintroduced the same loss class one clause over, and all three panelists
converged on it independently. `_classify` reaches its sidecar branch only inside
`if impl and not contract:`, so a non-implementation file can **never** settle at
`RULE_SIDECAR` — the clause `in_sidecar and floor_rule != RULE_SIDECAR` was permanently
true, the cache was discarded on every ingest, and the agent's Tier-1 refinement
collapsed to Tier 4 each run. Because `classify_reference_docs` synthesizes a sidecar
entry for **every** `cite/` file, a `cite/`-only corpus began reporting `zero_citable`
and writing *"no authoritative contract was found; all requirements will be
code-derived"* into the Phase-2 Overview — **manufacturing the exact virtio signature
this instruction exists to surface** — while the same run's show correctly listed those
documents as authoritative and Tier-1 `FORMAL_DOC`s existed. B's framing: the show's
correctness was being purchased at the price of the manifest's.

The fix is one operator — key the clause on the floor the sidecar actually lifts
(`== RULE_IMPL`) — verified independently by all three.

### 5. The pause was keyed to a phrase, not to whether anyone was there (C, round 1)

The first draft skipped the confirmation pause only on four literal phrases. That blocks
QPB's own continuous run: `AGENTS.md`'s full-pipeline default says *"do NOT stop at any
phase boundary"*, the `single_pass` prompt uses none of those words, and a headless
`run_playbook` has **no operator to answer at all**. C also punctured the claimed
symmetry with Feature D — that interview is opt-in and never pauses, which is why it
carries no continuous-run language; 030 pauses by default and then carves out phrases.

The rule is now keyed to the only question that matters — *is an operator stepping this
run and waiting right now?* — with an explicit "do not decide this by matching the
operator's exact words" and a fail-safe to `offer=False`. C separately found the show was
missing from the mandatory end-of-phase message template, i.e. the surface a faithful
agent actually prints.

### 6. Filenames are attacker-influenced surface too (A, round 1)

A newline in a document path injected a forged **"Authoritative sources your
requirements can cite"** heading into the operator-facing show. `_safe_path` now
neutralizes C0/C1 controls, the Unicode line/paragraph separators, the bidi overrides,
and the backtick, and bounds length. Separately, a path containing whitespace wrote
successfully to the positional decision file and parsed back as a *different* path — a
silent no-op the operator would read as success; now refused loudly at write time.

### 7. Defensive sweep: the control files were being served as documentation (C, round 1)

`qpb_authoritative.txt` was added to two of four corpus-enumeration sites;
`load_tier4_context()` and `_collect()` were handing it — and, pre-existing,
`qpb_promote.txt` and `qpb_advisory_rescue.txt` — to the agent as Tier-4 "documentation".
A single `CONTROL_FILENAMES` set now applies at all four sites, closing the pre-existing
instances of the same class per the `DEVELOPMENT_PROCESS.md` defensive-sweep charter.

---

## Where the panelists agreed, and where they diverged

**Agreed (highest confidence).** The security invariant holds: no document content, no
classifier, no persona can promote a document — only the human operator, at this step.
A re-ran the full round-1 poisoning battery *from scratch* in round 5 rather than assume
the invariant survived four rewrites of the guard, and it did. The promotion is bounded
exactly where every other operator override is: it lifts the implementation floor (the
same power the path-keyed sidecar already grants, keyed on content instead) and never
the advisory or README/ledger floors, with a refused promotion stated plainly in the
show rather than dropped.

**Diverged — a severity call, resolved by evidence.** B established the `cite/`
cache-bypass mechanism in round 4 and, having verified the *show* stayed correct,
assigned the consequence to A and C as a reproducibility cost. A and C chased it into
`citable_count` and filed FIX-REQUIRED. B's round-5 note is the honest record: *"my
round-4 severity call was too generous… the show's correctness was being purchased at
the price of the manifest's."* This is the case for a panel over a single reviewer — one
reviewer found the mechanism, two others found what it cost.

**Deliberately not changed, with the panel's agreement.** Reasons in the show stay
**generated** rather than passed through from the record's `reason` string: pass-through
would trade a structural no-leak guarantee for cosmetic variety, and those strings
literally carry "Tier 4". B accepted the call and noted a structured plain-language
sub-reason would be the better long-term answer, but no cheap version exists on today's
records.

## Verification

- **Full suite 2847 / 0 failures / 14 skipped, Python 3.14.6.** (Panelist C's checkout
  reports 13 — the delta is one fixture-presence guard; all skips are absent baseline
  archives under `repos/`, `matplotlib`/`numpy` not installed, or canonical `quality/`
  artifacts absent from a checkout. None is code-conditional.)
- **Module tests grew 32 → 46 → 52 → 57 → 60** across the five rounds.
- **27 mutation bites (M1–M27), every one fired and restored.** Every clause of both
  halves of the operator-override guard is pinned individually (A's standing NIT), and
  the round-4 regression is pinned in **both** directions — M25 fails if the clause
  reverts to `!= RULE_SIDECAR`, M26 fails if it is removed entirely. M21 is the most
  instructive: drop the "already reflected" condition and a settled rescue's tier
  collapses 1 → 4, reproducing A's warning exactly.
- Round trip verified end to end by C: promoted document → Tier-1 `external-spec`
  `FORMAL_DOC` → `citation_verifier` OK → both gate checks PASS.
- B re-ran a 26-row show-vs-pipeline alignment matrix over two consecutive `ingest()`
  calls per row: 26/26 aligned on both passes, in both `formal_records` modes.

## Carry-forward for the orchestrator (NOT filed against 030)

**The same defect class, one surface over.** In the `classifier_status: unwired`
degraded state, a `cite/` document sits at Tier 4, so `zero_citable` is true while a
Tier-1 `FORMAL_DOC` exists and the show correctly says authoritative — and
`classification_disclosure` then asserts *"No authoritative contract (Tier 1/2) was found
in the gathered docs: all requirements will be code-derived."* That sentence is false in
that state. It is the pre-existing instr-024-tripwire vs instr-011-`cite/`-branch
divergence, in surfaces instruction 030 never touched, and it is reachable only inside an
already-loudly-disclosed degraded mode whose own text says grounding "may be understated"
and names the remedy. **Suggested fix: give `citable_count` the same predicate the show
now uses (`_is_authoritative`).** Not taken here because changing `citable_count`
semantics ripples into the gate WARN and the mandated Phase-2 Overview disclosure — a
cross-cutting contract change that is the design owner's call, not the worker's.

Standing NITs recorded in the panelist files, all in the safe direction and none
reachable on the documented path: `classifier_status` still reads `unwired` after a
promotion (identical at `1aeee87`, pre-existing); the discard path re-invokes the
classifier on overridden documents; `_safe_path` leaves inert zero-width characters; the
`byte_count` example heuristic is a crude proxy among documentation candidates; and the
pre-existing instr-011 contract sniff and `RULE_LLM` cache channel still launder a
*tier* — but not *consent*, which is the line this instruction draws.
