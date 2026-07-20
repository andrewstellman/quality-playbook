# VERDICT: SHIP

Panelist: item-3 dedicated charter — the WARN-never-FAIL property of the glossary slot.
Commit under review: **0e75fd2** (`v1.6.0 [instr 002 item 3]: glossary slot in the architecture — WARN only`).
Baseline for all comparisons: **aa4b4f6** (pre-instruction-002), run from a throwaway git worktree.
Environment: Python 3.14.6, macOS, branch `1.6.0`.

Every finding below was produced by **executing** the gate, not by reading it. All commit-message
claims were treated as unverified until reproduced.

---

## 1. The acceptance bar — MET

Ran `check_render_contract` against all three fixtures at HEAD and at the `aa4b4f6` baseline:

| fixture | baseline aa4b4f6 | HEAD 0e75fd2 |
|---|---|---|
| chi     | FAIL=0 WARN=0 | **FAIL=0 WARN=1** |
| express | FAIL=0 WARN=0 | **FAIL=0 WARN=1** |
| virtio  | FAIL=0 WARN=0 | **FAIL=0 WARN=1** |

Zero new FAILs. Exactly one WARN each, and in all three it is the glossary advisory
(`has no glossary/definitions section — … advisory, never a FAIL`). This is precisely the outcome
the instruction names as "expected and correct".

## 2. Can it escalate to FAIL? — NO, on 15 adversarial routes

Built a mutation harness over the chi fixture in a temp tree (the committed fixture was never
touched) and drove every route in the charter plus several more. **FAIL=0 in all 15 cases:**

| # | route | FAIL | glossary signal |
|---|---|---|---|
| 0 | no glossary (baseline) | 0 | WARN absent |
| 1 | good glossary | 0 | PASS |
| 2 | heading only, empty body | 0 | WARN near-empty |
| 3 | whitespace-only body | 0 | WARN near-empty |
| 4 | single-word body (`TBD`) | 0 | WARN near-empty |
| 5 | `## Definitions` | 0 | PASS |
| 6 | `## Terms` | 0 | PASS |
| 7 | `## Glossary and definitions` | 0 | PASS |
| 8 | `## GLOSSARY` (upper) | 0 | PASS |
| 9 | `## Glossary ##` (closed ATX) | 0 | PASS |
| 10 | glossary inside a code fence | 0 | WARN absent (fence-blanking correct) |
| 11 | glossary inside an HTML block | 0 | WARN absent |
| 12 | glossary containing REQ headings | 0 | PASS |
| 13 | glossary last in document order | 0 | PASS |
| 14 | glossary first, before Overview | 0 | PASS |

Cases 10/11 correctly report *absent* — a glossary that exists only inside a fence or HTML block is
not a glossary, and the fence-blanking path handles it. Case 12 (a glossary holding a real
colon-form REQ heading) emits `PASS: glossary/definitions section present` and produces **no
glossary FAIL**; the single FAIL observed there is the pre-existing REQ-sequence check firing on the
artificial out-of-order `REQ-901`, not the glossary check.

**Conclusion: there is no route by which the glossary check itself can FAIL.** The three-branch
structure (`warn` / `warn` / `pass_`) has no `fail(` in it, and behavior confirms the source reading.

## 3. Is the WARN-never-FAIL test real? — YES (mutation-bitten)

Took a pristine snapshot of the working `quality_gate.py` (`shutil.copy2`, md5
`c4e1fdce…`), purged `__pycache__`, confirmed 94 tests green, then escalated the glossary
absent-branch `warn(` → `fail(`.

**Result: exactly 8 tests went RED** — matching the commit message's claim precisely:

- `GlossarySlotTests.test_absent_glossary_warns_and_does_not_fail`
- `GlossarySlotTests.test_the_check_has_no_fail_path_in_source`
- `RegenerationOracleTests.test_regenerated_documents_pass_the_render_contract` × chi/express/virtio
- `BeforeAfterDeltaTests.test_every_before_document_fails_more_than_its_after` × chi/express/virtio

Restored from the pristine snapshot, purged `__pycache__`, md5 matched, `git status` clean, 94 green.

**The structural source-scan test is meaningful, not cosmetic.** It went red under the mutation, and
it is genuinely complementary to the behavioral tests: it asserts on the check's *source block*, so a
`fail()` added there is caught even if no fixture happens to exercise that branch. Two further points
in its favor: it strips comment lines before asserting (otherwise the block's own prose "no fail()
path" would match the pattern it forbids — a real trap, handled), and its anchors are located with
`str.index`, which raises `ValueError` if the anchor comment is renamed. That makes it **fail-safe,
not fail-open** — a refactor that moves the block errors the test rather than silently passing.

## 4. The allowlist — HONEST (verified by three separate mutations)

`EXPECTED_FIXTURE_WARNS` contains exactly one entry, `"glossary/definitions section"`. Probed it:

- **A new unexpected WARN still fails.** Injected a spurious `warn()` into `check_render_contract`
  → `test_regenerated_documents_emit_only_expected_advisory_warnings` FAILED on all three targets.
  The allowlist is not a blanket suppression.
- **The staleness guard works.** Added a bogus never-firing row → `test_the_expected_warn_allowlist_is_not_stale`
  FAILED naming that row. An entry that stops firing must be deleted, not left as standing permission.
- **F-1 is actively asserted, not allowlisted.** Suppressed the F-1 PASS line in the gate →
  `test_f1_coverage_and_gaps_still_passes_on_every_fixture` FAILED on all three targets. F-1 is not
  in the allowlist and is independently pinned.

The allowlist is also **tight in a way worth noting**: the key matches the *absent* WARN but **not**
the near-empty WARN text. If a fixture ever gained a stub glossary, that near-empty WARN would
surface as unexpected and fail the test rather than being silently absorbed. That is the right shape.

The replacement of the old zero-WARN assertion is a genuine improvement over both the original and
over a naive count check — the test asserts the *set* of unexpected WARNs is empty and separately
reconciles the WARN counter against emitted lines, so a new WARN cannot slip in as another goes away.

## 5. Fixture edits — NONE

`git diff aa4b4f6..1d3cbc8 -- 'bin/tests/fixtures/render_contract_v160/**/REQUIREMENTS.md'` is empty.
None of the five instruction-002 commits (f1b228d, f8b73dc, 0e75fd2, a59e5c6, 1d3cbc8) touches any
path under `bin/tests/fixtures/render_contract_v160/`. The standing constraint was respected: the
WARN was accepted as the correct outcome rather than engineered away by hand-polishing the oracle.

## 6. Regressions — NONE

- **Full suite: 2551 tests, 0 failures, 13 skipped.** Matches the claimed count exactly.
- **Count delta verified independently.** Parent commit f8b73dc in a clean worktree: 2543 tests.
  2543 → 2551 = +8, matching the commit message. (The parent worktree also showed 6 errors +
  1 failure in `test_setup_repos`; these are worktree artifacts — that module needs the gitignored
  `repos/` tree, which does not exist in a worktree. Unrelated to item 3; HEAD is fully green in the
  real tree.)
- **Archived-tree sweep: 95 trees carrying a `REQUIREMENTS.md`, zero FAIL-count flips** between
  baseline and HEAD. The glossary WARN flipped no tree's exit code. Three trees (CASE-002-jspdf,
  CASE-006-budibase, wn-go-02-goshs) carry WARN=1 at *both* baseline and HEAD — pre-existing and
  unchanged.

---

## The structural-regex question (charter's highest-value item) — reported in full

Item 3 also added `glossary|definitions|terms` to `_RENDER_STRUCTURAL_HEADING_RE`. I probed this
hard, because it is the one change that touches checks other than the glossary advisory.

**Is it load-bearing? Yes — but not for the reason the commit message gives.**

`_render_classify_sections` skips any section without REQ headings *before* it consults the
structural regex (`if not has_reqs: continue`). So a normal, REQ-free glossary — the shape the
generation guide prescribes — was never at risk of being classified functional. I confirmed this by
reverting *only* the regex line and re-running: **all 15 adversarial cases still give FAIL=0**, and
all three fixtures still give FAIL=0 WARN=1. For the ordinary case the regex changes nothing.

Where it *does* matter is a glossary that **contains REQ headings**. With the regex reverted, that
document goes FAIL=1 → **FAIL=3**, the two extra being exactly the intro-prose and singleton FAILs
firing on the Glossary section. So the back-door FAIL the commit describes is real — it just arises
when the glossary *has* REQs, not when it has none. The commit message's phrasing ("it would count
as a functional section **with no REQs** and no intro prose") inverts the mechanism. The change is
justified; the sentence explaining it is wrong. **Non-material to the verdict** — the code is right
and the property holds — but worth correcting so a future reader does not reason from it.

**Side effect: a narrow bypass and a narrow escalation.** Widening the structural allowlist applies to
*all* sections, not just the glossary. Measured, baseline vs HEAD:

| shape | baseline | HEAD | direction |
|---|---|---|---|
| functional section renamed `## Terms`, intro prose stripped | FAIL=1 | **FAIL=0** | defect → pass (**bypass**) |
| section named `## Terms` holding one unjustified REQ (singleton) | FAIL=1 | **FAIL=0** | defect → pass (**bypass**) |
| *every* functional section named `## Terms` | FAIL=0 | **FAIL=1** | pass → FAIL (**escalation**) |
| control: same shapes under original section names | FAIL=1 | FAIL=1 | unchanged |
| `## Payment terms`, `## Terms of service` | FAIL=0 | FAIL=0 | unaffected (regex is anchored) |

Assessment — why this does not block:

1. It is **not** the glossary check failing. The escalation comes from the pre-existing
   "no functional section" FAIL, and on that pathological document (every section named `Terms`)
   the FAIL is arguably correct: the document really has opted out of section structure.
2. The blast radius is **bounded by anchoring**. `_RENDER_STRUCTURAL_HEADING_RE` is `\Z`-anchored, so
   only headings named *exactly* `Glossary` / `Definitions` / `Terms` / `Glossary and definitions`
   are affected. `Payment terms` and `Terms of service` are untouched — I verified both.
3. This bypass **class pre-exists by design** for `Overview`, `Use cases`, `Requirements`,
   `Cross-cutting concerns`, `Traceability appendix` and the NFR names; the classifier's docstring
   states the trade-off deliberately, and total bypass is caught (an empty `functional` list is its
   own FAIL). The change extends an already-accepted trade-off to three more names.
4. **Zero real-world impact measured**: no fixture and none of 95 archived trees changes verdict.

It is a genuine, if narrow, widening of the gate's blind spot, and it should be recorded rather than
discovered later — hence the follow-up below.

---

## Verdict

**SHIP.**

The load-bearing property holds under execution, not merely under inspection. The glossary check
cannot FAIL by any of the 15 routes I could construct; the acceptance bar (FAIL=0, one glossary WARN,
zero new FAILs vs baseline) is met on all three fixtures; the fixtures were not edited; the suite is
green at the claimed 2551 with the claimed +8 delta; 95 archived trees show zero exit-code flips; and
the tests that assert the property are real — the mutation bite reddened exactly the 8 tests claimed,
and the allowlist withstood three independent probes designed to expose it as papering over a defect.

Every quantitative claim in the commit message that I checked reproduced exactly (8 tests red,
2543 → 2551, clean fixture tree, FAIL=0 WARN=1 per fixture). The single inaccuracy is a rationale
sentence misdescribing *why* the structural registration is needed, not a false claim about outcomes.

### Follow-ups (non-blocking)

1. **Record the `Terms` / `Definitions` bypass.** A functional section named exactly `Terms` or
   `Definitions` now escapes the intro-prose and singleton checks. Consider dropping bare `terms`
   from `_RENDER_STRUCTURAL_HEADING_RE` (it is the one ambiguous token — `glossary` and `definitions`
   are unambiguous section names, `terms` is a plausible functional-section name) while keeping it in
   the glossary *detection* pattern, which is a separate regex and would be unaffected.
2. **Correct the commit/design rationale.** "would count as a functional section with no REQs" is
   backwards — no-REQ sections are skipped before the structural test. The registration matters for
   REQ-*bearing* glossaries. Worth fixing wherever this reasoning is carried forward into Design §5.2.
3. **Design §5.2 / Implementation Plan still say "eight-part".** The commit flags this as
   orchestrator-owned and deliberately untouched, and the guide states the relationship explicitly.
   Tracking only, so the ninth advisory part is absorbed rather than forgotten.
4. Consider a test pinning that `## Payment terms` is *not* treated as structural, to lock in the
   anchoring that currently bounds the blast radius.

### Verification hygiene

All mutations were applied to the working tree, reverted from a pre-taken pristine `shutil.copy2`
snapshot (never `git checkout --`), with `__pycache__` purged scoped to `bin/` and `plugins/` before
each re-verify. Final state confirmed: gate md5 `c4e1fdcea64bb96e958c74117a174bc8` (identical to
snapshot), test module md5 unchanged, `git status` showing only the operator's pre-existing
uncommitted `docs/design/` edits and the untracked instruction file — exactly as at session start.
Both temporary worktrees were removed.
