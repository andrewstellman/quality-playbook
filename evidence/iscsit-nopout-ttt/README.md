# iscsit NOP-Out TTT lookup (QPB iSCSI run, BUG-035)

The patch file is ready for `git send-email` once it has your Signed-off-by. It hasn't been sent anywhere.

## What it changes

`iscsit_process_nop_out()` now looks the reply's TTT up with a new `iscsit_find_nopin_from_ttt()`, which only matches NOP-In commands. `iscsit_find_cmd_from_ttt()` is unchanged for its other caller (Data ACK SNACK, ERL>=1).

This isn't the council's replacement fix. Both reviewers proposed "opcode is NOOP_IN and state isn't REMOVE" after the existing first-match lookup. A Reject from `iscsit_add_reject()` has TTT 0 (never set after the memset in `iscsit_allocate_cmd()`), and on a fresh session the first NOP-In ping can also get TTT 0. With a Reject ahead of it on `conn_cmd_list`, the first-match lookup returns the Reject, so the opcode check would drop a correct initiator's reply. `checks/lookup-test-output.txt` shows that case failing for the opcode-check version and passing for this one.

The double reply (two NOP-Outs for one NOP-In) isn't addressed. The note below the `---` line says so.

## Where it was built

Cloud workspace: a `git clone` of torvalds/linux at `v7.4-rc3` (`aebb7274476403040d582c61478df8f4a7bf9cd3`), branch `iscsit-nopout-ttt`, made with `git format-patch --base=v7.4-rc3`. Author and committer are `Andrew Stellman <astellman@stellman-greene.com>`.

## Checks run (all in `checks/`)

| Check | Result |
|---|---|
| `checkpatch.pl` (default) | Only "Missing Signed-off-by". `--strict` adds one CHECK for `extern` in the header, kept because every other prototype there uses it |
| W=1 build of `drivers/target/iscsi/` (x86_64, gcc 13.3) | 0 warnings |
| `git am` onto mkp `7.4/scsi-fixes` and `7.5/scsi-staging` (fetched 2026-11-18) | Applies cleanly to both. Neither branch touches this code |
| Fixes tag | `e48354ce078c` has the same unchecked lookup (shown in `history-and-maintainers.txt`). The lines blame to `778de368964c`, the 2013 refactor |
| 2015 commit cited in the changelog | `9547308bda29`, in mainline since v4.2 |
| Lookup unit test | The real helper extracted from the patched file, compiled with `-Wall -Wextra -Werror` against list/lock shims: 7/7 pass |

## Not done

- Your Signed-off-by. The kernel's coding-assistants.rst doesn't allow an AI to add it. Add it with `git commit -s --amend`, or put it above the `---` line.
- No run on a kernel. The plan is to build this on the lab guest and boot it with `KERNEL=` (not into `/boot`), then confirm that an open-iscsi session logs in, does I/O against the slow LUN, and keeps answering NOP-In pings past the 15-second nopin timeout. When that's done, the first paragraph under `---` should be updated to say so.
- The QPB harness test (`test_reg_nopout_ttt_matches_only_nopin`) wasn't rerun. It stubs `iscsit_find_cmd_from_ttt()` with one planted command, so it doesn't build against the new helper and can't model list order.
- Recipients aren't decided. `get_maintainer.pl` output is in `checks/history-and-maintainers.txt`. Martin K. Petersen and linux-scsi/target-devel are the minimum.
- target-devel and linux-scsi haven't been checked again since the council's 17 Nov search.
