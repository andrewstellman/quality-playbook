# Review panel: nvmet CRTO-from-CAP patch

Three reviewers, three charters, run in parallel as independent sub-agents with fresh
context. Each reads the evidence folder, not the chat that produced it, and writes its
verdict to its own file in this directory. A verdict is one of SHIP, FIX-REQUIRED, or
CONCERN, per question, plus an overall verdict, with every claim tied to a file and line
the reviewer read. Same shape as `../../nvmet-anagrpid/review/PANEL.md`; the method is in
`../../README.md`.

Common instructions given to every reviewer:

> You are reviewing evidence for a Linux kernel patch before it is sent to the linux-nvme
> mailing list. Everything is under `/Users/andrewstellman/Documents/QPB/evidence/nvmet-crto/`.
> Read `README.md`, `RUNBOOK.md`, `RUN-REPORT.md`, `cc-red-base.txt`, `cc-green-crto.txt`,
> the `DRAFT-0001-*.patch` file, `repro-bug001-crto.sh`, and `build-kernel.sh`. The sibling
> bug's evidence, already sent to the list, is in `../nvmet-anagrpid/` (its two reproducers
> are the cross-check in this run). The kernel source at the snapshot commit is at
> `/Users/andrewstellman/Documents/QPB/repos/linux/nvme-target/` (target side only; there is
> no `drivers/nvme/host/` there) and a full-history blobless clone is at `~/src/linux`,
> currently on branch `qpb/nvmet-crto` with the draft commit on top of the snapshot. The
> NVMe spec text is `.../nvme-target/reference_docs/cite/nvme-base-2.4.txt`.
> Work from the raw captures and the source, not from the summaries. Quote what you read.
> Be adversarial: your job is to find the reason this should not be sent. If you find
> none after looking, say what you looked for. Write your full review to the file named
> in your charter. Do not modify any other file.

## Reviewer A: falsify the red/green (Opus)

Charter: try to show that the GREEN result does not prove the patch fixes the bug.

Questions:
1. Is the GREEN kernel different from the RED kernel in any way other than the patch?
   Check `build-kernel.sh`: does it reset the tree before applying? Same config? Could
   the suffix change, the `/boot` cleanup the autopilot did (RUN-REPORT "Environment
   fixes"), or a rebuild artifact explain the result?
2. Does the cross-check hold? On the patched kernel the two ANAGRPID reproducers must be
   RED with output identical to the base run apart from the kernel string. Compare the
   captures line by line.
3. Could `repro-bug001-crto.sh` produce GREEN on a buggy kernel or RED on a fixed one?
   Read the `sed` parse of `value:`, the `(( CAP >> 24 ) & 0xff)` and `CRTO & 0xffff`
   arithmetic, the controller-name grep, and the exit paths. Is there any input that makes
   it print GREEN with CRTO still 0, or UNEXPECTED on a correct kernel?
4. Is the value read at offset 0x68 actually CRTO as served by `nvmet_execute_prop_get()`,
   or could nvme-cli, the fabrics host, or the TCP transport be substituting or caching
   a value? Trace the path from `nvme get-property` to the target's `case NVME_REG_CRTO`.
5. Is the claim "CSTS defines only bits 6:0 and nvmet writes only RDY, CFS and SHST"
   true at the snapshot? Grep every write to `ctrl->csts` in the target tree.

Write to `A-falsify-redgreen.md`.

## Reviewer B: patch minimality and kernel style (Sonnet)

Charter: is this the smallest correct change, written the way this subsystem writes code?

Questions:
1. Is `NVME_CAP_TIMEOUT(ctrl->cap)` the right expression? CRTO is a 32-bit register with
   CRWMT in bits 15:0 and CRIMT in bits 31:16 (spec Figure 57). `NVME_CAP_TIMEOUT()`
   yields an 8-bit value that lands in CRWMT with CRIMT = 0. Is that correct for a
   controller that does not set CAP.CRMS, and does anything in the host or the spec
   require CRIMT to be non-zero here?
2. Is there a smaller or more idiomatic fix, or a better one (for example, a dedicated
   `ctrl->crto` field, or deriving CRTO where CAP is built in `nvmet_init_cap()`)? If an
   alternative is better, say why; if the submitted form is better, say why.
3. Does the patch touch every site that has the bug and no other? grep the target for
   `NVME_REG_CRTO`, `NVME_CAP_TIMEOUT`, and `csts`.
4. Style: `checkpatch.pl --strict` output is in `RUN-REPORT.md`; does anything else in the
   diff deviate from the surrounding code?
5. Is there a case where the old code was correct and the new code is not?

Write to `B-patch-minimality.md`.

## Reviewer C: commit message and email against the evidence (Sonnet)

Charter: every sentence in the draft patch's commit message must be traceable to a file
in the evidence folder or to the source, and the email must be free of the mistakes made
on the previous patches from this project.

Checklist:
- Every function, macro, field, and register name in the message must exist in the
  snapshot source with exactly that name. Grep each one. A name that does not exist is
  FIX-REQUIRED.
- `Fixes:` must name the commit that introduced the defect, not one that moved the line.
  Verify the blame chain in `RUN-REPORT.md` step 3 yourself in `~/src/linux`, and state
  whether the reasoning holds. Check the tag format: 12-character hash, subject in
  parentheses and double quotes.
- `Assisted-by:` form. Survey what has been merged: in `~/src/linux`,
  `git log origin/master --grep='^Assisted-by:' -40 --format='%h %s%n  %(trailers:key=Assisted-by,valueonly)'`,
  and the same restricted to `-- drivers/nvme`. The trailer must match merged practice
  and name the actual model and agent. The body sentence naming the tool and its URL
  stays. Compare with the ANAGRPID patch as sent (`../nvmet-anagrpid/0001-*.patch`).
- The "Tested on" paragraph must match the raw captures: kernel release strings, the
  before values, the after values, the transport, the tool.
- The spec quotation must match `nvme-base-2.4.txt` verbatim, and the figure reference
  must be right. Find the lines yourself (Figure 36 is CAP; Figure 57 is CRTO).
- The host paragraph ("The Linux host reads CRTO only when CAP.CRMS.CRWMS is set"): the
  autopilot checked `drivers/nvme/host/core.c` at the snapshot (RUN-REPORT claim 3).
  Re-derive it: `git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c:drivers/nvme/host/core.c | grep -n -B4 -A10 NVME_REG_CRTO`.
  Is "Linux initiators have not seen the wrong value" an over-claim? Consider
  out-of-tree or non-Linux initiators and whether the sentence needs them.
- Standalone patch, not a series; `base-commit` line present; no `Signed-off-by` in the
  draft (the operator adds it); author name and email consistent.
- Subject line: correct prefix for `drivers/nvme/target` (check
  `git log --oneline -30 4d7d9486 -- drivers/nvme/target/fabrics-cmd.c` in `~/src/linux`),
  under 75 characters, imperative.
- Every body line 75 columns or fewer.

Also: is anything in the message an over-claim or an under-claim? Is "Advertising CRWMS
is a separate change" enough context for a maintainer, or should the message say what a
host would do differently once CRWMS is advertised?

Write to `C-message-and-email.md`.

## Synthesis

After all three files exist, the orchestrating session reads them and writes
`SYNTHESIS.md`: per-question verdicts by reviewer, disagreements, the overall verdict,
and the exact list of changes required before sending, if any.
