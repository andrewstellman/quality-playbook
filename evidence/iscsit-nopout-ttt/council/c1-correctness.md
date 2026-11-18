# c1-correctness: review of 0001-scsi-target-iscsi-Match-NOP-Out-replies-only-against.patch

## 1. Verdict

SEND AFTER CHANGES. The code change is correct and complete for what it claims, and it introduces no new race. One changelog sentence is wrong for iSER and needs rewording before it goes out.

## 2. Findings

### F1 (should-fix, changelog): "now closes the connection" is false on isert

Current text: "A NOP-Out that names another command's TTT now closes the connection, as one naming an unknown TTT already does."

The -EINVAL from iscsit_process_nop_out() closes the connection only on iscsi-tcp and cxgbit:
- iscsi-tcp: iscsit_handle_nop_out() returns it, iscsi_target_rx_opcode() returns it, and iscsit_get_rx_pdu() breaks out of the RX loop on `ret < 0` (iscsi_target.c, v7.4-rc3 ~4118).
- cxgbit: cxgbit_handle_nop_out() returns it, and cxgbit_process_iscsi_pdu()'s callers bail on `ret < 0` (cxgbit_target.c:1511, 1523).
- isert: isert_handle_nop_out() returns it to isert_rx_opcode(), whose return value is discarded by isert_recv_done() (ib_isert.c:1389, `isert_rx_opcode(isert_conn, rx_desc, ...);` with no check). The PDU is just dropped. The connection only fails later if the nopin response timer expires.

The patch's behaviour is still right on all three (the bad NOP-Out is treated exactly like one naming an unknown TTT). Only the sentence overstates it. Fix in section 3.

### F2 (nit, informational, no change needed): the changelog's list of commands with a non-0xffffffff TTT is accurate but not exhaustive

Confirmed in v7.4-rc3:
- READs: `cmd->targ_xfer_tag = session_get_next_ttt()` when ISCSI_FLAG_CMD_READ is set (iscsi_target.c:1170). Includes bidi.
- Text: TTT copied from the initiator's header on a continuation (iscsi_target.c:2202) or taken from the counter when the target needs a continuation (iscsi_target.c:3506).
- Rejects from iscsit_add_reject(): opcode set to REJECT, targ_xfer_tag never written after the memset in iscsit_allocate_cmd() (iscsi_target_util.c:169), so 0. They stay on conn_cmd_list in ISTATE_SENT_STATUS until a later PDU's ExpStatSN acks them through iscsit_ack_from_expstatsn() (iscsi_target.c:949). The NOP-Out reply branch doesn't call that, so a Reject can still be on the list when the first NOP-In goes out.

Others the changelog doesn't name (all harmless under the new helper because none has opcode ISCSI_OP_NOOP_IN):
- Rejects made from an existing command by iscsit_add_reject_cmd() keep that command's TTT. A READ rejected at iscsi_target.c:1185/1217/1233 (after the TTT is assigned at 1170) goes on conn_cmd_list as an ISCSI_OP_REJECT carrying a counter TTT.
- Async event (MC/S connection drop): iscsit_build_conn_drop_async_message() puts the cmd on conn_cmd_list with TTT 0 (iscsi_target.c:2732-2737). It becomes 0xffffffff only when the TX thread builds the PDU (2755).
- isert only: isert_rx_opcode() always allocates a cmd for NOOP_OUT (ib_isert.c:1260), unlike iscsi-tcp and cxgbit, which allocate only when TTT is 0xffffffff (iscsi_target.c:3958, cxgbit_target.c:1229). A NOP-Out with a valid ITT and TTT != 0xffffffff skips the field setup in iscsit_setup_nop_out() (only done for TTT 0xffffffff, iscsi_target.c:1772) and is added to conn_cmd_list by iscsit_process_nop_out() with opcode 0 (which is ISCSI_OP_NOOP_OUT), i_state 0 and TTT 0. The old helper could match it. The new one can't.
- TMR (2051), logout (2487), NOP-Out ping (1776) and non-READ SCSI (1172) all use 0xffffffff. ERL2 reallegiance moves only SCSI_CMD and NOOP_OUT commands to the new connection (iscsi_target_erl2.c:292, iscsi_target_tmr.c:219/387), so NOP-Ins never migrate. R2T TTTs live in struct iscsi_r2t, not cmd->targ_xfer_tag, and aren't on conn_cmd_list.

The changelog doesn't need to list these. "NOP-Ins aren't the only commands with a TTT" followed by examples is fine.

### F3 (nit, out of scope, for the maintainer's likely question): the double reply is of similar severity

The new helper still returns a NOP-In that's already in ISTATE_REMOVE, so a second reply queues it for removal twice (use-after-free and double free in iscsit_immediate_queue's ISTATE_REMOVE case, iscsi_target.c:3698-3703). The patch's note under `---` says this is deliberately left out, and that's accurate. Two things for the follow-up:
- An `i_state != ISTATE_REMOVE` check in the helper would be racy. iscsit_send_unsolicited_nopin() writes `ISTATE_SENT_NOPIN_WANT_RESPONSE` after the PDU is transmitted (iscsi_target.c:3046-3048), so a fast genuine reply can set REMOVE and then have it overwritten, and a second reply would pass the check.
- Removing the NOP-In from conn_cmd_list with list_del_init() inside the helper, under cmd_lock, before returning it would close it: a second reply can't find it, and the ISTATE_REMOVE handler's own list_del_init() is idempotent. The cost is that a NOP-In removed early but still on the immediate queue at connection teardown isn't freed by iscsit_release_commands_from_conn(). Worth weighing in the separate change.

A maintainer may ask for both fixes in one series. Saying in the note that a follow-up is planned (if it is) would pre-empt that.

### F4 (nit, out of scope, pre-existing, unverified at runtime): isert seems to leak the cmd it allocates for every NOP-Out reply

On isert, a reserved-ITT NOP-Out with a TTT gets a freshly allocated `cmd` (ib_isert.c:1261). iscsit_process_nop_out()'s reply branch returns 0 (or -EINVAL) without freeing `cmd`, and isert_handle_nop_out() doesn't free it either. That seems to leak one sess_tag_pool tag per answered NOP-In on iSER. It isn't affected by this patch and shouldn't go in it. I'm noting it only so nobody attributes it to this change.

## 3. Changelog edits

1. Before: "A NOP-Out that names another command's TTT now closes the connection, as one naming an unknown TTT already does."
   After: "A NOP-Out that names another command's TTT is now handled the same way as one naming an unknown TTT."

No other edits needed. The other factual sentences check out (see section 4).

## 4. What I checked and found correct

- All three callers (iscsi-tcp iscsit_handle_nop_out, cxgbit_handle_nop_out, isert_handle_nop_out) reach the new helper only through the exported iscsit_process_nop_out(), whose signature is unchanged. No transport calls iscsit_find_cmd_from_ttt() directly. The helper is internal to iscsi_target_mod, so no EXPORT_SYMBOL is needed.
- ISCSI_OP_NOOP_IN is set only in iscsit_add_nopin() (iscsi_target_util.c:861 v7.4-rc3). NOP-Ins sent in response to pings keep opcode NOOP_OUT. So opcode NOOP_IN plus TTT != 0xffffffff means exactly an unsolicited want-response NOP-In, and the opcode test is the right discriminator.
- iscsit_add_nopin() is only called with want_response=1 (iscsi_target_util.c:974), so every NOOP_IN on the list has a counter TTT.
- Locking and lifetime are the same as the old helper. The pointer is returned after dropping cmd_lock, and the only things that free a NOP-In are the ISTATE_REMOVE handler (queued by this RX thread itself) and connection teardown (after RX stops). iscsit_ack_from_expstatsn() doesn't touch NOP-Ins (their state is never ISTATE_SENT_STATUS). No new race. It's narrower than before, because the old helper could hand back a READ whose lifetime the backend controls.
- TTT uniqueness among NOP-Ins on one connection: the counter is per session, 32-bit and skips 0xffffffff (include/target/iscsi/iscsi_target_core.h:897). A new want-response NOP-In is only generated after the previous one is answered (nopin timer restarted in the reply branch) or the response timer has failed the connection, so at most one is alive per connection. A collision would need 2^32 allocations with an old NOP-In still on the list. Not reachable in practice, and it wouldn't matter: either NOP-In is a valid target.
- The session counter starts at 0 (sess allocated with kzalloc_obj, iscsi_target_login.c:222), so the first READ's TTT is predictable, as claimed.
- The changelog's reason for not using "existing lookup + opcode check" is valid: a Reject with TTT 0 can sit ahead of a TTT-0 NOP-In on a fresh session with no prior READ, and the first-match lookup returns the Reject.
- Behaviour for correct initiators: unchanged except in that same Reject/NOP-In TTT-0 case, where the old code freed the Reject and left the NOP-In on conn_cmd_list until connection close. The new code matches the NOP-In. That's an improvement, not a regression.
- Alternatives: initializing targ_xfer_tag to 0xffffffff in iscsit_allocate_cmd() fixes Rejects, async and isert NOP-Out entries, but not READs or Text, which legitimately carry counter TTTs, so it's insufficient alone. Putting the opcode check inside iscsit_find_cmd_from_ttt() would break the Data ACK SNACK caller (iscsi_target_erl1.c:539), which needs SCSI READs. A separate helper is the simplest correct option. A maintainer might prefer one helper with an opcode argument (and the SNACK caller could then require ISCSI_OP_SCSI_CMD), but that's style.
- The NULL deref claim: transport_generic_free_cmd(se_cmd, 0) skips target_wait_free_cmd() and calls transport_lun_remove_cmd(), which sets `cmd->se_lun = NULL` (target_core_transport.c:781, 3032-3033). target_complete_ok_work() then reads `cmd->se_lun->lun_stats` in the DMA_FROM_DEVICE case (target_core_transport.c ~2652). The claim is consistent with the code and correctly hedged as not reproduced.
- 9547308bda29 does what the changelog says (non-READ SCSI commands get 0xffffffff), and its own description shows the same first-match lookup hitting a correct initiator in 2015.
- Build: my own worktree at 81547cab0bbb, `make W=1 drivers/target/iscsi/iscsi_target.o drivers/target/iscsi/iscsi_target_util.o` with the shared .config (x86_64, ISCSI_TARGET=m). 0 warnings. isert and cxgbit aren't enabled in that config, but neither references the changed symbols.

## 5. What I couldn't check

- Anything at runtime (by rule). The NULL-deref path, the isert leak in F4, and the Reject/NOP-In ordering on a live session were all checked only by reading the code.
- isert and cxgbit object builds (CONFIG_INFINIBAND_ISERT and CONFIG_CHELSIO_T4 are off in the shared config). They don't call the changed code directly.
- Whether the Fixes: commit e48354ce078c and the stable tag are the best choice. I left that to the history reviewer.
