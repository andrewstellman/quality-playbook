# QPB 1.6.1 cloud test protocol

Written 2026-10-02 by the Mac Cowork session for the cloud session running the icalendar experiment. It tests the 1.6.1 changes on a real target. You already have the context: `HANDOFF-2026-10-01-cloud.md`, `QPB_v1.6.1_Cloud_Implementation_Spec.md`, and your own `HANDOFF-QPB-1.6.1-gate-failures.md`.

## What changed since your spec

You were going to implement Features S, W and R yourself (spec §3–5). **The Mac session has implemented them instead,** together with the gate and Feature H fixes from your gate-failures handoff. **Don't implement anything from the spec. Your job now is to test.**

The changes were reviewed by three reviewers (Opus, Sonnet, Fable) over three rounds, and all three ended at SHIP. The full `bin/tests` suite has the same 7 failing files before and after the change; all of them need fixtures or tools that aren't in the repo. Synthesis: `AI-Driven Development/Quality Playbook/Reviews/v1.6.1_cowork_council/SYNTHESIS.md` on the Mac. It isn't needed to run this protocol.

What's in it (12 commits on branch `1.6.1`):

| Feature | What it does |
|---|---|
| **G**: honest gate verdicts | **Bug evidence:** a `── Bug evidence ──` block appears under the lead line in every outcome. It says "reproduced N of N", lists the bugs that rest on questioned requirements, and states what "reproduced" does not show. The `::QPB::` sentinel gains `bug_evidence`, `bugs`, `bugs_reproduced` and `bugs_on_flagged_reqs`.<br>**Curated messages** for requirement overreach, tier mismatch and AGENTS.md. The generic fallback names every failing check, and the failing lines are listed under each category.<br>**A fourth result,** `RESULT: GATE PASSED WITH DECISIONS NEEDED — N requirement decision(s)` (exit 0, `gate_result` "DECISIONS", `verdict_state` "decisions"). It applies when the only blocking items are overreaching requirements that no confirmed bug depends on. An overreach that a bug's `req_id` points at still fails the gate.<br>**`OPERATOR_DECISIONS.md`:** Phase 5 now writes it.<br>**Stale reviews:** Council reviews carry `req_hash`; a review that predates a rewrite is stale.<br>**Other changes:** a missing AGENTS.md is a WARN, not a FAIL; `.rst` is accepted in `cite/`; and the State P5/B/DN templates are updated. |
| **H**: Feature H fixes | **Merge fixes:** a `correct` now backfills the tier and flags prose it didn't narrow (`needs_text_review`). A confirm versus a correct is no longer treated as a conflict. Overlapping adds are clustered by citation.<br>**Persona brief:** `references/persona_brief.md` ships ("a requirement may state only what its quoted passage states").<br>**Remapping:** renumbering is applied on disk (`bugs_manifest.json`, `citation_semantic_check.json`, `req_id_remap.json`).<br>**Smaller fixes:** the disclosure names the reviewers that actually ran, and ingest now warns about nested reference-doc folders it skips. |
| **S**: subagent execution | Phases may run in per-phase subagents if the **parent** runs `qpb_gate_witness.py` after every Phase 6 and pastes its output. The witness re-runs the gate and compares it with `quality/results/quality-gate.log`: RESULT exactly; the Total counts without WARN; and the verdict state from the sentinel and the lead line. It exits 0 on MATCH, 1 on MISMATCH, and 2 if there's no log. Subagents can't nest, so the parent spawns the Feature H personas, the Phase 6 auditor and challenge reviewers. "AUTOMATION ONLY" is gone from the agent files. |
| **W**: claims rules | `references/claims_rules.md`, wired into SKILL.md's reference table, the BUGS.md/writeup guidance, the Phase 5 guide and `what_just_happened.md`. |
| **R**: Prepare upstream submissions | This is Phase 7 path 5 (`references/phase7_guide.md` → `references/upstream_submission.md`). The steps:<br>1. Policy check, written to `quality/upstream/POLICY.md`.<br>2. Shortlist, then **stop for Andrew's pick**.<br>3. Confirmers.<br>4. Fixer.<br>5. A panel of 2 executors and 13 roles, spawned by the parent.<br>6. Prepare one bug at a time: `REVIEW.md`, then **stop**.<br>7. Record the outcome.<br>`scripts/upstream_scripts.py` generates `submit.sh` (draft only; never ready, merge or comment), `dup-search.sh` and `verify.sh`, which Andrew runs with his own `gh` login. |

## Ground rules

- Everything in the handoff's §2 still applies: never push, post or open anything; never fabricate; paste output verbatim; no `Signed-off-by` or `Co-Authored-By`; correctness bugs only.
- Testing 1.6.1 behaviour does not cancel the one-bug-at-a-time protocol. R's stop points are real stops for Andrew.
- Log everything in `CLOUD-LOG.md` under a new heading, **"1.6.1 cloud test"**.
- **Any place where you had to improvise because the skill text didn't cover the case is a defect in 1.6.1.** Record it in `TEST-RESULTS.md` (see the end), even if you worked around it.

## T-0: get the 1.6.1 code and check it's the reviewed code

1. Andrew pushes branch `1.6.1` from his Mac. If he hasn't yet, the patch series is in this folder (`patches/0001…0012-*.patch`); apply it with `git am` onto `1.6.1` at `eaaffd7`.
2. In a fresh QPB clone on `1.6.1`, confirm the reviewed content:
   - `git rev-parse HEAD^{tree}` must print `306ec25fab939a07bf8cfec686403f2ecce3edc0`. Commit SHAs may differ after `git am`, but the tree must not.
   - `git log --format=%s eaaffd7..HEAD` must show the 12 subjects, from `v1.6.1 [G]: gate verdict honesty …` to `v1.6.1 [council-3]: witness compares the lead line …`.
   - **If the tree hash differs, stop and tell Andrew.**
3. Run `bin/tests` file by file (`python3 -m pytest bin/tests/<f> -q -p no:cacheprovider`, with a timeout per file). Expected: every file passes except at most these 7, which also fail without the change: `test_doc_classification_v160`, `test_language_disclosure_override_058`, `test_logs_flat_layout_end_to_end`, `test_pretag_cleanup_089i`, `test_setup_repos`, `test_setup_repos_bundle_parity_089n`, `test_virtio_run_fixes_031`. Any other failure: record it with output, then go on.

## T-1: the new gate on your real 90-bug run (Feature G)

Use the gap iteration's `quality/` folder, the one in `qpb-icalendar-cloud-03-gap.zip` that produced `Total: 8 FAIL (7 substantive, 1 record-keeping), 14 WARN`. Work on a **copy**, and don't modify the run.

Run the 1.6.1 gate on it (`python3 <1.6.1>/plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py .` from the copy's root) and paste:
- the `Total:` / `RESULT:` lines;
- the whole operator verdict block;
- the `::QPB::` line.

**Predictions, written before the run. Report each as HELD or FAILED, with the lines that show it.**

| # | Prediction |
|---|---|
| P1 | `── Bug evidence ──` says `Reproduced: 90 of 90 bugs`, with red and green logs checked 180 of 180, and includes the sentence about what "reproduced" does not show. |
| P2 | It lists the bugs on questioned requirements: BUG-012 (REQ-013); BUG-016, BUG-031, BUG-042, BUG-043, BUG-069 (REQ-021). |
| P3 | AGENTS.md appears as a WARN, not a FAIL. |
| P4 | REQ-013 and REQ-021 stay **substantive** FAILs, because confirmed bugs depend on them, and their lines name those bugs. |
| P5 | REQ-010, REQ-052, REQ-053, REQ-054 become **operator-decision** FAILs, because no confirmed bug points at them. **Exception:** if any confirmed bug in `bugs_manifest.json` has no usable `req_id`, they stay substantive, with a "cannot rule out" note. Check which applies and say so. |
| P6 | REQ-016 (tier 3 with a citation) is a **record-keeping** FAIL (`check_v1_5_0_requirements_manifest` is a record-keeping check, unchanged) with the curated tier-mismatch message, not `[generic]`. |
| P7 | Overall: `Total: 7 FAIL (2 substantive, 1 record-keeping, 4 operator-decision), N WARN` and `RESULT: GATE FAILED — 2 substantive issue(s) must be fixed`. If the exception in P5 applies: `7 FAIL (6 substantive, 1 record-keeping), …` and `6 substantive`. (Your 1.6.0 count "7 substantive, 1 record-keeping" was the 6 overreach FAILs plus AGENTS.md as substantive, and REQ-016 as record-keeping. In 1.6.1 AGENTS.md is a WARN.) |
| P8 | "What happened" says the bugs are reproduced and that what failed is the paperwork behind the requirements. It does not say the run "can't be trusted". |
| P9 | The run has no `req_hash` in `citation_semantic_check.json` (it was written by 1.6.0), so you get one WARN about missing `req_hash`, not a FAIL. |
| P10 | The sentinel has `"bug_evidence":"reproduced","bugs":90,"bugs_reproduced":90,"bugs_on_flagged_reqs":6`. |

Then judge the verdict block as an adopter would. Read it cold: is it clear what is wrong, who has to act, and whether the 90 bugs can be acted on? Record any sentence that misleads.

## T-2: the witness (Feature S)

On the same copy:

1. Write the 1.6.1 gate's own output to `quality/results/quality-gate.log`, then run `python3 <…>/scripts/qpb_gate_witness.py .`. Expect exit 0 and `MATCH`.
2. Create AGENTS.md at the copy's root and run the witness again. Expect exit 0 and a MATCH that says the WARN count differs.
3. Edit the log's `RESULT:` line to `RESULT: GATE PASSED`. Expect exit 1 and `MISMATCH`.
4. Restore the log. Edit the lead line to `[PASS] GATE PASSED -- this run looks solid` but keep the sentinel. Expect exit 1 and `MISMATCH … (lead line`.
5. Delete the log. Expect exit 2.

Also check that the witness can be found where an installed skill would look for it: `quality-playbook install --into <scratch> --ai-tool claude`, then confirm `bin/qpb_gate_witness.py` exists in the installed skill.

**Evidence from your own run.** For each Phase 6 you've already run under 1.6.0 (baseline, gap, and any others), put your parent gate output next to the subagent's log, as the spec's "Evidence for the subagent-execution change" section asks. If you finished more iterations since your last report, include them.

## T-3: Feature H on the real persona moves (best effort)

If your run kept the persona outputs (moves per persona, candidates, `expert_review_summary.json`), replay the merge with the 1.6.1 code (`persona_merge.merge_personas` on those moves against a copy of the Phase 2 manifest). Check that:

- REQ-016's `correct` now carries the cited document's tier;
- REQ-013's `correct` is applied, with the other persona's confirm recorded as a dissent;
- the seven overlapping RECUR-range adds form one cluster, with the others recorded as duplicates;
- REQ-021's narrowed `correct` flags the prose it didn't supply (`needs_text_review`).

If the persona moves weren't kept, write "not testable from saved artifacts" and say what QPB should save so it can be tested next time.

## T-4: "Prepare upstream submissions" on icalendar (Feature R, the main test)

This replaces the handoff's §6 and the spec's §5.5. Do it **using only what the skill text says.**

1. Reinstall the skill into the icalendar target from the 1.6.1 checkout (`quality-playbook install --into <icalendar> --ai-tool claude`). Run the install validator to `status=ok`. Leave the existing `quality/` folder in place.
2. Open `references/phase7_guide.md` and follow path 5 into `references/upstream_submission.md`.
3. Go step by step, with these stops:
   - **Policy check:** write `quality/upstream/POLICY.md`. icalendar's AI policy allows AI-assisted contributions if:
     - an issue is opened first;
     - the commit message names the model and how it was used;
     - the change-log entry mentions AI use.
     - Check that the skill's step records all of these.
   - **Shortlist:** propose 3–4 bugs, then **stop for Andrew's pick.** The 6 bugs on questioned requirements should be deprioritised, as the skill text says.
   - **Duplicate search:** generate `dup-search.sh` with `upstream_scripts.py`. Andrew runs it on his Mac (his `gh` works there; yours is blocked) and gives you `dup-search.out`.
   - **Confirm, fix, then the panel** (2 executors + 13 roles, spawned by you as the parent). Then a focused re-review of any code revision.
   - **First bug:** `quality/upstream/<slug>/REVIEW.md` plus the explanation in chat, then **stop.**
   - **Generate** `submit.sh` and `verify.sh` with `upstream_scripts.py`. Run `bash -n` on each. Check that `submit.sh` opens the issue first (icalendar is an issue-first project) and contains no `gh pr ready/merge/comment` or `gh issue comment`.
   - Andrew decides whether to submit. Only if he does: run the Record step with his pasted output and `verify.sh`.
4. While you work, apply `references/claims_rules.md` to every operator-facing text. Afterwards, run its checklist on the `REVIEW.md` and the issue/PR text, and record any line that fails.

## Results file

Write `TEST-RESULTS.md` (and zip it at each stop, with `CLOUD-LOG.md`) containing:

- **T-0:** the tree hash, and the test files that passed or failed, with output for any new failure.
- **T-1:** P1–P10 each marked HELD or FAILED, with verbatim lines; plus your cold-read notes on the verdict block.
- **T-2:** steps 1–5 with exit codes and output; the install check; and your table of parent gate output versus subagent log.
- **T-3:** each check marked HELD, FAILED or NOT TESTABLE.
- **T-4:** each step marked done, partly or blocked, with the files it produced. A **defects list** of every place the skill text was missing, wrong or ambiguous, or that forced you to improvise. Each defect gets: file and line, what happened, and a suggested fix.
- **Summary:** what 1.6.1 got right on a real target, and what must change before 1.6.1 merges into `main`.
