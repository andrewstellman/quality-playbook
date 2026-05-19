# QPB v1.5.3 Phase 3c — RESUMABILITY_REPORT (full 4-kill version)

*Documents the four mid-pass kills exercised during the live
self-audit on QPB SKILL.md. Each kill captures pre/post cursor
state, validates the resumed run reaches `status: "complete"` with a
logically-equivalent artifact, and documents the protocol-level
guarantee (atomic JSONL append + atomic progress write +
verify-and-roll-back on resume).*

*Generated: 2026-04-27 (Phase 3c live run, HEAD 6a0b074).*

## Summary

| Pass | Kill point (cursor / total) | Records on disk pre-kill | Resume cursor (after verify_and_roll_back) | Final state | Result |
|---|---|---|---|---|---|
| A | 12 / 125 | 133 drafts (5 UC + 128 REQ) | 12 (no roll-back needed) | cursor=125, complete | ✓ logically equivalent to uninterrupted run |
| B | 19 / 1392 | 20 citations (idx 0–19) | 20 (rolled forward from 19) | cursor=200, complete (truncated) | ✓ resume picked up at idx 20 with no duplicates |
| C | 29 / 215 | 30 formal records (idx 0–29) | 30 (rolled forward from 29) | cursor=215, complete | ✓ all 200 citations + 15 UCs processed |
| D | n/a (atomic) | n/a | n/a | cursor=198, complete | ⚠ kill semantics degenerate by Pass D's design |

## Protocol-level guarantees (the "why" behind the kill behavior)

The per-pass execution protocol pins three invariants:

1. **JSONL append is atomic.** `protocol.append_jsonl` opens the
   file in append mode, writes one line, and closes it. Each
   record write is durable on the kernel's perspective; a crash
   between records leaves the file consistent (last record either
   complete or absent, never partial).
2. **Progress write is atomic via tmp + os.replace.**
   `protocol.write_progress_atomic` writes the new state to a
   `.tmp` file then `os.replace`s into position. A crash mid-write
   leaves either the previous state intact OR the new state
   complete; never a half-written file.
3. **Resume verifies disk vs progress and rolls back/forward.**
   `protocol.verify_and_resume` reads the last JSONL record's idx,
   compares to the progress cursor. If progress is ahead of disk
   OR behind disk (the latter happens when SIGKILL fired between
   append and progress-write), the cursor is rewritten to
   `last_idx + 1` and a `verify-and-roll-back` note is appended to
   `progress.notes`.

Together these guarantees mean a SIGKILL at any point in any pass
produces a coherent on-disk state that the next run can resume
from. The kills below verify this on real QPB data.

## Kill 1 — Pass A mid-section

**Setup:** ran `python3 -m bin.skill_derivation /Users/andrewstellman/
Documents/QPB --pass A --runner claude --pace-seconds 0` from a
fresh `quality/phase3/`. Waited until `pass_a_progress.json`
reported cursor=12 (i.e., section 12 was about to be processed
but section 11's progress write had completed).

**Kill point:** SIGKILL the python process and the in-flight
`claude --print --model sonnet` subprocess at 01:26:49 UTC.

**Pre-kill state on disk:**

```
quality/phase3/pass_a_progress.json:
  cursor=12, total=125, status="running"

pass_a_drafts.jsonl: 133 lines (5 UC + 128 REQ records covering
                                section_idx 0..11)
pass_a_use_case_drafts.jsonl: 5 lines (UCs from execution-mode
                                       sections 2, 3, 4)
```

**Resume:** ran the same command again. Pass A's
`verify_and_resume` read `pass_a_progress.json` (cursor=12) and
read the last JSONL record (section_idx=11). `expected_cursor =
last_idx + 1 = 12`. Match → resume from cursor=12.

**Final state:** Pass A completed 4 runs in total (1 initial + 3
restarts: Kill 1 resume, then 2 tripwire halts that auto-halted
mid-run on legitimately-fast LLM responses, then a final resume
to completion). Final cursor=125, status="complete", last_updated
07:17:57 UTC.

**Validation:** Final `pass_a_drafts.jsonl` has 1392 records (then
truncated to 200 in commit 2/4 for Pass B tractability). Every
`section_idx` in [0, 125) is represented at least once in the
unioned drafts. No duplicates per section. Logically equivalent
to an uninterrupted run modulo wall-clock variance.

## Kill 2 — Pass B mid-draft

**Setup:** kill helper at `/tmp/qpb_resume_evidence/
kill_pass_helper.py` patches `protocol.append_jsonl` to count
calls and SIGKILL self after the K-th call. Ran `PYTHONPATH=.
python3 /tmp/qpb_resume_evidence/kill_pass_helper.py B
/Users/andrewstellman/Documents/QPB --kill-after 20 --target-file
pass_b_citations.jsonl`.

**Kill point:** `_kill_after` patch fired SIGKILL right after the
20th `append_jsonl` call (the append for `_pass_b_idx=19`). Helper
emitted `[kill_pass_helper] killing after 20 records to
pass_b_citations.jsonl; pid=61977` and exited with returncode 137
(SIGKILL).

**Pre-kill state on disk:**

```
quality/phase3/pass_b_progress.json:
  cursor=19, total=1392, status="running"

pass_b_citations.jsonl: 20 lines (_pass_b_idx 0..19)
```

Note the **discrepancy**: progress reports cursor=19, but the file
contains 20 records (idx 0–19 inclusive, last_idx=19,
expected_cursor=20). This is the exact race the per-pass execution
protocol's verify-and-roll-back step is designed for: SIGKILL
fired between `append_jsonl(record_19)` and
`write_progress_atomic(cursor=20)`, leaving progress one step
behind disk.

**Resume:** ran `python3 -m bin.skill_derivation
/Users/andrewstellman/Documents/QPB --pass B --runner claude`.
`verify_and_resume` read progress.cursor=19 and last_idx=19.
`expected_cursor = 19 + 1 = 20`. progress.cursor (19) ≠
expected_cursor (20) → roll forward: rewrote progress.cursor=20
with `notes = "verify-and-roll-back: cursor 19 -> 20 per disk
state"`. Pass B then resumed from idx=20 onward.

**Final state:** Pass B was halted again at idx=200 (commit 2/4
truncation rationale). Progress finalized to cursor=200, total=200,
status="complete" with the truncation note in `notes`.

**Validation:** `pass_b_citations.jsonl` has 200 lines, every
`_pass_b_idx` in [0, 200) appears exactly once. No duplicates from
the kill+resume. The verify-and-roll-back's 19→20 correction
prevented Pass B from re-emitting `_pass_b_idx=19` as a duplicate
(which would have failed Pass C's invariants downstream).

## Kill 3 — Pass C mid-record

**Setup:** ran `PYTHONPATH=. python3
/tmp/qpb_resume_evidence/kill_pass_helper.py C
/Users/andrewstellman/Documents/QPB --kill-after 30 --target-file
pass_c_formal.jsonl`. The patch counts `append_jsonl` calls to
`pass_c_formal.jsonl` (UC records go to a different file, so the
counter only reflects formal REQs).

**Kill point:** SIGKILL after the 30th formal REQ append (record
for `_pass_c_idx=29`). Helper emitted `[kill_pass_helper] killing
after 30 records to pass_c_formal.jsonl; pid=66366` and exited
with returncode 137.

**Pre-kill state on disk:**

```
quality/phase3/pass_c_progress.json:
  cursor=29, total=215, status="running"

pass_c_formal.jsonl: 30 lines (REQ-PHASE3-001..REQ-PHASE3-030)
pass_c_formal_use_cases.jsonl: absent (not yet reached — UCs come
                                       after REQ phase)
```

Same race as Kill 2: progress.cursor=29 but disk has 30 records.
verify-and-roll-back applies.

**Resume:** ran `python3 -m bin.skill_derivation
/Users/andrewstellman/Documents/QPB --pass C --runner claude`.
verify_and_resume rolled cursor 29 → 30 per disk state. Pass C
resumed from idx=30.

**Final state:** Pass C completed all 215 records (200 citations
processed in REQ phase + 15 UC drafts processed in UC phase).
Final cursor=215, status="complete", last_updated 08:16:22 UTC.

**Validation:** `pass_c_formal.jsonl` has 198 records (some
citation records are skip/no_reqs markers and pass through without
producing a formal REQ). `pass_c_formal_use_cases.jsonl` has 15
records (UC-PHASE3-01..UC-PHASE3-15). All REQ IDs are
deterministically zero-padded; no gaps in the sequence. Resume
produced a logically-equivalent artifact set.

## Kill 4 — Pass D atomic write (degenerate kill semantics)

**Architectural note:** Pass D's `run_pass_d` reads all upstream
artifacts in memory, builds the audit / section coverage / council
inbox dicts, and writes three JSON files via
`_write_json_atomic` (tmp + os.replace) at the end. There is no
incremental cursor advance during the build — `progress.cursor`
goes from 0 (status=running at start) to N (status=complete at
end) in one step, where N is the count of audit decisions.

**Implication for mid-pass kill:**

- A SIGKILL **before** the three `_write_json_atomic` calls
  produces no on-disk artifact (the build is in-memory; the kill
  loses everything). The next run starts from cursor=0 and rebuilds
  identically — there is no "resume" because there is no partial
  state.
- A SIGKILL **after** the writes produces complete output. There is
  no partial state to resume from; the next run would read the
  complete artifacts and exit immediately.

**Conclusion:** Pass D's atomicity by design means mid-pass kill
semantics are degenerate. The `verify_and_resume` machinery is not
exercised because there is no JSONL with a per-record cursor (Pass
D writes whole-file JSON, not append-only JSONL). This is a
feature of Pass D's architecture, not a defect: an audit is a
read-then-summarize operation, not a per-record stream, so atomic
write is the right choice.

**Validation in lieu of a real kill:** the unit test
`test_skill_derivation_pass_d.py` covers the atomic write contract:
the audit / coverage / inbox files are either complete or absent,
never partial. Fixture-driven tests cover the disposition logic,
section coverage, completeness gap detection, council inbox
shape, and B4 upstream-status gate. These are the resumability
guarantees Pass D provides; mid-pass cursor-rollback is not
applicable.

## Downstream-refuses verification (B4 gate experiment)

**Setup:** mirrored the QPB live run output to a temp directory at
`/tmp/qpb_downstream_test/`, then deliberately corrupted the
upstream-status file:

```
$ jq '.status = "running"' \
    /tmp/qpb_downstream_test/quality/phase3/pass_a_progress.json \
    > /tmp/qpb_downstream_test/quality/phase3/pass_a_progress.json.new
$ mv .../pass_a_progress.json.new .../pass_a_progress.json
```

Then deleted `pass_b_progress.json` and ran `python3 -m
bin.skill_derivation /tmp/qpb_downstream_test --pass B --runner
claude`.

**Result:** Pass B raised `UpstreamIncompleteError` with the
expected diagnostic:

```
bin.skill_derivation.protocol.UpstreamIncompleteError: Pass B
refused to start: upstream progress at
/private/tmp/qpb_downstream_test/quality/phase3/pass_a_progress.json
reports status='running' (cursor=125, total=125). The upstream
pass must reach status='complete' before downstream may consume
its artifact. Resume or re-run the upstream pass first.
```

The B4 gate enforces the "downstream refuses to start unless
upstream is complete" rule from the Implementation Plan exactly as
designed. The diagnostic names the downstream pass (`Pass B`),
the upstream progress file path, the upstream's reported status
and cursor/total, and the recovery instruction.

**Same gate applies symmetrically:** Pass C refuses unless Pass B
status=complete; Pass D refuses unless Pass C status=complete.
Tested in `test_skill_derivation_pass_b.py::UpstreamCompletionGateTests`,
`test_skill_derivation_pass_c.py::B4UpstreamGateTests`, and
`test_skill_derivation_pass_d.py::B4UpstreamGateTests` (all green
at the test counts in PHASE3B_SUMMARY.md item 2).

The CLI-level enforcement is also tested in
`bin/tests/test_skill_derivation_main.py::PassAllIntegrationTests`
(commit 1/4):
- `test_pass_b_refuses_when_pass_a_incomplete`
- `test_pass_c_refuses_when_pass_b_incomplete`

## Aggregate result

The per-pass execution protocol's atomic-append + atomic-progress-
write + verify-and-roll-back contract holds on real QPB data.
Three live mid-pass kills (Pass A, B, C) plus one architecture-
documented atomicity (Pass D) plus the downstream-refuses
experiment together demonstrate that the four-pass pipeline is
resumable from any non-Pass-D mid-execution point and refuses to
silently consume incomplete upstream artifacts.

The truncation in commit 2/4 does not affect the resumability
result: the mechanism by which Pass B was finalized at cursor=200
(rather than 1392) is independent of the resume mechanics. The
truncation was a deliberate operator decision motivated by Pass
B's wall-clock; the resume would have continued to cursor=1392
under a longer wall-clock budget.
