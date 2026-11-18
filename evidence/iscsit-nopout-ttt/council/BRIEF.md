# Council brief: review of one Linux kernel patch (iSCSI target, NOP-Out TTT lookup)

You are one of five independent reviewers. You haven't seen how this patch was written, and you won't see the other reviewers' work. Review it the way an experienced Linux SCSI/target reviewer would. Verify every claim yourself against the source. Don't take the changelog's word for anything.

## The patch

`/mnt/user-data/outputs/iscsit-nopout-ttt/0001-scsi-target-iscsi-Match-NOP-Out-replies-only-against.patch`

It's an unsigned draft. The submitter (Andrew Stellman) adds his own Signed-off-by; the kernel's AI rules forbid an AI adding it, so a missing Signed-off-by is expected and isn't a finding. Nothing has been sent.

Supporting checks the author already ran are in `/mnt/user-data/outputs/iscsit-nopout-ttt/checks/` (checkpatch output, W=1 build log, apply check against mkp/scsi.git, history check, a userspace test of the new lookup). The README next to the patch summarizes them. Treat these as claims to check, not facts.

## The source

`/home/claude/k/linux` is a clone of torvalds/linux (full history, blobs fetched on demand). Branch `iscsit-nopout-ttt` is the patch applied on `v7.4-rc3` (aebb7274476403040d582c61478df8f4a7bf9cd3). Remote `mkp` has `mkp/7.4/scsi-fixes` and `mkp/7.5/scsi-staging` (Martin K. Petersen's SCSI tree; for-next = 7.5/scsi-staging).

**Rules for the shared tree:** other reviewers use it at the same time. Read-only commands only (`git show`, `git log`, `git blame`, `grep`, reading files). Never `checkout`, `commit`, `reset`, `stash`, `am` or edit files in `/home/claude/k/linux`. If you need a modified copy or a build, make your own under `/home/claude/k/council/<your-name>/` (e.g. `git -C /home/claude/k/linux worktree add /home/claude/k/council/<your-name>/tree <ref>`, then build with your own `O=` directory, copying `/home/claude/k/out/.config` as a starting config). The machine has 2 CPUs, so build only what you need (single objects or `drivers/target/iscsi/`).

Kernel process docs are in the tree: `Documentation/process/submitting-patches.rst`, `coding-assistants.rst`, `generated-content.rst`, `security-bugs.rst`, `threat-model.rst`, `stable-kernel-rules.rst`, `coding-style.rst`.

## Background (context, not conclusions)

An LLM-driven review (Quality Playbook) flagged that `iscsit_process_nop_out()` handles a NOP-Out carrying a TTT by taking the first command on `conn_cmd_list` with that TTT, with no opcode or state check, setting it to ISTATE_REMOVE and queuing it for the TX thread to free. Earlier reviewers proposed, as a fix, keeping the existing lookup and adding `cmd_p->iscsi_opcode != ISCSI_OP_NOOP_IN || cmd_p->i_state == ISTATE_REMOVE` to the reject condition. This patch takes a different approach (a NOP-In-only lookup) and its changelog says why. Nothing has been reproduced on a running kernel. The double reply (two NOP-Outs for one NOP-In) is deliberately left for a separate change.

The submitter's own constraints for the changelog: short and plain (maintainers shouldn't hit tl;dr), only enough to explain the problem, plus a line saying it was found by Quality Playbook and reviewed by him. No em dashes. No claims stated as observed that weren't observed.

## Hard limits

- Don't boot anything, don't write or run anything that sends iSCSI PDUs to a target, and don't write a crash reproducer. Code reading, builds and userspace tests only.
- Don't post or send anything anywhere.
- Don't contact anyone.

## Output

Write your report to `/home/claude/k/council/<your-name>.md`, then reply with a 3-line summary (verdict plus your top finding). Use this structure:

1. **Verdict:** SEND AS IS / SEND AFTER CHANGES / DO NOT SEND, with one sentence why.
2. **Findings**, most severe first. Each with: severity (blocker / should-fix / nit), what's wrong, evidence (file:line in v7.4-rc3 or the patch, commands you ran and their output), and the concrete fix.
3. **Changelog edits**, if any, as before → after text for each (quote the exact current text).
4. **What you checked and found correct** (one line each), so the synthesis knows what was covered.
5. **What you couldn't check.**

Be specific and terse. If you think something is fine, say so in one line rather than padding. Don't invent problems to have something to report.
