# v1.6.0 Instruction 031 — Worker Self-Council synthesis

**Subject:** the three defects a fresh sonnet run of virtio phases 1–3 surfaced — the
end-of-Phase-1 worked example suggesting the wrong file, the persona validation pass
changing the operator's requirements without saying so, and `setup_repos.sh` producing a
benchmark install that blocks Phase 0.

**Commits reviewed:** `159c251` (the three fixes) → `b95c0f5` → `7ef67d0` → `0175947` →
`82de5a6` (four fix-up rounds), branch `1.6.0`, local only. One post-close commit landed
the last panelist's own prescribed NIT fix (see "After the close").

**Terminal verdict: unanimous SHIP after five rounds.**

| Round | A — the worked example never names a non-spec | B — the disclosure is present iff it ran, and true | C — the install is completed without weakening the validator |
|---|---|---|---|
| 1 | FIX-REQUIRED (2×P1) | FIX-REQUIRED (2×P0, 4×P1) | FIX-REQUIRED (3×P1) |
| 2 | FIX-REQUIRED (2×P1) | FIX-REQUIRED (3×P1) | FIX-REQUIRED (1×P1) |
| 3 | FIX-REQUIRED (1×P1) | **SHIP** | **SHIP** |
| 4 | **SHIP** | **SHIP** | **SHIP** |
| 5 (terminal, on head) | **SHIP** | **SHIP** | **SHIP** |

Panelist artifacts (gitignored): `runner/quality-playbook/reviews/031_self_council/` —
three files, every round preserved verbatim with its own verdict trail.

---

## Why a Council was worth it here

The instruction's acceptance oracle was satisfied by the first commit. Every defect below
was found *after* that point, by reviewers who ran the code instead of reading it.

## What the Council changed

### 1. A transparency feature whose headline promise could not be kept (B, round 1, P0)

The new disclosure told the operator: *"say **undo the expert review changes** and I will
put your requirements back exactly as they were."* `revert(which="all")` restores from
`PersonaPass._pre_requirements` — an **in-memory field**. The agent runs the pass in a
scripted Python invocation that exits before the operator ever reads the message, so by
their next turn the snapshot is gone; B rebuilt a pass from the on-disk artifacts and got
`TypeError: 'NoneType' object is not iterable`. A dropped requirement's body and a
corrected requirement's original wording existed **nowhere** on disk. `grep -rn "undo the
expert review"` over the whole repo returned exactly one hit: the string inside the
renderer.

The fix persists the pre-pass manifest (`quality/requirements_manifest.pre_review.json`)
and adds `revert_from_disk()`, which restores the **whole prior manifest** rather than
replaying moves — the only shape that can recover a dropped body — and is documented as a
procedure at State P2, in `phase2.md` and as § E.9 step 7.

**The lesson:** a disclosure that promises a capability is a claim about the code, and it
is subject to the same "verify before you claim" rule as a test result.

### 2. …and an invitation that would have destroyed what it offered to protect (B, round 1, P0)

The same paragraph offered "or just the added ones you name". A `correct` move retags the
operator's **own** record `agent-validation`, so naming that id in the selective revert
deletes their requirement rather than restoring its wording — and the renumber then moves
the persona's addition onto the id they named. The invitation is gone; the whole-pass
restore is the only thing offered; the underlying limitation is documented on `revert()`
and carried forward.

### 3. Completing an install introduced two new failures (C, round 1, P1×2)

Staging the missing scaffolding was the easy half. C chased the consequences:

* The `cat template >> .gitignore` append destroyed the **last existing rule** of any
  target whose `.gitignore` lacked a trailing newline — six repos under `repos/clean/`,
  reproduced on `agentscope` as `uv.lock# Quality Playbook — …`, silently un-ignoring
  `uv.lock` in the repo under audit.
* The `quality/RUN_INDEX.md` sentinel (required, because the appended template's
  `!quality/RUN_INDEX.md` negation makes `run_playbook`'s pre-flight demand it) made
  `archive_previous_run` **fabricate a `partial` prior run** on every freshly set-up
  target: a phantom `previous_runs/<ts>/` cell that `metrics_reconstruction` and
  `skill_derivation` read as a real observation, a bogus row in the append-only run index,
  and a subsequent `stale_quality_dir` Phase 0 block. Fixed by the one-line `non_live`
  addition, mirroring the existing `_LANGUAGE_SENTINEL` precedent — which also closed a
  second latent double-archive bug C found while verifying it.

### 4. The install un-installed itself on three benchmark targets (C, round 1, P1)

`casbin`, `keycloak` and `nats-server` under `repos/clean/` are real git checkouts, so the
appended `.gitignore` is a **tracked** modification — and `benchmark_lib.cleanup_repo()`,
called three times from `run_playbook.py`, reverted it. C observed `Tidied 1 tracked
file(s) in casbin: .gitignore`, after which Phase 0 reported the very finding this
instruction set out to eliminate. `.gitignore` now joins `AGENTS.md` in `PROTECTED_EXACT`.

### 5. Fixing one filename is not fixing the class (A, rounds 1–3)

Three rounds on the same surface, each one a level deeper:

* **Round 1:** the example named the largest promotable background document — on virtio, a
  45 KB Linux style guide over the 7.8 KB spec.
* **Round 2:** the name-signal fix inverted the instruction-030 doc-over-source rule (a
  spec-*named* `.c` beat an ordinary document, so the show said "treat
  `engine-protocol.c` as my specification" one line after saying that file "shows what the
  software already does"), and `linux-coding-**standards**.rst` — one rename from the file
  that caused the instruction — still won.
* **Round 3:** A caught its own round-2 certification as wrong. It had verified three of
  the four names it cleared; `documentation-standards.md`, `naming-standards.md` and
  `engineering-standards.md` were still named over the real spec. The veto is now organized
  by the rule that decides membership — **genre** words (what kind of document this is) and
  **practice-domain** words ("how the team works", not "what the software must do") — so
  the class is closed rather than the filenames.

**The lesson:** "I verified this" is itself a claim to verify. A round-2 pass that reasoned
about a token list instead of rendering it produced a confident, wrong all-clear.

### 6. The ordering nobody could satisfy (B, round 2, P1)

The disclosure required the end-of-phase block to be emitted *after* the pass. But the
requirements-interview offer lives *inside* that block, and `phase2.md` ordered the pass
*after* the offer. offer ⊂ block; block after pass; pass after offer — no ordering
satisfies all three, and no surface acknowledged it. All four surfaces now state one
order: **finalize → pass → re-render → State P2 block carrying the offer and the
disclosure together**, with the rationale (the operator walks the spec as it now stands).
B also found a *second* mandatory operator-facing end-of-Phase-2 message, in
`phase2_generation_guide.md`, still firing before the pass and saying nothing about it.

### 7. Silence beats a positive false claim (B, rounds 2–5)

A summary whose `applied_count` disagreed with its `applied` list rendered *"They read
through your requirements and did not change anything"* — worse than the silence the
feature replaced. `"there is nothing to undo"` was also the answer for a tree whose pass
ran *before* the snapshot existed, where the requirements really were changed. The undo
deleted the very list the same paragraph called *"listed for you to judge"*. A late undo
would have orphaned BUG→REQ links. A `bugs_manifest.json` keyed `bugs` instead of
`records` — the documented 2026-05-16 express defect — read as "no bugs". Each is now a
distinct, pinned behavior.

### 8. Tests that pin nothing (all three panelists, every round)

* A: the round-2 backslash-path test was a tautology — its fixture was rejected by the
  genre veto before the split mattered, so reverting the fix killed zero tests.
* A: the `RULE_OPERATOR_AUTHORITATIVE`/`RULE_CONTRACT` exclusion added at A's own request
  was pinned by **zero** of 225 tests.
* B: mutating the BUG guard to block *every* undo — including the boundary-time one the
  disclosure offers — was caught by no test, which would have let the round-1 P0 fix
  regress invisibly.
* C: the idempotence test was a tautology (`--replace` `rm -rf`s the destination, so the
  guard was never reached; C mutation-proved it passes with the guard deleted), and the
  replacement tests **failed rather than skipped** on a fresh clone because
  `repos/setup_repos.sh` is force-tracked while the `_benchmark_lib.sh` it sources is not.

## Evidence the panel produced beyond the fixes

* A rendered the worked example against four real benchmark corpora beyond virtio:
  `express-1.6.0` (19 docs) → `01_API_Reference.md`; `chi-1.6.0` (18) →
  `13_api_reference.md`; `bus-tracker-smoke` (10) → `02_siri_api_endpoint.md`; and a virtio
  variant holding only the style guide and the history doc → `<the-file>`. Four right
  answers and one honest withholding.
* C re-verified the fresh-clone fix more strictly than the worker claimed it: a pure
  `git archive` extraction with nothing layered in (51 run / 4 skipped / 0 failures), then
  added back **only** `_benchmark_lib.sh` to prove it is the sole gap.
* B verified the undo end-to-end in a fresh process against a pass containing a grounded
  add, a grounded correct, an ungated drop and an ungrounded add.

## Self-corrections worth keeping

Both A and B corrected themselves on the record rather than silently:

* A, round 3: *"In round 2 I certified `documentation-standards.md` as falling to the
  placeholder. I never actually re-ran that filename."*
* A, round 5: a wrong extraction expression in its own probe briefly printed a regression
  that did not exist — recorded rather than quietly fixed, *"since silent self-correction
  is the thing I have been marking against this commit."*
* B, round 4: discarded a mutation that turned out to be a semantic no-op rather than
  counting it as a coverage gap.
* C, round 4: flagged that its own first check of the phantom-archive fix was contaminated
  (it validated the target first, leaving the validator's `.qpb_validation_*` witness in
  `quality/`), so anyone reproducing its steps in that order would see a phantom archive
  and think the fix had regressed.

## Mutation verification

Across the five rounds the panel ran **57 mutations** against this instruction's code
(A: 9 pins re-bitten at head; B: 25, 24 caught, the one gap closed and re-verified; C:
4 behavioral mutations through the skip guards, plus the guard-deletion and
tautology proofs). The worker ran **11** of its own, each reverting a specific clause,
confirming the named test fails, and restoring from a pristine `shutil.copy2` snapshot
with a scoped `__pycache__` purge.

## After the close

One commit landed after the terminal verdict: Panelist B's last NIT, which it rated
non-blocking and prescribed exactly ("the fix is one conditional on the message string").
The BUG guard refused both a readable manifest carrying real BUG records and an unreadable
one under the single message *"BUG records already exist"* — established only in the first
case, while State P2 tells the agent to report the refusal it got. The two states now say
what is true of each. Mutation-verified; the panel did not re-review it.

## Carry-forwards for the design owner

1. **`revert(which=[ids])` selective path** (B, round 1): a `correct` retags the operator's
   own record, so naming that id deletes their requirement. Pre-dates 031; no longer
   invited by any operator-facing text; has no non-test caller.
2. **`AGENTS.md` is auto-written into the operator's repo root** and no run-state template
   mentions it (B's defensive sweep). B supplied the hook: `run_playbook.py` already
   computes one of `wrote`/`regenerated`/`preserved` in `_safe_write_agents_md`, so a
   disclosure can key on that value with no new verification.
3. **Force-track `repos/_benchmark_lib.sh`** (C): one `git add -f` closes 031's two skips
   *and* six pre-existing errors in `test_setup_repos.py` on a fresh clone.
4. **A `setup_repos.sh` ↔ `_bundle_files()` drift test** (C): the benchmark lane has now
   been patched after diverging three times (089n, 050, 031).
5. **`qpb_validate`'s `apply_gitignore_template` remediation** names
   `<clone>/skill-template.gitignore`, which does not exist at the clone root (C).
6. **`archive_previous_run` lacks the dotfile exclusion `check_stale_quality_dir` has** (C),
   so the documented validate-then-run sequence can still produce a phantom archive.
   Pre-existing, reproduced on the parent commit.
7. **The genre veto is a hard filter, not a tie-break demotion** (A): on adopter systems
   whose *subject* is workflow, video coding, index formats or naming, a real spec is
   demoted and the example can fall to a smaller spec-named file. A rated it NIT for
   consistency with its own earlier call and did not ask for the redesign here.
8. **Rename `persona_review_summary.json`** (B): the artifact path is the one place the
   word "persona" still reaches an operator whose message is otherwise jargon-free.
9. **The UX draft and the shipped product describe different things** (B): the draft frames
   the expert review as an offered choice with consent; the shipped design runs it
   automatically and discloses afterwards. Not a contract violation of this instruction —
   which scopes fix 2 to *disclosure of an automatic pass* — but the operator has approved
   one of the two, and the repo cannot tell which.
