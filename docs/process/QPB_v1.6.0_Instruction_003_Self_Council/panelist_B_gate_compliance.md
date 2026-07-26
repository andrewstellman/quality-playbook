VERDICT: SHIP

# Panelist B — Interview-Artifact Gate Compliance (v1.6.0 Feature D, instr 003)

Commits reviewed: ca483e2, 5f1b3d6, dd03e77, bcc5585 (checked out at bcc5585 in an
isolated worktree). Baseline = 75e2fab (parent of ca483e2).
Checks under review, in `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py`:
- `check_operator_confirmations_append_only` (line 7774)
- `check_requirements_review` (line 7864)
Both registered in `check_repo` (lines 7957–7958), both `@verdict_category(VERDICT_SUBSTANTIVE)`.

Priorities: **all findings are P2.** No P0/P1. The highest-value question
(conditional inertness / no FAIL-flip regression) is empirically clean.

---

## 1. Conditional inertness — PASS (highest-value question)

Ran the FULL gate at both baseline (75e2fab) and review (bcc5585) against all six
required trees: the three render fixtures (`bin/tests/fixtures/render_contract_v160/{chi,express,virtio}`)
and three archived metrics trees (`metrics/v1.5.10_integration_regression/{chi,express,virtio}-1.5.8`).

- Substantive FAIL counts are **identical** baseline↔review on every tree
  (18 / 18 / 18 / 10 / 32 / 12).
- Full-output diff (base vs review) shows the ONLY changes are (a) the two new
  `[Operator Confirmations]` / `[Requirements Review]` INFO sections and (b) a
  non-semantic timestamp in the `::QPB::` sentinel. **No FAIL introduced, no
  WARN introduced, no verdict flip.**
- On all six trees both checks emit only `INFO: ... not present — no interview has
  run`.
- Zero false-trigger risk confirmed: `find repos metrics bin/tests` for
  `REQUIREMENTS_REVIEW.md` / `operator_confirmations.jsonl` returns nothing. The
  new artifact name `REQUIREMENTS_REVIEW.md` also does NOT collide with the
  superseded v1.5.7 walkthrough names (`REVIEW_REQUIREMENTS.md` /
  `REFINE_REQUIREMENTS.md`, deleted in dd03e77), so archived pre-v1.6.0 trees
  cannot trip these checks by coincidence.

Verdict on item 1: clean. A new blocking check that fires on existing runs was
the regression to fear; it does not happen.

## 2. REQUIREMENTS_REVIEW.md validation — behaves as specified; the Wiegers check is trivially satisfiable (P2)

Drove `check_requirements_review` directly (captured `_FAIL_RECORDS`/`WARN`):

| case | result | expected | ok |
|---|---|---|---|
| absent file | silent | silent | ✓ |
| (a) empty / whitespace-only | FAIL (substantive) | FAIL | ✓ |
| (b) prose, no dimension | FAIL (substantive) | FAIL | ✓ |
| (c) dimension, no move | WARN (not FAIL) | WARN | ✓ |
| (d) well-formed | PASS | PASS | ✓ |

**Finding P2-a — the Wiegers-vocabulary check is substring-based and trivially
satisfiable** (quality_gate.py:7887, `if not any(dim in lowered ...)`; 7896 same
for moves). Confirmed by execution:
- `"The interview is now complete. ... We confirm done."` → **PASS**. The word
  "complete" in unrelated prose satisfies the "Complete" dimension. (This is
  exactly the triviality the charter asked about — answer: yes, it passes.)
- `_REQ_REVIEW_DIMENSIONS` substrings also match inside their own negations:
  "incons**istent**" contains "consistent", "dis**honest**" contains "honest",
  "in**complete**" contains "complete".
- `_REQ_REVIEW_MOVES` match as substrings: "**add**ress"/"p**add**ing" satisfy
  "add", "**defer**red" satisfies "defer".

Severity is P2, not blocking: the failure mode is a **false-PASS** (too lenient),
never a false-FAIL, so it cannot regress an existing run (item 1); and it guards a
conditional, human-readable defect log, not a machine-consumed or durability
artifact. But the check delivers materially less than "speaks the shared Wiegers
vocabulary" implies — it is a presence-of-substring heuristic. A word-boundary
match against the capitalized dimension tokens, or requiring a dimension *heading*,
would make it meaningful.

## 3. operator_confirmations shape validation — correct field list; two lenient edges (P2)

All malformed records FAIL as required (drove `check_operator_confirmations_append_only`):
bad JSON line → FAIL; non-dict array `[1,2,3]` → FAIL; non-dict scalar `42` → FAIL;
missing required field (dropped `session_id`, dropped `operator_statement`) → FAIL;
invalid move `frobnicate` → FAIL; record with no `transcript_citation` → well-formed
(correct — it is conditional).

**Required-field list is exactly correct against schemas.md §9.5.1.**
`_OPCONF_REQUIRED_FIELDS` (quality_gate.py:7752) = `ts, move, req_title,
conditions_of_satisfaction, operator_statement, session_id`. §9.5.1 marks those six
"yes" and `transcript_citation` "conditional" — the gate correctly omits
`transcript_citation` from the required set. `_OPCONF_MOVES` matches §9.5.1's five
moves.

**Append-only invariant (the load-bearing F-2a guarantee) is correct.** Against a
`.prior.jsonl` snapshot: genuine append → PASS; truncate (2 lines → 1) → FAIL;
in-place rewrite → FAIL; reorder [A,B]→[B,A] → FAIL; identical → PASS; no snapshot +
well-formed → PASS. This is well covered by tests
(`test_truncating_rederive_fails`, `test_rederive_preserving_confirmations_passes`,
`test_operator_confirmations_gate_validates`).

**Finding P2-b — shape check is presence-only, not type-checked.** A record with
`req_title: 123` (integer) **passes** the gate, though schemas.md §9.5.1 types every
required field as `string` and the sole sanctioned writer
`run_state_lib.append_confirmation` (run_state_lib.py:1716) *does* reject non-string
fields. The gate is more lenient than both the schema and the writer.

**Finding P2-c — `move: null` slips through.** A record with `"move": null`
(present-but-null) passes: the missing-field check sees the key present, then
`move = obj.get("move")` is `None` and the `if move is not None` guard (7818–7819)
skips move-value validation. The writer rejects this too.

Both P2-b/P2-c require a hand-edit or a non-sanctioned writer to occur, so they are
robustness gaps, not live defects — but the gate is supposed to be the backstop for
exactly the writer being bypassed.

## 4. Artifact registration — correct call, confirmed

`REQUIREMENTS_REVIEW.md` and `operator_confirmations.jsonl` are registered
**conditional** in `references/artifact_contract.md` (lines 20–21, "If a validation
interview ran") and are **absent** from `validate_phase_artifacts.py::_validate_phase2`
(grep: no reference to either name in that file).

This is correct. The interview runs post-Phase-2 (playbook-end, "offers but never
auto-starts", Design §6). `_validate_phase2` (validate_phase_artifacts.py:323)
enforces the Phase-2-boundary artifact set — record-shaped manifests
(unconditional) plus `citation_semantic_check.json` and `RUN_CONTRACT.md`
(conditional). At the Phase-2 boundary the interview has not run, so the two
artifacts do not exist; adding them to `_validate_phase2` would FAIL **every** normal
run at the boundary. The worker's decision mirrors the same explicit reasoning
already recorded for `RUN_CONTRACT.md` (artifact_contract.md line 53:
"Deliberately not added to the unconditional Phase-2 required list, which would
retroactively fail every archived pre-v1.6.0 tree"). Confirmed correct.

## 5. Verdict category

- `check_operator_confirmations_append_only = SUBSTANTIVE` — **correct.** The
  truncation/prefix failure is the load-bearing F-2a durability guarantee (a
  re-derivation destroying operator-confirmed work). A corrupt-shape failure equally
  defeats durability ("a durability log that cannot be parsed cannot protect the
  operator's work"). Substantive is right.

- `check_requirements_review = SUBSTANTIVE` — **defensible, but arguably
  record_keeping (P2 judgment note).** `REQUIREMENTS_REVIEW.md` is a human-readable
  defect log; the *durable* record is `operator_confirmations.jsonl`. An empty or
  vocabulary-poor defect log while the jsonl is intact is documentation hygiene, not
  lost work or corrupted data — the profile the `record_keeping` category exists to
  hold. The worker's substantive choice is defensible (an interview that ran but
  recorded nothing is a real signal), and because the check is conditional it cannot
  affect existing runs either way. Flagging for the panel, not blocking.

## Mutation bite (as instructed) — passed, and surfaced a coverage gap (P2)

Neutered the Wiegers-dimension FAIL (`if not any(...)` → `if False and not any(...)`
at quality_gate.py:7887), purged `__pycache__`, ran
`test_feature_d_interview_fixture_v160.py` + `test_feature_d_supersession_v160.py`:
**all 18 tests still PASS.** No test went red.

**Finding P2-d — the no-Wiegers-dimension FAIL path (and the empty-log FAIL path)
has no automated coverage.** `test_defect_log_gate_validates` only exercises the
PASS path (a well-formed log). No test asserts that a dimension-less or empty log
FAILs, so a future regression neutering that guard would ship silently. The
load-bearing durability check is, by contrast, well covered. Combined with P2-a, the
Wiegers-dimension check is both lenient and untested.

Restored the gate file from a fresh `shutil.copy2` snapshot of the clean bcc5585
working file; `git diff --exit-code` on quality_gate.py is clean (byte-identical to
committed bcc5585). Also restored two `metrics/.../virtio-1.5.8/quality/mechanical/`
fixture files that a checkout carried in (fixture data, not my edits). Purged
`__pycache__`. **Worktree is clean** (`git status --short` empty).

## Full suite

`python3 -m pytest bin/tests/ -q` → **Ran 2573 tests** (matches the charter's
expected count), 2550 passed, 16 skipped, and **7 environmental non-passes**
unrelated to Feature D: 6 errors in `test_setup_repos.py` and 1 failure in
`test_language_disclosure_override_058.py`, all caused by the worktree lacking the
`repos/` benchmark tree (e.g. `FileNotFoundError: repos/_benchmark_lib.sh`;
"no baseline repo present under repos/"). These files were last touched in v1.5.8
(b44ce03), touch neither check under review, and fail identically regardless of the
003 commits. No Feature D or gate test fails.

---

## Summary

The two conditional gate checks are inert on every existing run (empirically proven,
no FAIL flip), the required-field list is exactly correct against schemas.md §9.5.1,
the load-bearing append-only durability guarantee works and is tested, and the
registration decision (conditional in the artifact contract, out of `_validate_phase2`)
is correct. The findings — Wiegers substring triviality (P2-a), presence-only shape
check (P2-b), `move: null` gap (P2-c), and the untested no-dimension FAIL path (P2-d),
plus a doc note below — are all P2 quality/robustness observations on a conditional,
non-load-bearing quality nudge. None can cause a false-FAIL on existing runs or
destroy operator work.

Doc note (P2): schemas.md §9.5.2 says "'Shortens' is measured by line count: the
file may only grow," but the implementation enforces a stricter **byte-prefix**
invariant (also catches in-place rewrites that preserve line count). The
implementation is stronger than the prose describes; the prose undersells it.

**VERDICT: SHIP.** No P0/P1. Suggested (non-blocking) follow-ups for a later
point-release: word-boundary the Wiegers/move matching (P2-a), type-check required
fields and reject `move: null` in the gate to match the writer (P2-b/c), add a
negative-case test for the dimension-less/empty defect log (P2-d), and reconcile the
§9.5.2 line-count wording with the byte-prefix implementation.
