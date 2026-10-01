# Submission protocol: one bug at a time, reviewed by Andrew

Adopted 2026-10-01. Applies to **every** open-source bug from this project: PRs, issues and mailing-list patches.

## Why

Volume pulls toward batching: "send these two today, these three tomorrow." That is the wrong default. Every submission has to be right, documented, and reviewed by Andrew before it goes out, however many are waiting. There is no rush.

## Before a submission (Claude)

Present **one** bug at a time. In the chat, give a brief explanation:

1. **The project:** what it does, in a sentence or two.
2. **The bug:** the expected behaviour and where that expectation comes from (doc, spec, RFC, maintainer statement), what actually happens, and why it went unnoticed.
3. **The fix:** how it works, with the diff shown.
4. **The regression test:**
   - how it was tested: the new test fails without the fix, passes with it, and fails again when the fix is reverted;
   - the full-suite result.
5. **Knock-on effects:**
   - who calls the changed code;
   - a before/after comparison on ordinary inputs, freshly run, showing nothing else changed;
   - any behaviour change for existing users. Andrew's rule: a fix with bad side effects is not submitted.
6. **Things to know:** related open PRs or issues, CLA or contribution-process steps, likely maintainer pushback.

Write the same explanation into `evidence/<slug>/REVIEW.md`. Add these sections there too:

- review history (confirmer, panel, re-review, with links);
- an upstream check: the default branch head, and whether the patch applies cleanly;
- the exact PR or issue text that will be submitted;
- the command to submit;
- an empty **Submission record** section.

The chat explanation and REVIEW.md must agree. Re-run the knock-on check at presentation time; don't rely only on older logs.

Then stop. Don't propose a schedule, don't queue the next bug in the same message, and don't group several bugs into one presentation.

## Submission (Andrew)

Andrew reads the explanation and the diff. If he's satisfied, he runs the submit script, which opens a **draft**, and pastes the output back.

## After a submission (Claude)

1. Verify on GitHub, or the list archive, that it landed. The PR page must show the title and body. The diff must match the evidence patch; compare blob hashes.
2. Fill in the **Submission record** in `REVIEW.md`:
   - date;
   - PR or issue link and number;
   - head branch and commit;
   - what was verified;
   - bot actions (CLA, CI gates);
   - what remains on Andrew's side (sign a CLA, mark ready);
   - maintainer responses.
3. Update the status line at the top of `REVIEW.md`.
4. Later maintainer responses, revisions, merges or closures are appended to the same record.

## Before any of this

Unchanged from before: confirmation by an independent confirmer, a minimal fix with red/green/revert, and the full review panel plus a re-review of any code revision. Only bugs that pass all of that get presented.

## Reference example

`evidence/cobra-suggest-runes/REVIEW.md` (spf13/cobra#2514) is the first submission made under this protocol.
