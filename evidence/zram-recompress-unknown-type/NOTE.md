# About this folder

This is the record of the Quality Playbook v1.3.7 run against the zram driver on 2026-04-06, the run that found the `recompress_store()` bug. It predates the `evidence/` folder and the review step that later runs went through before submission, so it has no `REVIEW.md`, no panel round and no submission log. The run files were recovered from a Time Machine backup on 2026-06-14 (`repos/recovered-timemachine-2026-06-14/zram-1.3.7/`, not tracked in git) and copied here on 2026-10-20 as they were written during the run. Nothing in them was edited; `STATUS.md` and this note are the only files written after the run.

What is here:

- `quality/` is the playbook output: the requirements, contracts and coverage matrix, the code review (`code_reviews/2026-04-06-code-review.md`), the three spec audits and their triage (`spec_audits/2026-04-06-triage.md`, where the bug is finding SA-004, "1/3 present + verification probe, CONFIRMED, real code bug"), and `test_regression.py`, where the triage added `test_recompress_store_rejects_unknown_type_values`.
- `test_zram_bugs.py` is the standalone red/green test file for the confirmed bugs (`test_bug_4_recompress_store_rejects_unknown_type_values`).
- `control_prompts/playbook_run.output.txt` is the agent's transcript of the run; `runner-20260406-160203.log` and `playbook_progress.txt` are the batch runner's logs (model gpt-5.4, 16:02 to 16:26 local time).
- `docs_gathered/` is the documentation the run was given alongside the source: the zram admin guide, the kernel coding style, the zsmalloc design note and a community development history.
- `AGENTS.md` and `REVIEW_INSTRUCTIONS.md` are the instructions the run and its reviewer were given.

Not here: the zram source tree the run read (a sparse checkout of `drivers/block/zram`), and the patch itself, which is in the lore.kernel.org thread linked from `STATUS.md`.
