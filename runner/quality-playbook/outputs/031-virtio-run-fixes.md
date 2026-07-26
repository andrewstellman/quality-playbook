# Output for 031-virtio-run-fixes.md
**Status:** completed

## Terminal verdict: unanimous SHIP (5 rounds)

| Round | A — worked example | B — disclosure | C — benchmark install |
|---|---|---|---|
| 1 | FIX-REQUIRED (2×P1) | FIX-REQUIRED (2×P0, 4×P1) | FIX-REQUIRED (3×P1) |
| 2 | FIX-REQUIRED (2×P1) | FIX-REQUIRED (3×P1) | FIX-REQUIRED (1×P1) |
| 3 | FIX-REQUIRED (1×P1) | **SHIP** | **SHIP** |
| 4 | **SHIP** | **SHIP** | **SHIP** |
| 5 (terminal, on head) | **SHIP** | **SHIP** | **SHIP** |

**The acceptance oracle was satisfied by the first commit.** Everything below was found
after that, by reviewers who ran the code rather than reading it.

---

## Fix 1 — the worked example no longer suggests the wrong file

**Before.** The end-of-Phase-1 show invited a correction with *"treat `X` as my
specification"*, where `X` was the **largest promotable background document**. On the real
virtio corpus that is `linux-coding-style.rst` (45 KB) rather than the actual spec
`virtio-spec-behavioral-contracts.md` (7.8 KB) — the feature built to help an operator
recover a mis-classified spec was telling them to promote a style guide.

**After** (`doc_classification.py`):
- a document must carry a **name signal** to be named (`spec`, `specification`, `contract`,
  `reference`, `protocol`, `api`, `rfc`, `standard` — whole-token, on the filename);
- a **veto** beats a spec word, organized by the rule that decides membership: *genre*
  words (guide, tutorial, FAQ, changelog, examples, contents, index/toc) and
  *practice-domain* words (coding, documentation, naming, formatting, engineering, commit,
  review, contributing, workflow — "how the team works", not "what the software must do");
- **documents and source files are separate strata** — a source file is named only when no
  document is promotable (preserving instr 030's code-shaped-contract affordance);
- operator-**demoted**, operator-**promoted** and machine-readable-contract records are
  excluded from candidacy;
- when nothing qualifies, the example uses the **neutral placeholder** `<the-file>`; when
  nothing is promotable at all it names nothing (instr 030's contract).

**The spec-vs-style-guide result, on the real corpus** (`repos/virtio-1.6.0/reference_docs/`,
6 docs, rendered):

```
**Is that right?** … the wording I understand looks like *"treat
`reference_docs/virtio-spec-behavioral-contracts.md` as my specification"* or *"that one
is just background"*.
```

Panelist A extended this to four more real corpora: `express-1.6.0` (19 docs) →
`01_API_Reference.md`; `chi-1.6.0` (18) → `13_api_reference.md`; `bus-tracker-smoke` (10) →
`02_siri_api_endpoint.md`; a virtio variant holding only the style guide and the history
doc → `<the-file>`. **Four right answers and one honest withholding.**

## Fix 2 — the persona pass is disclosed in the end-of-Phase-2 message

**Before.** The pass auto-applied changes to the operator's requirements and the standard
message said nothing; the only trace was a JSON file they had no reason to open.

**After.** `persona_apply.persona_review_disclosure(review_summary)` renders the
disclosure, and returns `None` when the pass did not run. Sample (plain language, no
internal labels):

```
### I had expert reviewers check your requirements

Before moving on, I brought in expert reviewers — one who knows this kind of system and
one who reviews for security — to read your requirements against the documents you gave
me. They only add or rewrite a requirement when they can point to the documentation that
backs it up.

Here's what they did:
- Added 2 requirements your documentation calls for but the list was missing.
- Rewrote 1 requirement to match what your documentation actually says.
- Removed 1 requirement they judged does not belong. (A removal isn't checked against your
  documents the way an addition is — worth a look.)
- Set aside 1 suggestion they could not back up with your documents. **I did not act on
  it** — it is listed for you to judge.

**Your requirements were changed by this — 4 changes in all.** Every one of them is listed
in `quality/persona_review_summary.json` with what it is based on, so you can check the
reasoning. Requirement numbers were put back in order afterwards, so some of them shifted.
If you would rather not keep any of this, say **undo the expert review changes** and I
will put your requirements back exactly as they were before this step.
```

A run where the pass did **not** run (disabled, or never run) adds nothing — the renderer
returns `None` and the State P2 block is emitted exactly as before.

**The undo in that sentence is now real.** It was not: `revert()` restored from an
in-memory field on a `PersonaPass`, and the agent runs the pass in a scripted invocation
that exits before the operator can answer. The pass now persists
`quality/requirements_manifest.pre_review.json`, and `revert_from_disk()` restores the
whole prior manifest — exact for adds, rewrites **and** removals — renames the summary to
`persona_review_summary.undone.json` (never clobbering an earlier one), and refuses in five
distinguishable states rather than guessing: the pass never ran; a pass ran but predates
the snapshot (*the requirements were changed* — point at the summary); already undone; BUG
records exist (a late undo would orphan BUG→REQ links); and a bug manifest it cannot read,
which says exactly that instead of claiming BUG records exist.

**Ordering.** The block is emitted **after** the pass — it cannot report a pass that has
not happened. Because the requirements-interview offer lives inside that block, one order
is now stated in every surface: **finalize → pass → re-render `REQUIREMENTS.md` → State P2
block carrying the offer and the disclosure together.**

## Fix 3 — a `setup_repos.sh` target validates Phase 0 clean

**Before** (`qpb_validate` on a freshly set-up virtio target):

```
closure_check path=skill-template.gitignore kind=scaffolding_template status=fail detail=missing
closure_check path=ai_context/TOOLKIT.md kind=reference_file status=fail detail=missing
scaffolding_check path=.gitignore kind=gitignore_scaffold status=fail detail="absent or missing QPB sentinel"
validation_complete status=remediable findings=3
```

**After**, same command, same target:

```
validation_complete status=ok findings=0
```

The script stages both documents into the FLAT `.github/skills/` install root, appends the
gitignore template (idempotent, header-keyed, newline-safe), and creates the
`quality/RUN_INDEX.md` sentinel the appended `!quality/RUN_INDEX.md` negation makes
`run_playbook`'s pre-flight require. **The validator is unchanged** — verified per-path at
head by Panelist C, who also confirmed no closure or scaffolding requirement was relaxed
anywhere. Panelist C re-ran five targets (`virtio`, `express`, `casbin`, `agentscope`,
`httpx`): all `status=ok findings=0`.

Completing the install turned out to introduce three further failures, all now fixed:
`cat >>` destroyed the last rule of a newline-less `.gitignore` (six repos under
`repos/clean/`); the new sentinel made `archive_previous_run` fabricate a `partial` prior
run on every fresh target; and on the three git-carrying clean repos `cleanup_repo` reverted
the appended `.gitignore`, silently un-installing the fix.

## Acceptance oracle — pass/fail per item

| # | Item | Result |
|---|------|--------|
| 1 | Worked example names the spec-like doc or a placeholder — never the style guide; **tested** | **PASS** — real virtio corpus + 4 more benchmark corpora; the practice-domain class (`documentation-standards.md` etc.) closed after A caught its own wrong all-clear |
| 2 | End-of-Phase-2 discloses the pass in plain language when-and-only-when it ran, reviewable + revertible | **PASS** — B scanned 10+ rendered shapes for jargon (none), verified every claim against the code, and round-tripped the undo from disk alone |
| 3 | A `setup_repos.sh` target validates Phase 0 clean; validator unchanged | **PASS** — 3 findings → `status=ok findings=0` on five targets; validator byte-identical |
| 4 | Full suite green | **PASS** — **2906 / 0 failures / 14 skipped, Python 3.14.6** |

## Files changed

| File | Change |
|------|--------|
| `plugins/.../scripts/doc_classification.py` | `_spec_like_name()` + `_SPEC_NAME_TOKENS` / `_NON_SPEC_NAME_TOKENS` (genre + practice-domain veto); doc/source stratification; candidate exclusions (operator-demoted, operator-promoted, contract); `_NEUTRAL_EXAMPLE` |
| `plugins/.../scripts/persona_apply.py` | `persona_review_disclosure()`; `PRE_REVIEW_MANIFEST_NAME` + snapshot write in `run_feature_h`; `revert_from_disk()` + `UNDONE_REVIEW_SUMMARY_NAME`; `revert()` limitation documented |
| `repos/setup_repos.sh` | stages `skill-template.gitignore` + `ai_context/TOOLKIT.md`; newline-safe idempotent `.gitignore` append; `quality/RUN_INDEX.md` sentinel; loud WARNINGs instead of silent skips |
| `bin/run_playbook.py` | `RUN_INDEX.md` joins `_LANGUAGE_SENTINEL` in `archive_previous_run`'s `non_live` |
| `plugins/.../scripts/benchmark_lib.py` | `.gitignore` joins `AGENTS.md` in `PROTECTED_EXACT` |
| `references/what_just_happened.md` | State P2 — the disclosure, the boundary order, the undo procedure and its refusal states; `persona_review_summary.json` added to the "do not invent counts" sources |
| `phase_prompts/phase2.md`, `references/requirements_pipeline.md` (§ E.9 steps 6–7), `references/phase2_generation_guide.md`, `SKILL.md` | the same one order + the disclosure + the undo |
| `references/artifact_contract.md` | three new rows: the review summary, the pre-pass snapshot, the undone summary |
| `bin/tests/test_virtio_run_fixes_031.py` | **new**, 59 tests |
| `bin/tests/test_classification_review_v160.py` | two instr-030 worked-example fixtures updated for the deliberately narrowed contract |
| `bin/tests/test_phase_prompts_externalized.py` | phase2 `EXPECTED_HASHES` rebaselined twice (14199 → 15025 → 15747) |
| `docs/process/QPB_v1.6.0_Instruction_031_Self_Council/synthesis.md` | tracked synthesis |

## Commits made (branch `1.6.0`, local only — never pushed)

- `159c251` — the three fixes.
- `b95c0f5` — fix-up 1: round-1 findings (3× FIX-REQUIRED closed).
- `7ef67d0` — fix-up 2: round-2 findings.
- `0175947` — fix-up 3: round-3 findings.
- `82de5a6` — fix-up 4: round-4 NITs.
- `fc2bbdd` — tracked synthesis + the post-close NIT.
- `c0f098d` — runner: output for instruction 031.

The orchestrator's uncommitted `docs/design/QPB_v1.6.0_Design.md` edit was left untouched
throughout; no commit here touches that file.

## Verification

- **Full suite 2906 / 0 failures / 14 skipped, Python 3.14.6.**
- **Fresh-clone behavior verified directly:** a pure `git archive` extraction runs the new
  test file at 51 run / 4 skipped / 0 failures (Panelist C repeated this with nothing
  layered in, then proved `_benchmark_lib.sh` is the sole missing dependency).
- **11 worker mutation bites**, each reverting a specific clause, confirming the named test
  fails, and restoring from a pristine `shutil.copy2` snapshot with a scoped `__pycache__`
  purge — never `git checkout --`. The panel ran ~57 more; B's tally was 25 with 24 caught,
  and the one gap it found was closed and re-verified.
- **Fix 3 verified by execution, not inspection:** `agentscope` keeps `uv.lock`; casbin's
  block survives `cleanup_repo`; a fresh target's `quality/` is untouched by
  `archive_previous_run` while a real prior run still archives with its `BUGS.md`.

## Notable observations

- **The oracle passed while the feature was broken.** Fix 2's headline promise ("I will put
  your requirements back exactly as they were") satisfied the instruction's wording and was
  unkeepable in fact — the snapshot lived in a process that exits before the operator can
  answer. A disclosure that promises a capability is a claim about the code.
- **Completing an install is not the same as making it work.** Staging the three items took
  minutes; the three failures that staging introduced (destroyed `.gitignore` rules, a
  fabricated prior-run archive, an install that reverted itself on git-carrying targets)
  took the panel to find.
- **A panelist caught its own false certification.** In round 2 A cleared four filenames
  having actually re-run three; round 3 found the class it had declared closed was still
  open. Two of my own tests were tautologies by the same mechanism.
- **Both `.gitignore`-adjacent hazards from memory held:** `repos/` needs `git add -f` and a
  verified `git show --stat`, and the runner mailbox stays untracked.

## Remaining v1.6.0 release items — for the orchestrator

Unchanged from the 030 output except where noted, plus this instruction's carry-forwards:

(a) broader 1.6.0 acceptance/release testing + Phase 8 tag/merge; (b) set OD-9 from instr
019 data; (c) Feature-G non-plaintext-contract → `FORMAL_DOC` wiring; (d) chi/express/virtio
Slice-1 coherence-fixture regeneration; (e) OD-11 drop/selective-revert BUG-reference
re-point hardening; (f) design-doc refresh (Design.md still describes the removed
fabrication-tell, and now also predates 031's disclosure + undo); (g) the redundant add-REQ
regex arm; (h) **closed by this instruction** (setup_repos.sh install completeness);
(i) runtime agent responsibilities; (j) the `citable_count` / `classification_disclosure`
divergence in the `unwired` degraded state (030 carry-forward, untouched).

**New from the 031 Council** — each is a scope call I did not take:

1. **`revert(which=[ids])` selective path** — a `correct` retags the operator's own record,
   so naming that id deletes their requirement rather than restoring its wording. Predates
   031; no operator-facing text invites it any more; no non-test caller.
2. **`AGENTS.md` is auto-written into the operator's repo root and no run-state template
   says so.** B's defensive-sweep match. The hook already exists:
   `run_playbook._safe_write_agents_md` computes one of `wrote`/`regenerated`/`preserved`,
   so a disclosure can key on that value with no new verification.
3. **Force-track `repos/_benchmark_lib.sh`** — one `git add -f` closes 031's two skips *and*
   six pre-existing errors in `test_setup_repos.py` on a fresh clone (C measured both).
4. **A `setup_repos.sh` ↔ `_bundle_files()` drift test** — the benchmark lane has now been
   patched after diverging three times (089n, 050, 031).
5. **`qpb_validate`'s `apply_gitignore_template` remediation** names
   `<clone>/skill-template.gitignore`, which does not exist at the clone root.
6. **`archive_previous_run` lacks the dotfile exclusion `check_stale_quality_dir` has**, so
   the documented validate-then-run sequence can still produce a phantom archive.
   Pre-existing; reproduced on the parent commit.
7. **The genre veto is a hard filter, not a tie-break demotion** — on adopter systems whose
   *subject* is workflow, video coding, index formats or naming, a real spec is demoted and
   the example can fall to a smaller spec-named file. A design change, not a fix-up.
8. **Rename `persona_review_summary.json`** — the artifact path is the one place the word
   "persona" still reaches an operator whose message is otherwise jargon-free.
9. **The UX draft and the shipped product describe different things** — the draft frames the
   expert review as an offered choice with consent ("I'll ask your okay to start them");
   the shipped design runs it automatically and discloses afterwards. Instruction 031 scopes
   fix 2 to *disclosure of an automatic pass*, so this is not a contract violation — but
   only the operator knows which of the two they approved.

## Council artifacts

- Gitignored: `runner/quality-playbook/reviews/031_self_council/` — three panelist files
  (581 / 666+ / 937 lines), each preserving all five rounds with its own verdict trail.
- Tracked: `docs/process/QPB_v1.6.0_Instruction_031_Self_Council/synthesis.md`.

## Next action expected from orchestrator

None required for 031. The nine carry-forwards above are scope calls for the design owner;
items 2, 3 and 6 are the cheapest and closest to shipped-behavior correctness.
