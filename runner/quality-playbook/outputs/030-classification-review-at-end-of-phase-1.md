# Output for 030-classification-review-at-end-of-phase-1.md
**Status:** completed

## What this instruction was

Classification is an **LLM judgment and it varies** — the same
`virtio-spec-behavioral-contracts.md` classified citable in one run and all-Tier-4 in
another. Today the operator only discovers a bad classification from the zero-citable
tripwire *after* Phase 2 has already derived 18 code-only requirements. This adds the
mirror image of the requirements interview one boundary earlier: at the **end of Phase 1,
before requirements are derived**, show the operator how each gathered document is being
used and let them confirm or correct it. End of Phase 1 → confirm the *classification*;
end of Phase 2 → confirm the *requirements*.

## Terminal verdict: unanimous SHIP (5 rounds)

| Round | A — operator-authored only, bounded | B — show present, plain, correct | C — straight-through, round trip, scope |
|---|---|---|---|
| 1 | FIX-REQUIRED (4) | FIX-REQUIRED (P0 + 2×P1) | FIX-REQUIRED (4×P1) |
| 2 | FIX-REQUIRED (1) | **SHIP** | **SHIP** |
| 3 | FIX-REQUIRED (1) | **SHIP** | FIX-REQUIRED (1) |
| 4 | FIX-REQUIRED (1) | **SHIP** | FIX-REQUIRED (1) |
| 5 | **SHIP** | **SHIP** | **SHIP** |

Every round found something real. Full narrative in the tracked synthesis.

## The end-of-Phase-1 show (plain-language sample)

Rendered from the **real preserved virtio manifest**
(`repos/virtio-1.6.0/quality/classification_manifest.json`, six docs, `zero_citable: true`):

```
### The documents you gave me

I read 6 documents and decided how to use each one. Here's what I settled on, before I
turn any of it into requirements.

**None of your documents are being used as authoritative sources this run — every
requirement will be drawn from the code.** If one of these *is* your specification — the
document that says what this software is supposed to do — tell me which one and I'll use
it that way.

**Background context — I read these, but I won't quote them**
- `reference_docs/index.rst` — I read it as explaining or describing the software rather than stating what it must do.
- `reference_docs/virtio-spec-behavioral-contracts.md` — I read it as explaining or describing the software rather than stating what it must do.
  … (4 more)

**Is that right?** You gathered these, so you're the one who knows. If I've got one
wrong, just say which one and how — the wording I understand looks like *"treat
`reference_docs/linux-coding-style.rst` as my specification"* or *"that one is just
background"*. I'll redo this before deriving anything. Otherwise say **keep going**.
```

Every reason is **generated from the decision**, never passed through from the record's
dev-facing `reason` string (which does carry "Tier 4"). That is what makes the no-jargon
guarantee structural rather than incidental — mutation bite M3 confirms it.

## Acceptance oracle — pass/fail per item

| # | Item | Result |
|---|------|--------|
| 1 | **Always shows**, plain language, no Tier/floored/manifest jargon; prominent zero-authoritative message | **PASS** — B scanned 11+ decision shapes against a superset of the UX plain-language key: zero leaks. Bites M3/M6 |
| 2 | **Operator can promote** → re-run ingest → `FORMAL_DOC` → Phase 2 can cite (build the virtio case) | **PASS** — virtio spec promoted → Tier-1 `external-spec` FORMAL_DOC, sha matches the classification key, `zero_citable` clears. C verified the last link: `citation_verifier` OK + both gate checks PASS |
| 3 | **Straight-through skips the pause, keeps the show** | **PASS** — and reframed after C's finding (below). `offer=False` renders an identical show. Bite M7 |
| 4 | **Security:** document content cannot self-promote; only the operator's explicit promotion works (mutation-bitten) | **PASS** — A re-ran its full round-1 poisoning battery from scratch in round 5. Bites M5/M23/M27 |
| 5 | **Symmetry/consistency** with the interview's opt-out + continuous-run handling | **PASS** — after correcting a symmetry that was claimed but not real (C) |
| 6 | Full suite green | **PASS** — **2847 / 0 failures / 14 skipped, Python 3.14.6** |

## The operator-promotion round trip (virtio case)

New operator-authored, content-keyed file `reference_docs/qpb_authoritative.txt`:

```
authoritative  reference_docs/virtio-spec-behavioral-contracts.md  45decdbe…  operator confirmed: this is the spec
```

Format is `<authoritative|background>  <path>  <document_sha256>  <reason>` — the same
shape as the instruction-025 advisory rescue (all four fields required; an unrecognized
verb is ignored, never guessed at). `record_operator_decision()` is the writer; a re-run
ingest turns the promoted doc into a byte-citable `FORMAL_DOC`. Demotion ("or the
reverse") is unconditional.

**Security invariant confirmed holding.** Only the human operator, at this step, can
promote a document — no document content, classifier, or persona can. A document whose
content embeds a ready-made `qpb_authoritative.txt` line asking to be promoted is not
promoted (bite M5). The promotion lifts the **implementation** floor (the same power the
path-keyed `qpb_promote.txt` already grants, keyed on content instead) but **never** the
advisory floor (that needs the 025 rescue, which acknowledges the specific signal) or the
README/ledger background rule; a refused promotion is stated plainly in the show rather
than dropped.

## What the Council changed (the findings that mattered)

1. **A show that reassures while misdescribing is worse than no show** (B, P0). The show
   split on the *classified tier*; the pipeline decides citability with `_formal_tier`,
   which honors `cite/` placement over the classifier. Reproduced: a real Tier-1
   `FORMAL_DOC` existed while the operator was told **none** of their documents were
   authoritative. Now `classification_review` takes `formal_records` (ground truth) and,
   without it, applies `_is_authoritative()` — byte-identical output either way, so
   correctness does not depend on the agent passing the argument.
2. **A decision the operator cannot revoke is not a decision** (A, rounds 1–3). Three
   surfaces claimed the operator's consent and none could be withdrawn: `operator_decision`,
   `RULE_SIDECAR`, and `advisory_rescued`. `git log -S` confirmed the sentences making
   each claim were introduced by instruction 030 itself.
3. **…and an override the operator cannot apply is equally useless** (C, round 3). The
   cache bypass existed for `qpb_authoritative.txt` alone, so a new `qpb_promote.txt` or
   `qpb_advisory_rescue.txt` line was a permanent silent no-op — and because the 025
   workflow requires copying the sha out of a manifest a prior ingest wrote, **that
   rescue could never fire as shipped**.
4. **The obvious fix for (3) would have destroyed (2)** — A caught it before it landed,
   and fix-up 3 then reintroduced the loss class one clause over, manufacturing the very
   `zero_citable` virtio signature this instruction exists to surface. All three
   panelists converged on the one-operator fix (`== RULE_IMPL`).
5. **The pause was keyed to a phrase, not to whether anyone was there** (C). Four literal
   phrases blocked QPB's own full-pipeline default, `single_pass`, and every headless
   run. Now keyed to *"is an operator stepping this run and waiting right now?"*, with
   an explicit "do not decide this by matching the operator's exact words" and a fail-safe
   to `offer=False`. C also found the show missing from the mandatory end-of-phase
   template — the surface a faithful agent actually prints.
6. **Filenames are attacker-influenced surface too** (A). A newline in a path injected a
   forged "Authoritative sources" heading into the show.
7. **Defensive sweep** (C): the operator control files were being served to the agent as
   Tier-4 documentation at two of four enumeration sites — including, pre-existing,
   `qpb_promote.txt` and `qpb_advisory_rescue.txt`. One `CONTROL_FILENAMES` set now
   applies at all four.

## Straight-through behavior (as shipped)

The show prints in **every** mode; only the pause varies, and the pause is the
**exception** because the Mode A default is the full six-phase pipeline that does not
stop at phase boundaries. `offer=True` only when an operator is stepping the run and
waiting; `offer=False` for the full-pipeline default, an explicit run-everything, the
`single_pass` prompt, and any runner-driven or headless run where **no operator is
present to answer**. If the agent cannot tell, `offer=False` — a blocked unattended run
is a worse failure than a missed pause, and the disclosure has been made either way.

## §8a design note

`docs/design/QPB_v1.6.0_Design.md` §8a gains an **"End-of-Phase-1 classification review"**
subsection: the always-rendered plain-language show; confirm-or-correct with the pause
keyed to whether an operator is waiting (naming phrase-matching as the first draft's
mistake); the operator-authored content-keyed correction that re-derives citability
through a re-run ingest; and the operator-only bound. The authoritative/background split
is documented as the **pipeline's own** citability rule, because splitting on the
classified tier misdescribes both directions.

## Files changed

| File | Change |
|------|--------|
| `plugins/.../scripts/doc_classification.py` | `RULE_OPERATOR_AUTHORITATIVE`/`_BACKGROUND`; `Decision.operator_decision`; `_OPERATOR_RULES`; `_newly_overridden()` + the withdrawal disjunction (the operator-override contract, both directions); `_is_authoritative()`; `_safe_path()`; `classification_review()`; playback statuses |
| `plugins/.../scripts/reference_docs_ingest.py` | `OPERATOR_DECISION_NAME` + `CONTROL_FILENAMES` (4 sites); `_load_operator_decisions()`; `record_operator_decision()` |
| `phase_prompts/phase1.md` | mandatory end-of-Phase-1 review block |
| `references/what_just_happened.md` | State P1 — the show + the pause rule |
| `references/phase1_exploration_guide.md` | the 4-step protocol + the show in the mandatory end-of-phase template |
| `SKILL.md`, `schemas.md` §9.6.1, `docs/design/QPB_v1.6.0_Design.md` §8a | disclosure + schema + design |
| `bin/tests/test_classification_review_v160.py` | **new**, 60 tests |
| `bin/tests/test_phase_prompts_externalized.py` | phase1 `EXPECTED_HASHES` rebaselined (twice — the sanctioned change-acknowledgement signal) |
| `docs/process/QPB_v1.6.0_Instruction_030_Self_Council/synthesis.md` | tracked synthesis |

## Commits made (branch `1.6.0`, local only — never pushed)

- `823feec` — the feature (show + operator-authored correction + prose + design).
- `f89e8b3` — fix-up 1: round-1 findings (3× FIX-REQUIRED closed).
- `1aeee87` — fix-up 2: round-2 findings.
- `7fbce6b` — fix-up 3: round-3 findings — the operator-override contract, both directions.
- `a5517c9` — fix-up 4: the sidecar application clause must key on the floor it lifts.
- `53848ac` — tracked self-Council synthesis.
- `<output commit>` — runner: output for instruction 030.

The orchestrator's uncommitted `docs/design/QPB_v1.6.0_Design.md` OD-11 edit was left
alone throughout: both commits touching that file staged **only** my own hunk
(`git apply --cached` on a filtered patch), verified each time.

## Verification

- **Full suite 2847 / 0 failures / 14 skipped, Python 3.14.6.** Panelist C's checkout
  reports 13 — the delta is one fixture-presence guard. All skips are absent baseline
  archives under `repos/`, `matplotlib`/`numpy` not installed, or canonical `quality/`
  artifacts absent from a checkout; none is code-conditional, and the new module has zero.
- **27 mutation bites (M1–M27), every one fired and restored.** Every clause of both
  halves of the operator-override guard is pinned individually; the round-4 regression is
  pinned in **both** directions (M25 on revert, M26 on removal). M21 reproduces A's
  warning exactly — drop the "already reflected" condition and a settled rescue collapses
  1 → 4. Restores used a `shutil.copy2` pristine snapshot with a scoped `__pycache__`
  purge; never `git checkout --`/`git restore`/shell `cp`.

## Notable observations

- **`SKILL.md` and `references/` are symlinks** from the plugin path to the repo root;
  `git status` reports the real repo-root paths.
- **The `bin/` bundle is gitignored** (staged at build time), so no bundle sync was
  needed; `doc_classification.py` is already in the install closure, so the prose's
  `from bin.doc_classification import classification_review` resolves adopter-side.
- **A drive-by doc-truth fix:** `schemas.md` §9.6.1 documented neither the instruction
  023/024/025 optional fields nor the manifest-level status fields. I added a row for my
  own `operator_decision` field plus the new `floor_rule` values, and a one-line pointer
  noting the earlier fields exist and live in `doc_classification.py` — rather than
  either leaving the section half-accurate or redesigning someone else's section.
- **Panelist B's self-correction is worth keeping.** B established the `cite/`
  cache-bypass mechanism in round 4, verified the show stayed correct, and assigned the
  consequence to A and C as a reproducibility cost. A and C chased it into `citable_count`
  and filed FIX-REQUIRED. B's round-5 note: *"my round-4 severity call was too generous…
  the show's correctness was being purchased at the price of the manifest's."* This is the
  case for a panel over a single reviewer — one found the mechanism, two found what it cost.

## Carry-forward for the orchestrator — a scope call I did NOT take

**The same defect class, one surface over.** In the `classifier_status: unwired` degraded
state a `cite/` document sits at Tier 4, so `zero_citable` is true while a Tier-1
`FORMAL_DOC` exists and the show correctly says authoritative — and
`classification_disclosure` then asserts *"No authoritative contract (Tier 1/2) was found
in the gathered docs: all requirements will be code-derived."* **That sentence is false in
that state.** It is the pre-existing instruction-024-tripwire vs instruction-011-`cite/`-
branch divergence, in surfaces instruction 030 never touched, reachable only inside an
already-loudly-disclosed degraded mode.

Suggested fix: give `citable_count` the same predicate the show now uses
(`_is_authoritative`). **Not taken here** because changing `citable_count` semantics
ripples into the quality-gate WARN and the mandated Phase-2 Overview disclosure — a
cross-cutting contract change that is the design owner's call, not the worker's. Flagging
rather than deciding.

## Council artifacts

- Gitignored: `runner/quality-playbook/reviews/030_self_council/` — three panelist files
  (916 / 952 / 705 lines), each preserving all five rounds with its own verdict trail.
- Tracked: `docs/process/QPB_v1.6.0_Instruction_030_Self_Council/synthesis.md`.

## Next action expected from orchestrator

None required for 030. The remaining v1.6.0 release items are unchanged from the 029
output, plus the `citable_count` carry-forward above.
