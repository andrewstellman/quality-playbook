# Council synthesis: iscsit NOP-Out TTT lookup patch

Five independent reviewers, 2026-11-18. Each read the brief (`BRIEF.md`) and the patch, but saw neither how the patch was made nor each other's reports. c1, c3 and c5 ran on Opus, c2 and c4 on Sonnet. The reports are in this folder.

| Reviewer | Focus | Verdict |
|---|---|---|
| c1-correctness | Code paths, locking, TTT collisions | SEND AFTER CHANGES (one changelog sentence) |
| c2-changelog | Every sentence against v7.4-rc3 | SEND AFTER CHANGES |
| c3-adversarial | Break the patch | SEND AFTER CHANGES (couldn't break the code) |
| c4-maintainer | Martin/Mike's view, conventions | SEND AFTER CHANGES |
| c5-evidence | Re-run every check, design the runtime test | SEND AFTER CHANGES, after the runtime test |

Nobody found a problem with the code. All five changes asked for are to the changelog, the notes, the tags or the testing.

## What the reviewers confirmed

- The new lookup matches exactly the unsolicited want-response NOP-Ins. `ISCSI_OP_NOOP_IN` is set only in `iscsit_add_nopin()` (c1, c3).
- No new race. Locking and pointer lifetime are the same as the old helper, and narrower in effect (c1).
- No sequence from a conforming initiator gets worse with the patch. Nothing other than a NOP-In can reach `ISTATE_REMOVE` through this path after it (c3).
- The NULL `se_lun` claim is right at the stated confidence. iscsit holds a second reference, so the `se_cmd` survives, and `target_complete_ok_work()` reaches `se_lun->lun_stats` for a READ with good status unless an abort or stop intervenes (c1, c2).
- `Fixes: e48354ce078c` is right. 778de368964c is only the refactor (c2).
- What 9547308bda29 changed is described accurately (c1, c2, c4).
- The subject line is fine (c2, c4).
- c5 reran everything:
  - checkpatch (default and `--strict`)
  - gcc and clang W=1 builds
  - `git am` onto both mkp branches
  - checked that `real_lookups.c` is verbatim and that the patch file matches the branch commit
  - the 7 original lookup cases plus 11 new ones, also under ASan/UBSan

  All came out as claimed.

## Findings accepted

1. **"Now closes the connection" is false on iSER** (c1, c2, c3). `isert_recv_done()` discards `isert_rx_opcode()`'s return value (ib_isert.c:1389, checked), so the PDU is dropped and the connection stays up. Reword.
2. **Cc: stable** (c2, c4). stable-kernel-rules.rst excludes theoretical bugs unless the changelog explains how they're triggered, and this one hasn't been reproduced. Drop it and keep `Fixes:`, so stable can still pick it up.
3. **Vague references** (c2, c4). In "fixed this" and "can still match these", the reader has to work out what "this" and "these" refer to.
4. **The Reject-ahead-of-NOP-In reason overstated how likely the case is** (c2, c5). The code fact is right. But the case needs an earlier protocol-violating PDU that the target rejects without closing the connection, no READ before the first ping (open-iscsi's INQUIRY at login takes TTT 0), and the Reject still unacknowledged. A correct initiator won't hit it. That keeps the helper as a correctness choice rather than a fix for an observed failure, and the changelog should say only what's true. The README was wrong to say it would "drop a correct initiator's reply", and Claude said the same thing in chat. Both get corrected.
5. **The notes describe the lookup test backwards** (c5). In the test, the Reject is the one ahead on the list.
6. **The double-reply note states a race as unconditional** (c2, c5). It only happens if the second NOP-Out arrives before the TX thread frees the NOP-In.
7. **A line over 75 columns** (c2). It's the wrapped commit reference.
8. **base-commit** (c4). `mkp/7.4/scsi-fixes` is based on v7.4-rc1 and doesn't contain rc3 (checked). Regenerate with `--base` against that branch. The patch already applies there cleanly.
9. **Run the runtime regression test before sending** (c5, and c4 for stable). The changed line runs on every NOP-In reply on every session. c5's plan, in section 6 of its report, uses only normal initiator traffic. It covers idle pings, pings with READs outstanding, initiator pings on and off, 20 logout/login cycles and two sessions, on the patched kernel and an rc3 baseline, with exact pass criteria. It also needs an arm64 W=1 build, since only x86_64 has been built so far.

## Findings not accepted

- **Add an `Assisted-by:` trailer** (c4, its top finding). Commit 1e035297ffda ("docs: remove Assisted-by references", in v7.4-rc1) removed the tag from coding-assistants.rst and submitting-patches.rst, and dropped checkpatch's handling of it. checkpatch in this tree flags it as non-standard. The Maintainers Summit view recorded there is that tool disclosure goes in the cover letter or the changelog prose, and generated-content.rst still asks for it to be noted in the changelog. So the prose disclosure stays and no trailer is added. c4's evidence was real: both bf33e01f8838 and your own d1512773a0d5 carry the trailer. d1512773a0d5 was committed on 28 Oct, after the removal, so a trailer wouldn't be rejected. It just isn't asked for any more.
- **`%hu` for the CID, to match the neighbouring messages** (c3, c4). checkpatch's default run gives a WARNING for `%hu` in this tree. `%u` is what checkpatch wants, and it's harmless. Kept `%u`.
- **Drop the GitHub URL from the disclosure** (c4). That's your call. Your nvmet v2 kept it, and generated-content.rst asks what tools were used. It's listed as a decision for you below.
- **Subject reword** (c4, optional). The current subject is accurate and 63 characters long. No change.

## Out of scope, for the follow-up or a maintainer's questions

- **The double reply is about as serious as the bug this patch fixes** (c1). A check that `i_state != ISTATE_REMOVE` won't close it, because the TX thread writes `ISTATE_SENT_NOPIN_WANT_RESPONSE` after it transmits and can overwrite REMOVE. Checking that the state equals SENT would break iSER, which never sets it. c1 and c3 both arrived at the same fix: take the NOP-In off `conn_cmd_list` with `list_del_init()` under `cmd_lock` inside the new lookup. c1 notes the cost: a NOP-In taken off early and still on the immediate queue at teardown wouldn't be freed by `iscsit_release_commands_from_conn()`.
- **isert NOP-Out command leak** (c1, c2, c3, from code reading). It's unconfirmed and predates this patch. isert allocates an `iscsit_cmd` for every NOP-Out, and the reply and -EINVAL paths never free it, which would be one session tag per answered ping.
- **Data ACK SNACK** (c3). It still uses the first-match lookup, so it can be pointed at the wrong command, but it frees nothing and only applies at ERL≥1.
- **Recipients** (c4). To: Martin K. Petersen. Cc: linux-scsi, target-devel, Mike Christie, Dmitry Bogdanov, Maurizio Lombardi, John Garry. Skip the stale blamed-fixes addresses. `get_maintainer.pl` output is in `../checks/`.
