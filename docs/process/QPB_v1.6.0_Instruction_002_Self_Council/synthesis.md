# Instruction 002 — worker self-Council synthesis

*v1.6.0 render-contract hardening (pre-Feature-D). Protocol: instruction 002
§ Council — a focused single-panel review, **plus a dedicated panelist charter
for item 3** verifying the WARN-never-FAIL property.*

## Panel

| Panelist | Charter | R1 verdict |
|---|---|---|
| item-3 | glossary slot: WARN-never-FAIL, incl. a test proving it cannot escalate | **SHIP** |
| focused | items 1, 2, 4, 5 | **FIX-REQUIRED** (2 blocking) |

Round 2 = closure verification of `0f7cc0a`.

## Commits

| SHA | Item |
|---|---|
| `f1b228d` | 2 — delete the dead renderer carrying the C-7 defect |
| `f8b73dc` | 1 — no disjunctive acceptance clauses |
| `0e75fd2` | 3 — glossary slot, WARN only |
| `a59e5c6` | 4 — regenerate the stale before-state figures |
| `1d3cbc8` | 5 — record the regeneration expectations |
| `64b48c8` | 5 — ground the expected forms in verified source (self-caught) |
| `0f7cc0a` | close the self-Council findings |

---

## Findings

### B-1 (blocking, closed) — the rule missed a third prompt

Item 1's acceptance was "both producers addressed", and both were. But the
skill-derivation producer has **two** Pass A prompts, and
`pass_a_uc_section.md` authors both `acceptance_criteria` (REQs) and
`acceptance` (UCs). It did not get the rule.

The gap is intra-producer, which is why it passed the literal criterion — and
it is not hypothetical. **express UC-06.b, one of the five live instances the
instruction names, is a use-case acceptance clause.** A rule landed only on the
REQ prompt would not have prevented the defect it was written for.

This is the same shape as instruction 001's C-2 finding: a rule stated in one
place and contradicted or absent in a sibling surface that an agent is equally
likely to be reading.

### B-2 (blocking, closed) — the deleting commit created its own drift

`curate_requirements.py` still described itself as a "curated REQUIREMENTS.md
generator" and listed "5. Render to REQUIREMENTS.md" — the renderer `f1b228d`
had just deleted, in the module deliberately preserved so a future B-4 reader
could use it. A commit whose subject is removing dead code left a dead
description behind.

### Non-blocking, also closed

- **Bare `terms` in the structural-heading regex** (item-3 panelist). A real
  functional section named "Terms" escaped the intro-prose and singleton
  checks. Dropped from the structural list; glossary detection keeps its own
  broader pattern, so a `## Terms` glossary is still found.
- **MP-1 attribution** — said "round 3", landed at `a95dcb5` (round 2).
- **The item-5 provenance line** named only the REQ prompt, which B-1 made
  untrue for row 2.

### Self-caught before the panel reported

The item-5 expectations doc asserted two code facts it had never checked, and
both were wrong: that express's JSONP guard *rejects* member-access chains (it
**sanitizes**, `response.js:286`, and its permitted set *includes* `.`, `[`,
`]`), and that virtio *clamps* oversize queues (it **rejects** with `-E2BIG`,
`virtio_ring.c:3342`; the halving loop I mistook for clamping answers a
different question — allocation pressure, not the device maximum).

This is the fabrication class instruction 001's Council caught as a P0 in
virtio's coverage statement: plausible technical prose about a codebase,
asserted rather than checked. Corrected against source in `64b48c8`, with a
provenance section that now distinguishes Council-supplied from source-verified
from open-question, and records the error rather than quietly fixing it — a
document that tells a future regeneration what to expect is worthless if its
own claims were invented.

---

## What the panel confirmed

**Item 3's property holds under adversarial execution.** The dedicated panelist
built 15 documents attempting to make the glossary check FAIL — empty and
whitespace bodies, alternate headings, fenced and HTML-block glossaries,
REQ-bearing glossaries, glossary-only documents, repositioned glossaries — and
got FAIL=0 on all 15. The mutation bite reproduced exactly: escalating `warn(`
to `fail(` turns 8 tests red, including all three fixtures, which is precisely
the signal the instruction says means "implemented wrong".

**Item 4 fully reproduces, and the instruction was wrong.** The focused panel
reconstructed the delta commit-by-commit through worktrees: `edc5cec` 11/9/6 →
`f9984ae` 11/10/7 (stamp) → `a95dcb5` 13/12/9 (MP-1). chi's delta is exactly
+2 MP-1; the intro-prose FAIL the instruction attributed it to was already
inside the original 11.

**The standing constraint held.** No fixture `REQUIREMENTS.md` was touched by
any instruction-002 commit, verified by diff across all seven.

**No mechanical check was added for item 1.** `quality_gate.py` is touched only
by item 3's commit — the verifiable form of that claim.

---

## Process observation

Both panelists independently reported a **shared-tree race**: a transient suite
failure caused by one agent running source-mutation bites while the other ran
the suite. Neither was a real defect, and both caught it by re-running with a
checksum. Worth recording as a runner-level hazard: concurrent reviewers on one
working tree will keep producing phantom failures unless mutation bites are
serialized or run in worktrees.

## Artifacts

| File | Contents |
|---|---|
| `panelist_item3_warn_never_fail.md` | R1, item 3 — WARN-never-FAIL charter |
| `panelist_focused_items_1_2_4_5.md` | R1, focused panel |
| `round2_closure.md` | closure verification of `0f7cc0a` |
| `synthesis.md` | this file |

**Gitignore status:** this directory matches `.gitignore:82` (bare `reviews/`,
matching at any depth) and is **untracked**. A tracked copy is committed at
`docs/process/QPB_v1.6.0_Instruction_002_Self_Council/`, per the instruction's
explicit requirement and the precedent set in 001.
