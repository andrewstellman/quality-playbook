# Panel A — Correctness / Spec Compliance — QPB instruction 058 (v1.5.10)

Reviewer: PANEL A (independent adversarial). Charter: correctness / spec compliance.
Source of record reviewed: `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py`
(git-tracked) and `bin/run_playbook.py`, `bin/qpb_harness_tick.py`. The gitignored
`.github/skills/.../quality_gate.py` copy was NOT reviewed (per charter).
Spec: `docs/design/QPB_v1.5.10_Language_Disclosure_And_Override_Design.md`.

All line refs are against the working-tree files at review time.

---

## 1. `--language` threaded through the FULL chain `main → check_repo → check_test_file_extension` — PASS

- `main` parses `--language` via a two-pass arg loop: `--language` sets
  `expect_language`, the next token is captured into `language_override`
  (`quality_gate.py:6903-6917`). Correct token consumption (mirrors `--version`).
- Validation against `_LANG_TO_VALID` keys with exit 2 on unknown:
  `quality_gate.py:6930-6935` — `if language_override and language_override not in
  _LANG_TO_VALID:` prints a usage error and `return 2`. Verified live: invoking
  `main(['--language','xyz','.'])` returns exit code 2 and lists the valid choices.
  The exit-2 is correctly distinguished from the exit-1 "no repos" usage.
- Passed to `check_repo`: `check_repo(rd, version, strictness,
  language=language_override or None)` (`quality_gate.py:6978`). The `or None`
  normalizes empty string to None (clean).
- `check_repo` forwards to the extension check:
  `check_test_file_extension(repo_dir, q, language=language)` (`:6830`), and to the
  disclosure recorder `_maybe_record_language_disclosure(repo_dir, repo_name,
  language)` (`:6860`).
- `check_test_file_extension` validates the OVERRIDE, not the detected plurality:
  when `language` is set it assigns `detected_lang = language` and skips the
  `detect_project_language()` call entirely (`:3981-3988`); the `_LANG_TO_VALID`
  lookup and extension comparison then run against the override (`:3994-4009`).
  `ran_on` is surfaced via `info(f"--language override active: ran_on={language}")`
  (`:3986`).

This is exactly the threaded-through-the-call-site behavior the spec D3 demands —
not the function body alone. No mismatch path where the gate validates the detected
language while the agent tested the override.

NIT (non-blocking): the `ran_on` record produced inside `check_test_file_extension`
is only an `info()` log line; the *persisted* `ran_on` in INDEX.md §11 summary is
the operator/agent's responsibility (enforced by the conditional INDEX check, point
3). The two `ran_on` notions are distinct and both present — no gap, just two
layers. Worth knowing but not a defect.

## 2. `detect_project_language` is a thin delegate; byte-identical winner — PASS

- `detect_project_language` is now `ranked = detect_project_languages(repo_dir);
  return ranked[0][0] if ranked else ""` (`quality_gate.py:2815-2822`). It performs
  no independent walk — the singular and plural cannot drift by construction.
- Byte-identical-winner verification against the pre-058 source
  (`git show 518270c:...`): the `language_order` list, the `excluded` set
  (incl. dist/build/out/target), the `order_index` `setdefault` (clj keeps idx 9,
  its first occurrence), the depth-5 `os.scandir` walk, and the extension counting
  are character-for-character identical between the old `detect_project_language`
  body and the new `detect_project_languages` body.
- Tiebreak equivalence: pre-058 returned `max(counts, key=lambda l:
  (counts[l], -order_index[l]))`; post-058 returns
  `sorted(counts.items(), key=lambda kv: (-kv[1], order_index[kv[0]]))[0][0]`.
  `max` picks the highest count and, among equal counts, the smallest
  `order_index` (because `-order_index` is maximized). The sort picks the smallest
  `-count` (= highest count) and, among ties, the smallest `order_index`. Each lang
  has a unique `order_index`, so no exact-key tie exists and the iteration-order
  ambiguity of `max` is irrelevant. The `[0]` of the sort equals the old `max`.
  **Winner is provably byte-identical.**
- Regression confirmed live: `bin/tests/test_quality_gate_language_detection.py`
  passes 9/9, including `test_single_language_pins_unchanged` and the build-output
  exclusion pin.

## 3. Disclosure matches detection (stdout block AND INDEX check on the SAME condition) — PASS

- Single shared predicate: `_disclosure_fires(ranked)` returns
  `len(languages_over_disclosure_threshold(ranked)) >= 2` (`:2873-2875`).
- stdout block: recorded by `_maybe_record_language_disclosure`, which gates on
  `len(languages_over_disclosure_threshold(detect_project_languages(repo_dir))) < 2`
  → return (`:2886-2888`) — i.e. fires iff `_disclosure_fires` is true. Emitted by
  `_emit_language_disclosures` after the RESULT/verdict lines (`:7005`).
- INDEX check: `check_v1_5_0_index_md` fires the conditional disclosure-field
  requirement on `if not is_legacy and
  _disclosure_fires(detect_project_languages(q.parent)):` (`:5550`). `q.parent` is
  the repo root (q = repo_dir/"quality"), the SAME directory passed to
  `_maybe_record_language_disclosure`. **Both layers share the identical predicate
  and the identical detection input.**
- Threshold D5 verified live: `_DISCLOSURE_MIN_RATIO = 0.10`, `_DISCLOSURE_MIN_FILES
  = 5` (`:2851-2852`); `languages_over_disclosure_threshold` uses denominator
  `total = sum(count for _, count in ranked)` (`:2862`) — `sum(counts.values())`,
  NOT `count_source_files`. Boundary is ≥-inclusive on both bounds (`count >=
  _DISCLOSURE_MIN_FILES and (count / total) >= _DISCLOSURE_MIN_RATIO`, `:2868-2869`).
  Confirmed empirically: 45/5 (exactly 10%, exactly 5 files) → fires; 4 files → no;
  5% → no.
- The conditional INDEX fields are NOT added to `_V150_REQUIRED_SUMMARY_KEYS`
  (`:4772`, iterated unconditionally at `:5534`) — they live in a separate
  `is_legacy`-exempt conditional block (`:5550-5565`), so single-language and legacy
  archived runs are not failed. Matches D2 exactly.

## 4. No `RESULT:` string drift — PASS

- `_compute_final_verdict` produces `total_line` / `result_line`; these are printed
  (`:6985-6986`) before any disclosure work. `_emit_language_disclosures` (`:7005`)
  only `print()`s new lines and is invoked AFTER `total_line`/`result_line`/the
  operator verdict block and BEFORE the trailing `::QPB::` sentinel (`:7023`).
- The disclosure code never touches `result_line`, `total_line`, `exit_code`, or the
  sentinel string; `main` returns the unmodified `exit_code` (`:7026`). The block is
  purely additive print output. No RESULT/total/::QPB:: drift.
- `_LANGUAGE_DISCLOSURES` is reset per-invocation in `_reset_counters` (`:1590`,
  called at the top of `main`), so no cross-call accumulation leaks into another
  run's output.

## 5. D4 archive-on-switch (`bin/run_playbook.py`) — PASS

- `archive_on_language_switch(repo_dir, requested_language)` (`run_playbook.py:3355`):
  reads the prior language via `_read_run_language` (`.qpb_language` sentinel
  preferred, INDEX §11 `summary.ran_on` fallback — `:3310-3337`); returns False when
  no prior or prior == requested (`:3373-3375`); skips when the tree has no live
  content beyond the archive subtrees + sentinel (`:3379-3385`); archives via
  `archive_lib.archive_run(...)` THEN `_clear_live_quality` + `_write_run_language`
  (`:3387-3412`).
- Error-gate replicates BOTH branches per D4: `except ArchiveError` → WARN + `return
  False` (no clear) (`:3394-3403`); `except Exception` → WARN + `return False` (no
  clear) (`:3404-3410`). Clear only runs on the success path (`:3411`). A failed
  archive cannot destroy live artifacts.
- Call-site ordering (idempotency) verified at BOTH sites: `:4790-4794` and
  `:4903-4906` call `archive_on_language_switch(repo_dir, args.language)` BEFORE
  `archive_previous_run(repo_dir, timestamp)`, then `_write_run_language(...)` after.
  On a switch the tree is cleared first, so the following `archive_previous_run`
  no-ops on the cleared tree — no double-archive. The sentinel is preserved by
  `_clear_live_quality` (`:2669-2670`, `:3257`) and treated as non-live by
  `archive_previous_run`, so the language record survives a normal rotation and is
  re-stamped by `_write_run_language` each run.

## Additional threading checks — PASS

- gate argv forward: `_finalize_iteration(... language=...)` appends
  `["--language", language]` to the gate subprocess argv when set
  (`run_playbook.py:5225-5232`); all `_finalize_iteration` call sites pass
  `language=getattr(args, "language", None)` (`:4314, :4955, :4971, :5539, :5560`).
- prompt directive: `_language_prompt_directive` (`:1345-1361`) emits a
  Phase-2 generation-scoping directive, combined into the prompt via
  `_effective_prefix` (`:1363-1367`); used at `:3909, :4236`. Derived from
  `args.language` (not baked into prompt_prefix) so the parent→worker re-dispatch
  re-derives it and never double-applies.
- worker re-dispatch: the child command forwards `--language` (`:5880-5884`).
- arunner native: `qpb_harness_tick.py:618` exposes `LANGUAGE` template var from
  `entry.get("language", "")` for the Phase-2 worker_prompt + gate worker_cmd.
- CLI flag declared `--language` dest=`language` (`:569-576`).

## Targeted test evidence

`python3 -m pytest bin/tests/test_quality_gate_language_detection.py` → 9 passed,
including the single-language byte-identical pins, the build-output exclusion, and
the install-marker exclusions; the hollow-`.clj` substance case FAILs as designed
(the 056 deep-check is intact). Per charter I did not run the full suite (implementer
ran it ×3 stable).

---

## Findings summary

No correctness gaps that defeat the feature. The `--language` override threads
end-to-end through the gate call chain and validates the override (not the detected
plurality); the singular detector is a true delegate with a provably byte-identical
winner; stdout disclosure and the conditional INDEX check fire on the identical
`_disclosure_fires` predicate over the identical detection input; the threshold is
≥-inclusive on the `sum(counts)` denominator; RESULT/total/::QPB:: strings and the
exit code are untouched (disclosure is purely additive); D4 archive-on-switch archives
then clears with both error branches gated and is correctly wired before
`archive_previous_run` at both call sites.

NITs (non-blocking): the `ran_on` produced inside `check_test_file_extension` is an
`info()` log line distinct from the persisted INDEX `ran_on`; both layers exist, no
gap.

VERDICT: SHIP
