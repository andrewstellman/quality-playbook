# c3-adversarial: review of 0001-scsi-target-iscsi-Match-NOP-Out-replies-only-against.patch

## 1. Verdict

SEND AFTER CHANGES. The code change is correct and I couldn't break it: no conforming-initiator sequence regresses, and after it no non-NOP-In command can reach ISTATE_REMOVE through the NOP-Out path. One changelog sentence overstates the behaviour on iSER and should be reworded.

## 2. Findings

### F1 (should-fix, changelog accuracy): "now closes the connection" is not true on iSER

The changelog says: "A NOP-Out that names another command's TTT now closes the connection, as one naming an unknown TTT already does."

That's true for iscsit TCP and cxgbit, but not for iSER:
- TCP: `iscsi_target_rx_opcode()` returns the -EINVAL and `iscsit_get_rx_pdu()` breaks out (iscsi_target.c:4119-4121).
- cxgbit: `cxgbit_rx_opcode()` goes to transport_err on `< 0` (cxgbit_target.c, `if (cxgbit_target_rx_opcode(csk) < 0) goto transport_err;`).
- iSER: `isert_recv_done()` calls `isert_rx_opcode(...)` and ignores the return value (ib_isert.c:1389). The bad NOP-Out is dropped and the connection stays up.

The relative part ("as one naming an unknown TTT already does") is right on all three transports, because both cases take the same `return -EINVAL`. Only "closes the connection" is too broad. On iSER the fix still works (the READ isn't touched), so this is wording, not code.

Fix: see changelog edit 1.

### F2 (nit, changelog): Reject sources

"Rejects allocated by iscsit_add_reject() keep the 0" is correct (iscsi_target.c:787-815, `memset` at iscsi_target_util.c:169), but `iscsit_add_reject_cmd()` on a SCSI command rejected early in `iscsit_setup_scsi_cmd()` (before the TTT is assigned at iscsi_target.c:1169-1172) also leaves a Reject with TTT 0 on `conn_cmd_list`. Async Event commands (iscsi_target.c:2732, MC/S only) also sit on the list with TTT 0 until sent. The patch handles all of these because it filters on opcode; the sentence just names one source. Optional: drop the function name ("and Rejects keep the 0 ..."). Leaving it is fine.

### F3 (nit, code): format specifier

The new `pr_err` uses `CID: %u`; the existing `iscsit_find_cmd_from_ttt()` right above uses `%hu` for the same u16 `conn->cid`, as do 21 other messages in drivers/target/iscsi (1 uses `%u`). Not a warning either way. Use `%hu` for consistency if respinning; not worth a respin by itself.

### Out-of-scope items a reviewer will ask about

Each is pre-existing and none weakens this patch; they're separate changes.

1. **Double reply (two NOP-Outs for one NOP-In).** Still double-queues ISTATE_REMOVE for the NOP-In (hostile only; a conforming initiator answers once). Separate change, as the note says. Important for whoever writes it: an `i_state != ISTATE_REMOVE` test is not sufficient. `iscsit_send_unsolicited_nopin()` writes `i_state = ISTATE_SENT_NOPIN_WANT_RESPONSE` after `xmit_pdu` returns (iscsi_target.c:3045-3048), so if the reply arrives before the TX thread gets there, TX overwrites the RX thread's ISTATE_REMOVE and a second NOP-Out passes the test. An `== ISTATE_SENT_NOPIN_WANT_RESPONSE` test is worse: it races the same way against a fast correct initiator, and isert never moves a NOP-In out of ISTATE_SEND_NOPIN_WANT_RESPONSE (`isert_immediate_queue()` / `isert_put_nopin()`, ib_isert.c:2211-2213, 1894-1911), so it would break iSER keepalives entirely. A robust fix is to `list_del_init()` the NOP-In under `cmd_lock` in the lookup itself, so a second lookup can't find it (the TX REMOVE case already does `list_del_init`, which is idempotent). The patch's opcode-only predicate is the right one for this patch precisely because it doesn't depend on i_state.
2. **Related hostile race, same class.** `iscsit_add_nopin()` (iscsi_target_util.c:852-876) puts the NOP-In on `conn_cmd_list` before queuing ISTATE_SEND_NOPIN_WANT_RESPONSE. A NOP-Out that guesses the TTT in that window queues REMOVE ahead of SEND, and TX would free then send. Tiny window, TTT predictable. Belongs with the double-reply change (queue first or add to the list after queuing), not here.
3. **iscsit_handle_data_ack() (ERL>=1) keeps the first-match lookup** (iscsi_target_erl1.c:539). It only sets `ICF_GOT_DATACK_SNACK` and `acked_data_sn` on whatever it finds; it frees nothing. The same Reject-TTT-0 shadowing can misdirect a correct initiator's Data ACK for a session's first READ (TTT 0) to a Reject. Low impact, ERL>=1 only, separate patch. The changelog already says it's left unchanged; that's enough.
4. **Text TTT.** Text continuations are looked up by ITT (`iscsit_find_cmd_from_itt`, iscsi_target.c rx_opcode ISCSI_OP_TEXT; same in isert and cxgbit), not TTT, so there's no TTT-confusion bug there. Note `iscsit_process_text_cmd()` copies the initiator's TTT into `cmd->targ_xfer_tag` when there's no text_in (iscsi_target.c:2202), so with the old lookup a hostile initiator could plant any TTT on a Text command. The new helper's opcode filter makes that irrelevant to the NOP-Out path.
5. **Rejects on conn_cmd_list.** Normal lifetime: SENT_STATUS after send (iscsi_target.c:3837-3840), freed when ExpStatSN acks them (iscsit_ack_from_expstatsn, iscsi_target.c:949-977). They don't need to come off the list for this fix; the opcode filter makes their TTT 0 harmless.
6. **iSER leaks the NOP-Out's own iscsit_cmd on every NOP-In reply (pre-existing, from code reading only).** `isert_rx_opcode()` allocates a cmd for every NOP-Out (ib_isert.c:1260-1267), but `iscsit_process_nop_out()` only frees `cmd` on the final "not expecting a response" path (added by 1a40f0a36fb6 for the TTT=0xffffffff case); the TTT-reply path and the `return -EINVAL` path return without freeing it. On TCP and cxgbit `cmd` is NULL there, so only iSER is affected. Each answered NOP-In would leak one session tag, and `iscsit_allocate_cmd()` then waits for a tag (TASK_INTERRUPTIBLE). Not caused or worsened by this patch (the -EINVAL path leaked before too). Worth a separate look; I haven't confirmed it on hardware and haven't checked whether something I missed reclaims the tag.

## 3. Changelog edits

1. Before: "A NOP-Out that names another command's TTT now closes the connection, as one naming an unknown TTT already does."
   After: "A NOP-Out that names another command's TTT is now handled the same way as one naming an unknown TTT, which closes the connection on TCP and cxgbit."
2. (optional) Before: "and Rejects allocated by iscsit_add_reject() keep the 0 that iscsit_allocate_cmd() leaves in targ_xfer_tag."
   After: "and Rejects keep the 0 that iscsit_allocate_cmd() leaves in targ_xfer_tag."

## 4. What I checked and found correct

- Only one place sets `iscsi_opcode = ISCSI_OP_NOOP_IN` (iscsi_target_util.c:861, `iscsit_add_nopin`); nothing later changes a NOP-In's opcode (`iscsit_add_reject_from_cmd` only touches RX commands). So the helper can't return a non-NOP-In.
- `iscsit_add_nopin()` is only called with want_response=1 (iscsi_target_util.c:974), so every NOP-In on the list has a real TTT; NOP-In echo replies to pings are ISCSI_OP_NOOP_OUT with TTT 0xffffffff and aren't matchable.
- Conforming initiators (RFC 7143 NOP-Out TTT = copy of the NOP-In's TTT, else 0xffffffff) only send TTTs of live NOP-Ins; the lookup now fails only when the TTT names a non-NOP-In, which a conforming initiator can't do except by TTT collision, where the new lookup is the correct one. No regression found.
- Pre-patch, the Reject-TTT-0 / NOP-In-TTT-0 case with a correct initiator freed the Reject and left the NOP-In on the list until connection close; the patch fixes that too.
- TTT counter starts at 0 per session (`session->targ_xfer_tag++`, iscsi_target_core.h:902-904) and READ, R2T, Text continuation and NOP-In share it (iscsi_target.c:1170, 3093, 3507; util.c:866). Changelog claim confirmed.
- 9547308bda29 does what the changelog says (non-READ SCSI commands get TTT 0xffffffff); its own changelog describes the same first-match shape.
- READ freed via `iscsit_free_cmd(cmd, false)` -> `transport_generic_free_cmd(se_cmd, 0)` doesn't wait for tasks and `transport_lun_remove_cmd()` NULLs `se_lun` (target_core_transport.c:765-782, 3014-3044); `target_complete_ok_work()` dereferences `cmd->se_lun->lun_stats` for DMA_FROM_DEVICE (target_core_transport.c:2652). Changelog's "from reading the code" claim is accurate and properly hedged.
- Timers when the lookup now fails: the `return -EINVAL` is before `iscsit_stop_nopin_response_timer()` / `iscsit_start_nopin_timer()`, so timers stay exactly as they would for an unknown TTT. On TCP/cxgbit `iscsit_close_connection()` stops both (iscsi_target.c:4285-4286). On iSER the connection stays up and the real NOP-In's response timer keeps running, which is correct: a real reply later stops it, no reply fails the connection. No bad timer state.
- cxgbit: uses `iscsit_immediate_queue`/`iscsit_response_queue` (cxgbit_main.c:677-678), allocates no cmd for TTT!=0xffffffff NOP-Outs, one RX thread per connection like TCP; cxgbit's DDP tag goes in `r2t->targ_xfer_tag`, not `cmd->targ_xfer_tag`. Nothing differs.
- isert: the opcode-only predicate works with isert never updating NOP-In i_state; the ISTATE_REMOVE handler does `list_del_init` + `isert_put_cmd` like TCP.
- Locking: the helper takes `conn->cmd_lock` with `spin_lock_bh` exactly like `iscsit_find_cmd_from_ttt()`; returning the pointer after unlock is the same as before and safe because only the RX thread queues REMOVE for a NOP-In.
- `iscsit_find_cmd_from_ttt()` has one remaining caller (iscsi_target_erl1.c:539), as the changelog says.
- The extracted helper in checks/real_lookups.c matches the patch text; the test cases and output are consistent with the code.

## 5. What I couldn't check

- I didn't build the patched tree myself (relied on checks/build-W1.txt), and nothing was run on a kernel.
- iSER tag leak (out-of-scope item 6) is from code reading only.
- Whether maintainers would rather have the double-reply fix as patch 2/2 of the same series; I'd suggest offering it that way, but this patch stands on its own.
