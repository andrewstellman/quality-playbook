# About this folder

This is the record of the Quality Playbook v1.2.15 runs against gson on 2026-04-02 and 2026-04-03, the experiment that found the duplicate-key bug in `MapTypeAdapterFactory`. It predates the `evidence/` folder and the review step that later runs went through before submission, so it has no `REVIEW.md`, no panel round and no submission log. The run files were recovered from a Time Machine backup on 2026-06-14 (`repos/recovered-timemachine-2026-06-14/gson-1.2.15/` and `gson-naive/`, not tracked in git) and copied here on 2026-10-20 as they were written during the runs. Nothing in them was edited; `STATUS.md` and this note are the only files written after the runs.

What is here:

- `EXPERIMENT.md` describes the experiment: a baseline run with only in-repo documentation (Condition A) against a run whose requirement derivation also read a corpus of retrieved documentation (Condition B). Its "Confirmed Bug" section records the finding, the reproduction and the root cause.
- `GSON_BUG_ISSUE.md` is the bug report as drafted, and `GsonDuplicateKeyBug.java` is the standalone reproducer.
- `quality_baseline/` is the Condition A output (2026-04-02, model gpt-5.4), `quality_v2_77req/` and `quality_v3_93req/` are the Condition B output after each requirements pass, and `quality/` holds the final requirements, contracts, coverage matrix and completeness report. The code reviews that report the bug are `quality_v2_77req/code_reviews/2026-04-03-head-review.md` and `quality_v3_93req/code_reviews/2026-04-03-head-review.md` (first bullet under `MapTypeAdapterFactory.java`, lines 191-206); the baseline code review and the auditor-2 spec audits also flag it.
- `retrieved_documentation/` is the 24-file documentation corpus Condition B read (official docs, 13 GitHub issues, 4 community tutorials), each with its source URL and retrieval date in front matter; `INDEX.md` lists them.
- `run_playbook_with_docs.sh` and `playbook_progress.txt` are the Condition B pipeline script and the runner's log for both runs.
- `control-adversarial-review/GSON_REVIEW_FINDINGS.md` is a separate adversarial code review of gson made without the playbook (from the `gson-naive` folder of the same backup), kept as a point of comparison. It does not report this bug; its FINDING-3 is about duplicate names being handled differently across APIs.

One correction to the record: `EXPERIMENT.md` says the fix was filed as PR #2999. The PR that carries the fix is google/gson#3006 (opened 2026-04-03, merged 2026-04-05); #2999 is an unrelated pull request by another author. `EXPERIMENT.md` also says the baseline run did not find the bug; `quality_baseline/code_reviews/code-review-2026-04-03-copilot.md` and `quality_baseline/spec_audits/2026-04-03-auditor2.md` do report it. The file is kept as written.

Not here: the gson source tree the runs read, and the `metrics/` benchmark module, which is part of gson itself.
