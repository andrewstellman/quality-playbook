# c2-changelog: sentence-by-sentence check of the changelog and notes

Line refs are v7.4-rc3 unless marked "branch" (the patched tree, +20 lines in util.c, 1 in iscsi_target.c).

## 1. Verdict
SEND AFTER CHANGES. The code claims check out; three sentences overclaim or are incomplete (connection-close on iSER, "can still match these", the Reject/NOP-In reachability), Cc: stable doesn't meet the stable rules as written, and one line is over 75 columns.

## 2. Findings (most severe first)

### F1 (should-fix) "A NOP-Out that names another command's TTT now closes the connection" is false for iSER
- TCP: iscsi_target_rx_opcode() NOOP_OUT case -> iscsit_handle_nop_out() -> `return iscsit_process_nop_out()` (iscsi_target.c:1941) -> -EINVAL (:1825-1826 in rc3 numbering of the lookup NULL check). rx loop (iscsi_target.c:4119-4121) does `ret = iscsi_target_rx_opcode(); if (ret < 0) break;`, then rx thread calls iscsit_take_action_for_connection_exit(). So TCP closes. Confirmed.
- iSER: ib_isert.c:1389 `isert_rx_opcode(...)` in isert_recv_done() discards the return value (isert_rx_opcode returns `ret`, init -EINVAL, :1226-1308). No reinstatement on -EINVAL. isert_handle_nop_out (:1196) is just `return iscsit_process_nop_out()`. So on iSER the NOP-Out is silently dropped and the connection stays up. Also isert allocates `cmd` for every NOP-Out (:1262), so the cmd isn't freed on that path either. That predates this patch and is the same for the "unknown TTT" case the sentence cites.
- Fix: say "on iSCSI/TCP", or drop the sentence (see edits). The "as one naming an unknown TTT already does" half is true for exactly the same transports.

### F2 (should-fix) Cc: stable doesn't meet stable-kernel-rules.rst as written
- Rules (stable-kernel-rules.rst, "It must either fix a real bug that bothers people"; "No 'This could be a problem...' type of things like a 'theoretical race condition', unless an explanation of how the bug can be exploited is also provided").
- The changelog itself says the oops is from reading and not reproduced, and the trigger is an authenticated initiator sending a NOP-Out with a TTT it must guess (the READ case is guessable on a fresh session, but still needs a deliberately wrong PDU). No user report. Size (23 lines) and Fixes: tag are fine.
- Fix: drop `Cc: stable@vger.kernel.org`. Keep Fixes:. Maintainer or stable can pick it up later; add the tag back if it's reproduced.

### F3 (should-fix) "a Reject with TTT 0 can be ahead of a NOP-In that also got TTT 0 on a fresh session": true as code, but reachability is narrower than the sentence suggests
- Code facts, all confirmed: iscsit_allocate_cmd() memsets the cmd (util.c, iscsit_allocate_cmd) and iscsit_add_reject() (iscsi_target.c:787-815) never sets targ_xfer_tag; it list_add_tails the reject on conn_cmd_list (:806-808). The first iscsit_add_nopin(want_response=1) takes session_get_next_ttt() (util.c branch :865-866) = 0 on a fresh session. lookup is first-match in list order (util.c:384-396).
- Reachability: iscsit_add_reject() always returns -1. Callers on the RX path whose return is propagated close the connection (rx loop break). The Rejects that leave the connection up are the ones where the caller maps the failure to 0: NOP-Out setup failures (iscsit_handle_nop_out :1858-1860 `if (ret < 0) return 0`; F bit clear :1725-1727, reserved ITT without I bit :1735-1738, oversize :1746-1751), Data-Out oversize (iscsit_handle_data_out :1706-1707 returns 0 on rc<0; reject at :1577). Also Reject-from-cmd (iscsit_add_reject_cmd, :864) used for bad SCSI CDB headers, which run before targ_xfer_tag is assigned at :1170, so they also carry TTT 0 (I did not trace that every such caller returns 0 to the RX loop).
- So the ordering needs: an earlier protocol-violating PDU that the target rejects but survives, no READ/Text/R2T before the first want-response NOP-In, and the Reject's StatSN not yet acked (rejects stay on the list until ExpStatSN acks them). That is not a "correct initiator" scenario in the usual sense. README says "drop a correct initiator's reply"; that is an overstatement. The reason to prefer the opcode-aware lookup over the earlier proposal still stands (it's a pure correctness gain, no behaviour risk), just not as a real-world failure.
- Fix: say it plainly and shorter, e.g. "Checking the opcode after the existing lookup isn't enough: the first match can be a Reject, which also has TTT 0." Drop "fresh session" and the implied likelihood. Alternatively keep the sentence but add "after a rejected PDU".

### F4 (should-fix) "the lookup can still match these" and "fixed this" are vague
- 9547308bda29 diff (read): in iscsit_setup_scsi_cmd, `if (READ) next_ttt; else if (WRITE) 0xFFFFFFFF` became `if (READ) next_ttt; else 0xFFFFFFFF`. Commit message: TUR left at TTT 0, matched by the unsolicited NOP-In's reply (TTT 0), TUR queued for removal twice. So the sentence "fixed this for non-READ SCSI commands by giving them a TTT of 0xffffffff" is accurate, but "this" = "NOP-Out matching a non-NOP-In command at TTT 0", which the reader has to infer, and "these" in the next clause is unclear.
- Fix: name them (see edits).

### F5 (nit) Changelog line over 75 columns
- Patch line 44: `Commit 9547308bda29 ("target/iscsi: Fix double free of a TUR followed by a solicited NOPOUT") fixed this ...` the first line is 78 chars. submitting-patches.rst says wrap at 75. Other long lines are in the diff (fine).

### F6 (nit) "READs take theirs from the same per-session counter, as do Text commands with a pending continuation, and Rejects allocated by iscsit_add_reject() keep the 0 ..." is a run-on mixing two different mechanisms
- True on each part: READ iscsi_target.c:1170 (session_get_next_ttt); Text continuation :3506-3507 (only when TEXT_CONTINUE and TTT still 0xFFFFFFFF); Reject keeps 0 as above. Text cmds do sit on conn_cmd_list (allocated via iscsit_allocate_cmd in rx_opcode TEXT case). R2T TTTs also come from the counter but live in the r2t struct, not on the cmd, so they are not matched; the sentence correctly omits them.
- Fix: split, and say Rejects "have TTT 0".

### F7 (nit) Subject
- "scsi: target: iscsi: Match NOP-Out replies only against NOP-Ins" is 63 chars, correct prefix (git log -- drivers/target/iscsi: 16 "scsi: target: iscsi:" vs 6 "scsi: target:"). Accurate. Fine.

### F8 (nit) Notes under `---`: "applies cleanly to 7.4/scsi-fixes and 7.5/scsi-staging" and "no new warnings" are fine but the sentence "returns the NOP-In ahead of a Reject" is OK. Consider cutting the whole build/apply detail to one line; maintainers don't need the branch names.

## 3. Changelog edits (before -> after)

E1 (F1). Before:
"A NOP-Out that names another command's TTT now closes the connection, as one naming an unknown TTT already does."
After:
"A NOP-Out that names another command's TTT is now treated like one naming an unknown TTT (on iSCSI/TCP that closes the connection)."
Or cut it; it is not needed to justify the change.

E2 (F3). Before:
"Matching on the opcode after the existing lookup isn't enough, because a Reject with TTT 0 can be ahead of a NOP-In that also got TTT 0 on a fresh session."
After:
"Checking the opcode after the existing lookup isn't enough, because the first match can be a Reject (TTT 0) ahead of a NOP-In that also has TTT 0."

E3 (F4). Before:
"Commit 9547308bda29 ("target/iscsi: Fix double free of a TUR followed by a solicited
NOPOUT") fixed this for non-READ SCSI commands by giving them
a TTT of 0xffffffff, but the lookup can still match these. The counter
starts at 0 for each session, so the TTT of a session's first READ is
known in advance."
After:
"Commit 9547308bda29 ("target/iscsi: Fix double free of a TUR followed by
a solicited NOPOUT") fixed the same lookup for non-READ SCSI commands by
giving them TTT 0xffffffff. READs, Texts and Rejects can still be
matched. The counter starts at 0 for each session, so the TTT of a
session's first READ is predictable."
(wraps under 75; "known in advance" -> "predictable" is plainer)

E4 (F6). Before:
"NOP-Ins aren't the only commands with a TTT. READs take theirs from the
same per-session counter, as do Text commands with a pending
continuation, and Rejects allocated by iscsit_add_reject() keep the 0
that iscsit_allocate_cmd() leaves in targ_xfer_tag."
After:
"NOP-Ins aren't the only commands on that list with a TTT. READs and Text
commands with a pending continuation take theirs from the same
per-session counter. Rejects from iscsit_add_reject() have TTT 0."

E5 (F2). Delete the line `Cc: stable@vger.kernel.org`.

E6 (confidence, optional). Before: "From reading the code, target_complete_ok_work() then dereferences the NULL se_lun when the READ completes. I haven't reproduced this on a running kernel."
After (state what is read and why the command survives): "From reading the code, target_complete_ok_work() then dereferences the NULL se_lun when the READ completes (iscsit holds a second reference, so the se_cmd is still there). I haven't reproduced this on a running kernel." Confidence is right as is; the parenthetical is only worth adding if it fits the short-changelog goal. It pre-empts the reviewer question "isn't it a use-after-free instead?".

## 4. Checked and found correct
- "returns the first command on conn_cmd_list with that tag whatever its opcode": util.c:384-396, compares only targ_xfer_tag, first match under cmd_lock.
- "sets that command to ISTATE_REMOVE and queues it for the TX thread": iscsi_target.c:1830-1831 (`cmd_p->i_state = ISTATE_REMOVE; iscsit_add_cmd_to_immediate_queue`), no opcode/state check (:1823-1826). TX side: iscsit_immediate_queue() case ISTATE_REMOVE (iscsi_target.c:3697-3702 rc3): list_del_init, then iscsit_free_cmd(cmd, false).
- "frees it with transport_generic_free_cmd() which doesn't wait for the backend": iscsit_free_cmd (util.c:~700-717) calls transport_generic_free_cmd(se_cmd, shutdown=false); wait_for_tasks=false skips target_wait_free_cmd (target_core_transport.c, transport_generic_free_cmd).
- "sets se_cmd->se_lun to NULL": transport_generic_free_cmd -> (SCF_SE_LUN_CMD && se_lun) transport_lun_remove_cmd() -> `cmd->se_lun = NULL` (also drops lun_ref early).
- se_cmd survives the free: iscsit takes the second ack ref (iscsi_target.c:1206 target_get_sess_cmd(&cmd->se_cmd, true)), so free_cmd's put does not hit target_release_cmd_kref. So it is a NULL deref, not UAF of se_cmd.
- Deref reached for READ with good status: target_complete_ok_work(), DMA_FROM_DEVICE case: scsi_status==0 so no goto queue_status, then `cmd->se_lun->lun_stats` (unconditional se_lun deref). Earlier code only touches se_dev (transport_complete_task_attr, dev_qf_count); SCF_TRANSPORT_TASK_SENSE and transport_complete_callback are not set for a plain READ.
- Conditions that would stop it: target_complete_cmd_with_sense() returns early if target_cmd_interrupted() (CMD_T_ABORTED or CMD_T_STOP). Neither is set by iscsit_free_cmd(false). They'd only be set if an abort/TMR or connection shutdown races in, so the deref isn't guaranteed, but is reachable. "From reading the code ... I haven't reproduced" is the right confidence. (If the backend completes before the NOP-Out is processed, the READ is already past this point; the window is "READ still in backend", which the changelog states.)
- "The counter starts at 0 for each session": session struct (iscsi_target_core.h:637) zeroed by kzalloc_obj (iscsi_target_login.c:222), no other initialiser (grep of targ_xfer_tag in login.c: none); session_get_next_ttt (core.h:897-908) post-increments, skips 0xFFFFFFFF. "predictable" holds.
- "READs take theirs from the same per-session counter": iscsi_target.c:1169-1172.
- "Text commands with a pending continuation": iscsi_target.c:3506-3507.
- 9547308bda29 content and date (2015, v4.2) matches README; claim about it is accurate, only vague (F4).
- Unsolicited NOP-In gets TTT from the counter: util.c branch :865-866 (want_response only).
- "iscsit_find_cmd_from_ttt() is unchanged for its other caller, Data ACK SNACK handling": only other caller is iscsit_handle_data_ack, iscsi_target_erl1.c:539. No callers outside drivers/target/iscsi.
- Fixes: e48354ce078c is right. It contains the unchecked `iscsit_find_cmd_from_ttt(conn, hdr->ttt)` followed by ISTATE_REMOVE (checked via git show e48354ce078c) and READ TTTs from the counter (:986-988 there). 778de368964c is only the 2013 refactor that moved the code (blame target); citing it would understate the age. 9547308bda29 is a partial fix, not the introducer.
- Subject prefix and length (F7).
- Tool disclosure in changelog satisfies generated-content.rst ("if a tool was used to find a problem ... noted in the changelog"; "What tools were used" and how tested). Not-tested statement is explicit ("I haven't reproduced", "Not yet run on a kernel"), meeting coding-assistants.rst step 8. No Signed-off-by from the AI: correct (expected).
- No em dashes in the patch (grep count 0).
- Diff: new helper mirrors the old one, spin_unlock_bh before return, pr_err on miss; header prototype matches style of neighbours.
- "A second NOP-Out answering the same NOP-In is still accepted and queues it for removal twice": after the patch the first NOP-Out sets ISTATE_REMOVE and the TX thread list_del_inits and frees, so the second lookup normally fails (NULL -> -EINVAL) once the TX thread has run; but if both arrive before the TX thread processes the first, both match and ISTATE_REMOVE is queued twice. The notes sentence is true in that window but "is still accepted" is unqualified. Suggest "can still be accepted if it arrives before the first has been freed." (minor, in the notes, not the changelog).

## 5. Could not check
- Actual runtime behaviour (instructed not to boot or send PDUs).
- Whether "Claude Opus 5.5" is the exact model name/version in the QPB run record (not in the tree).
- Whether every Reject-from-cmd caller (iscsi_target.c:1014-1233) returns 0 to the RX loop (affects how wide F3's reachability is); only traced the NOP-Out and Data-Out paths.
- target-devel/linux-scsi list history for prior fixes.
- Whether the 15 s nopin timeout plan in the README is sufficient as a test; out of scope.
