# v3 (29 September 2026): minimal commit

Andrew asked for minimal commits. Two cuts, both suggested by reviewer O5 in round 2
(`evidence/review-2026-09-28-v2/O5-slop.md`) and left "contested" by the synthesis:

1. Error message: dropped the `bad_lengths[:5]` truncation and the "(and N more)" suffix.
   Now one f-string that lists the offending lengths and says what to set.
2. Dropped `test_split_batch_by_cp_rank_thd_covers_all_tokens`. It passed before and after
   the fix (a control), so it does not demonstrate this change.

Kept: the guard itself, the `test_split_batch_by_cp_rank_thd_non_divisible` test (regex
`\[10\] must be divisible by 4` still matches), the eight regenerated copies.

Re-verified in a fresh sandbox (CPU torch 2.14, Python 3.10) with the same
verbatim-extraction harness as v2 (`harness/run_extracted.py`, control test removed from
its list): base source + v3 tests: 1 failed (`DID NOT RAISE ValueError`), 4 passed
(`red.log`); v3 source + v3 tests: 5 passed (`green.log`). `check_copied_files.py`
passes. ruff clean on the changed lines (two RUF059 warnings in the file are pre-existing
on the base commit).

Diff: 10 files, +97 −9 (v2 was +115 −9). PR body unchanged: it never
described the control test or the truncation.
