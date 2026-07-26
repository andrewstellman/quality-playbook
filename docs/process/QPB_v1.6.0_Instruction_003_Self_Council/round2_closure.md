# Instruction 003 self-Council — Round 2 (closure)

Closure re-review of the fix commit **`d562f73`** ("v1.6.0 [instr 003]: close the
self-Council findings"). Each panelist re-reviewed in its own isolated git worktree
(the runner hazard from 002: two reviewers sharing one tree produced phantom failures
when one ran a mutation bite). C (supersession) was not re-run — its charter's surface
was untouched by the fix, so its Round-1 SHIP stands.

**Outcome: unanimous SHIP.** All Round-1 findings CLOSED; each verified with a mutation
bite (snapshot → mutate → confirm RED → `shutil.copy2` restore → hash/clean check),
`__pycache__` purged between mutate and restore, worktree clean at end.

---

## Panelist A — manifest write-back correctness → **SHIP**

- **P1 (F-2a durability inert) — CLOSED.** Two mechanisms now in
  `check_operator_confirmations_append_only` (quality_gate.py:7791-7911): (1)
  manifest-consistency — op-conf REQs in the manifest ⟹ log must exist and be
  non-empty (`_operator_confirmed_req_ids`), no snapshot needed; (2) the original
  prefix-vs-`.prior.jsonl` check, retained for cross-run truncation. Delete-hole and
  empty-hole no longer fall through to a silent PASS/INFO.
- **P2 #2 (tautological correction-mutation test) — CLOSED.**
  `test_correction_dropped_from_manifest_is_caught` drives a real `SCRIPTED_SESSION`
  through `_apply_move_broken_correct` (skips the manifest write, logs honestly) and
  asserts the real acceptance property.
- **P2 #3 (one-directional drift guard) — CLOSED.** `test_schema_table_and_gate_enum_agree`
  now parses §3.7 and asserts both directions.
- **P2 #4 (five-moves, three copies) — CLOSED.** `FiveMovesConsistencyTests`.
- **Bites:** neutered delete-hole condition → `test_deleting_the_log_while_reqs_remain_fails_without_a_snapshot` RED; neutered empty-hole condition → `test_emptying_the_log_while_reqs_remain_fails` RED (false PASS "backing 4 confirmed REQ(s)"). Both restored, clean. Fixture inertness confirmed (`test_operator_confirmations_gate_validates` fails==0). 334 targeted tests pass. No new P1.

## Panelist B — interview-artifact gate compliance → **SHIP**

- **P2-a (substring-satisfiable Wiegers) — CLOSED.** `_mentions()` word-boundary regex;
  empirically "inconsistent"↛"consistent", "dishonest"↛"honest", "addressed"↛"add".
- **P2-d (no FAIL-path coverage) — CLOSED.** `RequirementsReviewGateTests` (5 tests);
  mutation neutering the Wiegers FAIL turned 2 tests RED. Restored, clean.
- **P2-b/c (type-check the record) — CLOSED (behavior verified).** Gate now requires
  non-empty strings. B noted the fix was correct but the **gate path** had no dedicated
  committed test (only the writer, `run_state_lib.append_confirmation`, was covered).
  *Non-blocking residual, since closed by the worker — see below.*
- **Doc drift §9.5.2 — CLOSED.** Byte-prefix + both mechanisms documented.
- 334 targeted tests pass. No new issues.

## Panelist D — F-2a cross-run durability → **SHIP**

- **P1 — CLOSED.** Manifest-consistency verified (absent→FAIL, empty→FAIL, driven off
  `source_type=="operator-confirmation"`); prefix-vs-snapshot retained. Read-path +
  snapshot-before-rewrite instructions genuinely present in
  `references/requirements_interview.md` and `references/phase7_guide.md` (grep+read
  confirmed, not just claimed).
- **P2 #1 (dead+untested run_state_lib copy) — CLOSED.**
  `test_confirmations_append_only_matches_the_gate_mirror` drives the real function
  across 7 cases and asserts the two invariant copies agree (drift guard).
- **P2 #2 (§9.5.2 wording) / #3 (type-check) — CLOSED.**
- **Bite:** neutered `_operator_confirmed_req_ids` → both delete-hole and empty-hole
  tests RED; restored, sha256 match. **No-interview run is not falsely FAILed** —
  directly ran the gate against (1) empty quality/ no manifest, (2) manifest with only
  code-derived REQs: both emit only INFO, zero FAIL. 334 targeted tests pass. No new P1.

---

## Residual closed by the worker (from B)

B's single non-blocking residual: the gate's type-not-presence shape check was verified
correct by direct execution but had no committed test driving
`check_operator_confirmations_append_only` with a malformed record (Round-1 coverage
only exercised the writer). Closed by adding
`F2aDurabilityOracleTests.test_gate_rejects_a_malformed_record_directly` (subtests:
`move=None`, `req_title=123`, `operator_statement=""`, `session_id=None` — each ⟹ FAIL
with "non-empty") plus `test_gate_accepts_a_well_formed_record_directly` (control).
Mutation-bitten: replacing the type-check with a presence-only check turns the malformed
test RED; restored clean. Suite 2584 → **2586**.

## Disposition

Unanimous SHIP, zero open findings. Cleared to file. Worker never pushes/merges —
the operator lands the branch.
