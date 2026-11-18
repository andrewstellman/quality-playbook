# c5-evidence: evidence and testing review

## 1. Verdict

**SEND AFTER CHANGES.** I re-ran every check myself and they all came out as claimed. Two sentences in the notes below `---` are wrong or say more than the evidence shows, and the patch shouldn't go out until the runtime regression test in section 6 has run, because every NOP-In reply from every initiator goes through the changed line.

## 2. Findings (most severe first)

### F1 (should-fix): don't send before a runtime run

- **What's wrong:** the only evidence for the change is build checks and a userspace test of the lookup. The change is small, but it sits on a path that every logged-in initiator uses every `nopin_timeout` (15 s by default). If the reply isn't matched, the connection is dropped (`iscsi_target.c:1825` returns -EINVAL and the RX loop at `iscsi_target.c:4119-4121` breaks). `coding-assistants.rst` steps 5 and 8 ask for the fix to be verified and for anything untested to be stated. The notes do state it honestly, but "Not yet run on a kernel" on a fix found by an AI is exactly the case `generated-content.rst` says will get extra scrutiny.
- **Fix:** run the test in section 6 (about an hour of guest time), then replace the first paragraph of the notes with what was actually run. See C1.

### F2 (should-fix): one sentence in the notes describes the test case backwards

- **Current:** "returns the NOP-In ahead of a Reject with the same TTT"
- **What's wrong:** the test case (`lookup-test.c`, first check) puts the Reject *ahead of* the NOP-In on `conn_cmd_list`. As written, the sentence reads as if the NOP-In were the one ahead.
- **Fix:** see C2.

### F3 (should-fix): the double-reply sentence states a race as unconditional fact

- **Current:** "A second NOP-Out answering the same NOP-In is still accepted and queues it for removal twice."
- **What's wrong:** this only happens if the second NOP-Out arrives before the TX thread processes the first ISTATE_REMOVE. Once the TX thread has run `list_del_init` and `iscsit_free_cmd` (`iscsi_target.c:3697-3702`), a second reply finds nothing and the connection is closed. It also comes from reading the code, not from observing it. My extra test confirms that the helper itself returns the same NOP-In twice while it's still on the list (case "second reply ttt 4 still matches"), but the userspace test can't model the TX thread.
- **Fix:** see C3.

### F4 (nit): the build evidence covers x86_64 only, and the runtime guest is arm64

- The README and notes say x86_64 with gcc 13.3. I also built it with clang W=1, also clean. Nobody has built it for arm64 (there's no cross compiler on this box). The arm64 guest kernel build will cover that. Do that build with W=1 and record its warnings for `drivers/target/iscsi/`.

### F5 (nit): changelog, "known in advance"

- **Current:** "The counter starts at 0 for each session, so the TTT of a session's first READ is known in advance."
- **Verified:** `sess` is allocated with `kzalloc_obj` (`iscsi_target_login.c:222`), `session_get_next_ttt()` post-increments and skips 0xFFFFFFFF (`iscsi_target_core.h:897-908`), and nothing else initialises `sess->targ_xfer_tag`.
- **Why it's a nit:** the first READ only gets 0 if no NOP-In ping or Text continuation has used the counter first. "Predictable" is the accurate word, though in practice a READ (or INQUIRY) right after login gets 0. Optional edit in C4.

## 3. Changelog and notes edits

**C1** (notes, after the runtime test has run). Current:
> Not yet run on a kernel. So far it builds with W=1 and no new warnings
> (x86_64, ISCSI_TARGET=m), applies cleanly to 7.4/scsi-fixes and
> 7.5/scsi-staging, and the new lookup, compiled from this patch into a
> userspace test, returns the NOP-In ahead of a Reject with the same TTT
> and doesn't match READ or Text commands.

After (fill in the real numbers, and only list what actually ran):
> Tested on an arm64 QEMU guest: an open-iscsi initiator over 127.0.0.1
> to a block backstore on dm-delay logged in, ran verified I/O for N
> minutes with READs outstanding, answered all M NOP-In pings with no
> connection drops, and logged out and back in K times, also with two
> sessions at once. It builds with W=1 and no new warnings (x86_64 and
> arm64) and applies cleanly to 7.4/scsi-fixes and 7.5/scsi-staging. A
> userspace test of the new lookup returns the NOP-In when a Reject
> with the same TTT is ahead of it, and doesn't match READ or Text
> commands. I haven't tried a NOP-Out that names another command's TTT.

**C2** (if it's sent before the runtime test). Current: "returns the NOP-In ahead of a Reject with the same TTT" → After: "returns the NOP-In when a Reject with the same TTT is ahead of it on the list"

**C3** Current:
> A second NOP-Out answering the same NOP-In is still accepted and queues
> it for removal twice.

After:
> From reading the code, a second NOP-Out answering the same NOP-In is
> still accepted if it arrives before the TX thread has freed the NOP-In,
> and queues it for removal twice.

**C4** (optional) Current: "so the TTT of a session's first READ is known in advance." → After: "so the TTTs a session's READs get are predictable."

## 4. What I checked and found correct

- **Patch file = branch commit.** `git format-patch --base=v7.4-rc3 -1 iscsit-nopout-ttt` diffed against the file. The only difference is the 10 note lines below `---`. Author and committer are both `Andrew Stellman <astellman@stellman-greene.com>`. The branch parent is v7.4-rc3 `aebb7274476403040d582c61478df8f4a7bf9cd3`.
- **checkpatch from inside my worktree.** Default: only "Missing Signed-off-by". `--strict`: also the `extern` CHECK. `-g HEAD`: same result. With a Signed-off-by inserted: 0 errors, 0 warnings, 1 CHECK. There's no GIT_COMMIT_ID warning, so the commit IDs resolve. Keeping the `extern` to match the rest of the header is reasonable.
- **W=1 builds.** gcc 13.3 x86_64: `make O=…/c5-evidence/out W=1 drivers/target/iscsi/` compiled all 18 objects with 0 warnings. clang (LLVM=1) W=1 of `iscsi_target_util.o` and `iscsi_target.o`: 0 warnings.
- **`git am` in my own worktrees.** It applies cleanly to mkp/7.4/scsi-fixes @9f9e0b1e5399 and mkp/7.5/scsi-staging @08fec21faae4. Neither branch changes `iscsi_target_util.[ch]` or the NOP paths in `iscsi_target.c` relative to rc3. scsi-staging is based on v7.4-rc1, so the "0 commits since rc3" in the check log is a range artifact, but the conclusion is correct.
- **real_lookups.c is verbatim.** It's identical to patched `iscsi_target_util.c:384-422` apart from the comment line (checked with diff).
- **Shims don't change behaviour.** The locks and `pr_err` are no-ops (single-threaded), `list_for_each_entry` and `list_add_tail` are equivalent, and the opcode constants match `include/scsi/iscsi_proto.h` (0x20, 0x01, 0x04, 0x3f). The field types used match `iscsit_cmd` (u8 opcode, u32 TTT). Their 7/7 cases and 1/2 comparison cases reproduce exactly.
- **My extra cases: 11/11 pass**, and are also clean under ASan/UBSan (`/home/claude/k/council/c5-evidence/ut/extra-test.c`). They cover:
  - an empty list
  - [READ0, Reject0, Text0, NOP-In0], which returns the NOP-In, while the old lookup returns READ0
  - two NOP-Ins, each selected by its TTT
  - a Reject that kept a READ's TTT
  - a NOP-In behind 1000 READs
  - 0xFFFFFFFF, which matches a no-response NOP-In but can't be reached because the caller filters it at `iscsi_target.c:1823`
  - the double reply, which still matches and documents F3
- **Gaps in the userspace test.** It has no `i_state`, so it can't show that a NOP-In not yet sent (ISTATE_SEND_NOPIN_WANT_RESPONSE) is also matched. That's the same as before the patch and belongs with the double-reply change. It doesn't test the caller, but the caller change is one line and I checked it by diff.
- **Changelog facts I verified in the source:**
  - The first-match lookup is `util.c:384-402`.
  - ISTATE_REMOVE is freed by the TX thread at `iscsi_target.c:3697-3702`.
  - READs get a TTT from the counter at `:1169-1172`, and Text continuations at `:3506-3507`.
  - A Reject from `iscsit_add_reject` keeps TTT 0, because of the memset at `util.c:169` and nothing setting it after `:794-812`.
  - `transport_generic_free_cmd(se_cmd, 0)` doesn't wait and NULLs `se_lun` (`target_core_transport.c:3020-3033`, `765-782`).
  - `target_complete_ok_work` dereferences `cmd->se_lun->lun_stats` for DMA_FROM_DEVICE (around `target_core_transport.c:2652`).
  - The only other caller is `iscsit_handle_data_ack` (`erl1.c:539`).
  - cxgbit and isert also call `iscsit_process_nop_out`, so they get the fix too.
  - The only place that sets `ISCSI_OP_NOOP_IN` is `iscsit_add_nopin` (`util.c:861`).
- **Fixes and commit references.** `e48354ce078c` has the identical unchecked lookup (`iscsi_target.c:1654` in that commit). `9547308bda29` is in v4.2 and says what the changelog says about it. Both references use the correct format and subject.

## 5. What I couldn't check

- Anything at runtime: by the brief, nothing was booted.
- An arm64 build (no cross compiler here). sparse and smatch aren't installed.
- Whether linux-scsi or target-devel have posted a competing fix since 17 Nov (no list access from this review).

## 6. Runtime regression test (legitimate initiator behaviour only)

**Setup**
- Build the patched tree for arm64 with W=1, `ISCSI_TARGET=m`, `TCM_IBLOCK=m`, `DM_DELAY=m` and `ISCSI_TCP=m`. Turn on `KASAN`, `DEBUG_LIST`, `PROVE_LOCKING`, `DEBUG_OBJECTS_TIMERS` and `DYNAMIC_DEBUG` so that silent corruption shows up.
- Boot it with `-kernel`. Build the same config from unpatched v7.4-rc3 as a baseline and run the identical script on it. Both should pass.
- Confirm the patched module is the one loaded: `grep iscsit_find_nopin_from_ttt /proc/kallsyms` must be non-empty on the patched kernel and empty on the baseline.
- **Backing device:**
  ```
  losetup /dev/loop0 1G.img
  dmsetup create slow --table "0 $(blockdev --getsz /dev/loop0) delay /dev/loop0 0 1000 /dev/loop0 0 0"
  ```
  This delays reads by 1 s and leaves writes undelayed. Keep the delay well under the 30 s SCSI timeout and the NOP response timeout.
- **LIO configuration:**
  - block backstore on `/dev/mapper/slow`, one LUN, portal 127.0.0.1:3260
  - an explicit ACL for the initiator IQN, so the NOP attributes can be set. For the fast run, set `attrib/nopin_timeout=5` and `attrib/nopin_response_timeout=5`, both at the minimum of 3 or above. For the final run, use the defaults of 15 and 30.
- **Ping logging:** enable dynamic debug for the two existing messages:
  ```
  echo 'module iscsi_target_mod format "Sending Unsolicited NOPIN" +p' > /proc/dynamic_debug/control
  echo 'module iscsi_target_mod format "Got NOPOUT Ping" +p' > /proc/dynamic_debug/control
  ```
  On little-endian arm64 the TTT in these lines prints byte-swapped, but it's swapped the same way in both lines, so matching by value still works.
- Initiator: open-iscsi with `discovery`, then `--login`.

**Phases**
1. **Idle pings.** Log in, then do no I/O for at least 10 × `nopin_timeout` (and at least 3 × (`nopin_timeout` + `nopin_response_timeout`) in the default-timeout run).
2. **Pings with READs outstanding (the case the patch changes).** Run fio for 5 min or more on the LUN with direct I/O, randrw, and a 70/30 read/write mix, iodepth 16, and `verify=crc32c` on a written region. Sample `/sys/block/sdX/inflight` once a second.
3. **Initiator-originated pings too.** Repeat phase 2 once with the open-iscsi default `noop_out_interval` (5 s), and once with `node.conn[0].timeo.noop_out_interval=0` and `noop_out_timeout=0`, so that the only NOP traffic is the target's pings.
4. **Logout and relogin.** Do 20 cycles of: quiesce, logout, check that the ACL `info` shows no session, log in, run 30 s of fio verify, and stay logged in for at least 2 × `nopin_timeout`. The TTT counter restarts at 0 in each new session.
5. **Two sessions.** Create two ifaces (`iscsiadm -m iface -I a --op=new`, and the same for `b`), log in to the same target through both, and run fio on both devices for 5 min. The two sessions' TTTs overlap from 0, so this checks that each reply is matched on its own connection.
6. **Final logout.** Unload `iscsi_target_mod` and check that kmemleak, if enabled, has nothing new.

**Measurements and pass criteria (all must hold on the patched kernel, with the same results on the baseline)**
- **No error messages.** Target and initiator dmesg must have zero lines matching:
  - `Unable to locate NOPIN TTT`
  - `Unable to locate TTT`
  - `Did not receive response to NOPIN`
  - `detected conn error`
  - `connection.*error`
  - `KASAN`, `BUG:`, `WARNING:`, `list_add corruption`, `list_del corruption`, `possible circular locking`
- **Every ping answered, per phase.** For every `Sending Unsolicited NOPIN TTT: X` with X != 0xffffffff, a `Got NOPOUT Ping Response ITT: 0xffffffff, TTT: X` follows within `nopin_response_timeout`. The only allowed exception is the last ping, which may still be in flight at the end. The ping count must be at least floor(duration / `nopin_timeout`) − 1.
- **Per-session counts in phase 5.** Use `iscsiadm -m session -r SID -s` with initiator pings off (phase 3 setting). Over the phase, `noprx_pdus` and `noptx_pdus` each go up by the same amount (±1), and by roughly duration / `nopin_timeout`, on *both* sessions.
- **The interleaving actually happened.** In phase 2, consecutive NOP-In TTTs must show gaps (READs took TTTs in between), and at least half of the ping exchanges must coincide with an `inflight` sample whose read count is above 0. If not, raise the dm-delay read delay or the iodepth and rerun. Otherwise the phase hasn't tested the changed lookup with READs on the list.
- **Sessions don't drop.** Within each phase the SID and connection stay the same (`iscsiadm -m session -P 1` shows `LOGGED IN`/`LOGGED_IN` and an unchanged SID), with no reinstatement.
- **I/O is correct.** fio exits 0 with zero verify errors and zero I/O errors in every phase.
- **Logout is clean.** All 20 logout/login cycles succeed, and the module unloads.

**Leave out:** any step that sends a hand-made NOP-Out, reuses or guesses a TTT, sends a second reply, or is meant to trigger the NULL `se_lun` dereference. The Reject-ahead-of-NOP-In case can't happen with a correct initiator, because a Reject needs a protocol error and INQUIRY at login consumes TTT 0. That case stays covered by the userspace test only, and the notes should say that rather than imply the runtime test covered it.

## 7. Should it go out before the runtime test?

No. Nothing I found suggests the code is wrong, but the run is cheap. It's the only evidence that correct initiators still work on the one line every session uses, and without it the notes have to say "Not yet run on a kernel", which `coding-assistants.rst` and `generated-content.rst` both signal will get the patch less attention or more suspicion. Run it, put C1 in place of the first paragraph of the notes, apply C3, then send.

Scratch area: `/home/claude/k/council/c5-evidence/`. It has worktrees `tree`, `am-7.4-scsi-fixes` and `am-7.5-scsi-staging`, build dirs `out` and `out-clang`, `build-W1.log`, `build-clang-W1.log`, `fp.patch`, `signed.patch` and `ut/`.
