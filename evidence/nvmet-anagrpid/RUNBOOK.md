# Runbook: confirm and package the nvmet ANAGRPID-128 fix

You are Claude Code running on Andrew Stellman's Mac. Your job is to independently
reproduce one Linux kernel bug in a QEMU guest, confirm that one patch fixes it and
nothing else, trace the bug's origin for a `Fixes:` tag, and package a draft patch email.
You write everything you did and everything you saw into an evidence folder. You do not
send anything anywhere.

You have no memory of the earlier work that set this up. Everything you need is in this
file and the files it names. Read this whole file before running anything.

## The bug, in one paragraph

`drivers/nvme/target/configfs.c` accepts an ANA group ID of 128 (`NVMET_MAX_ANAGRPS`) in
two places, then passes it through `array_index_nospec(id, NVMET_MAX_ANAGRPS)`, which
clamps to `[0, 128)` and turns 128 into 0. The backing array
`nvmet_ana_group_enabled[NVMET_MAX_ANAGRPS + 1]` has a slot 128, and the target
advertises ANAGRPMAX = 128, so 128 is a valid ID and 0 is reserved. Two visible symptoms:
writing 128 to a namespace's `ana_grpid` reads back 0; creating and removing
`ports/N/ana_groups/128` leaves the slot-128 counter wrapped to `0xFFFFFFFF`, so the
ANA log page reports a phantom group 128 forever. The fix is `NVMET_MAX_ANAGRPS + 1` as
the size argument at both sites. Full write-up with code and spec quotes: `README.md`
in this folder. Do not change the diagnosis or the patch; your job is to test them.

## Paths

| what | where |
|---|---|
| evidence folder (you write here) | `~/Documents/QPB/evidence/nvmet-anagrpid/` |
| the patch under test | `~/Documents/QPB/evidence/nvmet-anagrpid/nvmet-anagrpid-128-nospec.patch` |
| the other patch (control, do not apply) | `~/Documents/QPB/evidence/nvmet-crto/nvmet-crto-from-cap.patch` |
| QEMU lab | `~/src/qemu-lab/` |
| ssh into the guest | `bash ~/src/qemu-lab/ssh.sh '<command>'` (runs `<command>` in the guest, echoes output) |
| copy scripts and patches into the guest | `bash ~/src/qemu-lab/scp.sh` |
| reproducer scripts (Mac side) | `~/src/qemu-lab/guest/repro-bug002-anagrpid.sh`, `repro-bug002-analog.sh`, `repro-bug001-crto.sh` |
| kernel build script (Mac side) | `~/src/qemu-lab/guest/build-kernel.sh` |
| full-history kernel clone, for blame | `~/src/linux` (blobless partial clone of torvalds/linux) |
| spec text | `~/Documents/QPB/repos/linux/nvme-target/reference_docs/cite/nvme-base-2.4.txt` |

Inside the guest, after `scp.sh`, the same scripts are at `~/guest/` and the patches at
`~/patches/` for user `lab`. The kernel source tree is `~/linux` in the guest, checked
out at the snapshot commit `4d7d9486c04d917265f64c55bd23b2cc4fe7749c` (v7.3-rc1).

## Hard rules

1. Never run `git send-email`, never `git push`, never post anything. Output is files only.
2. Never edit the patch, the reproducer scripts, or `build-kernel.sh`. If one of them
   seems wrong, stop and write what you found in `RUN-REPORT.md` under "Stopped".
3. Never fabricate output. Every log in the report is pasted from what a command printed.
   If a command failed, paste the failure.
4. Any reproducer result that is not a clean `RED:` or `GREEN:` line halts the run. Write
   the raw output to the report and stop. Do not retry with modifications.
5. Diagnose and fix the environment if it gets in the way (disk space, a missing package,
   a module not loading); do not change the experiment. Record every such fix.
6. Do not reuse the kernels already installed in the guest from the manual run
   (`7.3.0-rc1-qpb+`, `-qpb-anagrpid+`, `-qpb-crto+`). Build your own with the suffixes
   below so your evidence is independent of theirs.
7. No estimates of how long anything will take. Report what finished.

## Known traps (each cost time once; the scripts already handle them)

- Ubuntu's kernel does not ship `nvme-loop`; the scripts use NVMe/TCP to `127.0.0.1:4420`.
  The transports (`nvmet-tcp`, `nvme-tcp`) live in `linux-modules-extra`, already
  installed in this guest.
- `build-kernel.sh` disables debug info (an unstripped module tree was 8.8 GB and the
  initramfs step died with `zstd` exit 70, ENOSPC), strips modules on install, and purges
  `flash-kernel`, which breaks `make install` on a UEFI guest. Check `df -h /` before each
  build anyway; below about 8 GB free, remove old `/lib/modules/*qpb*` trees from
  earlier builds you made (not the manual run's) and re-check.
- nvme-cli 2.x: the get-property offset flag is `--offset=`, not `-o`.
- Reboot takes under a minute; ssh refuses connections until sshd is up. Retry `ssh.sh
  'uname -r'` every 10 seconds for up to 2 minutes rather than assuming failure.
- `ssh.sh` returns the remote command's exit code. The reproducers exit 1 on RED and 0 on
  GREEN by design; do not treat exit 1 as a failure of the command.

## Procedure

Save every command's full output. The simplest way: run each `ssh.sh` through
`tee -a ~/Documents/QPB/evidence/nvmet-anagrpid/cc-transcript.txt`.

### Step 0: preflight

```
bash ~/src/qemu-lab/ssh.sh 'uname -r; df -h /; ls /boot | grep vmlinuz; nvme version | head -1'
bash ~/src/qemu-lab/scp.sh
```

Record the output. If the guest is unreachable, stop: the operator has to start it
(`bash ~/src/qemu-lab/run.sh` in a terminal). Do not try to start it yourself.

### Step 1: red on the unpatched snapshot commit

```
bash ~/src/qemu-lab/ssh.sh 'SUFFIX=cc-base bash guest/build-kernel.sh' 2>&1 | tail -5
```

Must end with `installed: 7.3.0-rc1-qpb-cc-base+ and set as GRUB default`. Then:

```
bash ~/src/qemu-lab/ssh.sh 'sudo reboot'
# poll until it answers
bash ~/src/qemu-lab/ssh.sh 'uname -r'
bash ~/src/qemu-lab/ssh.sh 'sudo bash guest/repro-bug002-anagrpid.sh; sudo bash guest/repro-bug002-analog.sh; sudo bash guest/repro-bug001-crto.sh' 2>&1 | tee ~/Documents/QPB/evidence/nvmet-anagrpid/cc-red-base.txt
```

`uname -r` must be exactly `7.3.0-rc1-qpb-cc-base+`; if it is not, stop. Expected
verdicts, in order: RED, RED, RED. Anything else: stop.

### Step 2: green with only this patch

```
bash ~/src/qemu-lab/ssh.sh 'SUFFIX=cc-anagrpid bash guest/build-kernel.sh patches/nvmet-anagrpid-128-nospec.patch' 2>&1 | tail -5
```

The script resets the tree to the snapshot commit before applying, so this kernel
contains only this patch. Must end with `installed: 7.3.0-rc1-qpb-cc-anagrpid+ ...`.
Reboot, confirm `uname -r` is exactly `7.3.0-rc1-qpb-cc-anagrpid+`, run the same three
scripts, save to `cc-green-anagrpid.txt`. Expected verdicts: GREEN, GREEN, RED. The
trailing RED is the cross-check: the CRTO defect is untouched by this patch. Anything
else: stop.

### Step 3: trace the origin for `Fixes:`

In `~/src/linux` (on the Mac, not the guest). This clone is blobless, so the first blame
on a file pulls its history from GitHub; that is expected and can take a minute.

```
cd ~/src/linux
git blame -L 701,701 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/configfs.c
git blame -L 1979,1979 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/configfs.c
```

Those are the two `array_index_nospec(..., NVMET_MAX_ANAGRPS)` lines. For each blamed
commit, run `git show <sha> -- drivers/nvme/target/configfs.c` and answer, with the
diff excerpt pasted: did this commit introduce the `array_index_nospec` call with the
`NVMET_MAX_ANAGRPS` bound, or did it move or reformat a line that already had it? If it
moved it, follow the history back (`git log --oneline -S'array_index_nospec(newgrpid'
-- drivers/nvme/target/configfs.c` and likewise for `grpid`) until you find the commit
that introduced the bound. The `Fixes:` tag names the introducing commit. If the two
sites were introduced by different commits, say so; a patch may carry two `Fixes:` lines.
Write the full chain of reasoning into the report; a reviewer will check it.

Format the tag with `git log -1 --format='Fixes: %h ("%s")' <sha>` (12-character hash).

### Step 4: package the patch

```
cd ~/src/linux
git checkout -q -b qpb/nvmet-anagrpid 4d7d9486c04d917265f64c55bd23b2cc4fe7749c
git apply --check ~/Documents/QPB/evidence/nvmet-anagrpid/nvmet-anagrpid-128-nospec.patch
git apply ~/Documents/QPB/evidence/nvmet-anagrpid/nvmet-anagrpid-128-nospec.patch
git diff
./scripts/checkpatch.pl --strict -g HEAD   # after committing; see below
./scripts/get_maintainer.pl -f drivers/nvme/target/configfs.c
```

Commit with the message below, filling in the `Fixes:` line(s) from step 3 and the
kernel release strings from your own runs. Author is
`Andrew Stellman <astellman@stellman-greene.com>`; check `git config user.name` and
`user.email` in `~/src/linux` and set them for this repo only if they differ.
Do NOT add a Signed-off-by line and do not use `git commit -s`:
`Documentation/process/coding-assistants.rst` says AI agents must not add
Signed-off-by; the operator adds it when amending before sending. Then:

```
git commit -F <message file>
./scripts/checkpatch.pl --strict -g HEAD
git format-patch -1 --base=4d7d9486c04d917265f64c55bd23b2cc4fe7749c -o ~/Documents/QPB/evidence/nvmet-anagrpid/
```

Rename the output to `DRAFT-0001-nvmet-....patch`. Paste the checkpatch and
get_maintainer output into the report. Do not send it.

Commit message. Keep the shape; replace the bracketed parts; do not add claims that are
not in your logs:

```
nvmet: accept ANA group ID NVMET_MAX_ANAGRPS in configfs

nvmet_ns_ana_grpid_store() and nvmet_ana_groups_make_group() accept an
ANA group ID in the closed range 1..NVMET_MAX_ANAGRPS, but then pass it
through array_index_nospec() with NVMET_MAX_ANAGRPS as the size.  That
helper treats the size as a half-open bound, so the maximum valid ID,
128, is rewritten to 0.

nvmet_ana_group_enabled[] is NVMET_MAX_ANAGRPS + 1 entries wide, so
index 128 is a valid slot, and the controller advertises ANAGRPMAX =
NVMET_MAX_ANAGRPS.  NVMe Base Specification 2.4, section 8.1.1
(Asymmetric Namespace Access Reporting), "ANA Groups", defines a valid
ANA Group Identifier as "a non-zero value that is less than or equal to
ANAGRPMAX".

Two visible effects.  Writing 128 to a namespace's ana_grpid succeeds
but the namespace lands in the reserved group 0.  Creating and removing
ports/N/ana_groups/128 increments slot 0 on create but decrements slot
128 on release, leaving nvmet_ana_group_enabled[128] at 0xffffffff, so
every subsequent ANA log page reports a group 128 with no namespaces in
the Inaccessible state.

Use NVMET_MAX_ANAGRPS + 1 as the array_index_nospec() bound at both
sites, matching the array's actual size.

Tested on [your -cc-base+ release] (unpatched) and [your -cc-anagrpid+
release] (patched) in an arm64 QEMU guest with nvmet over NVMe/TCP to
127.0.0.1.  Before: ana_grpid written as 128 reads back 0, and the ANA
log after mkdir+rmdir of ana_groups/128 lists group 128 with nnsids 0,
state inaccessible.  After: ana_grpid reads back 128 and the ANA log
lists only group 1.

The issue was found by Claude Opus 5 running Quality Playbook, an
LLM-driven code review tool:
https://github.com/andrewstellman/quality-playbook

Fixes: [from step 3]
Assisted-by: Claude:claude-opus-5 [Quality Playbook]
```

(No Signed-off-by; the operator adds it.)

The `Fixes:` tag is the one thing in this message you cannot copy from anywhere; it
comes from step 3 only. The earlier virtio patch shipped with a wrong one, so this is
the line a reviewer will check hardest.

### Step 5: the report

Write `~/Documents/QPB/evidence/nvmet-anagrpid/RUN-REPORT.md` with these sections:
environment (Mac, QEMU version from `qemu-system-aarch64 --version`, guest kernel and
nvme-cli versions from step 0); the exact commands run; the three verdict lines from
each of `cc-red-base.txt` and `cc-green-anagrpid.txt` plus a pointer to the full files;
the blame chain from step 3 with the diff excerpts; checkpatch and get_maintainer output;
the draft patch filename; every environment fix you made; every deviation from this
runbook; and a final line, either `RESULT: red/green confirmed, draft patch ready` or
`RESULT: stopped at step N` with the reason.

Then `cd ~/Documents/QPB && git add evidence/nvmet-anagrpid && git commit -m "evidence:
nvmet ANAGRPID autopilot run"`. Commit only; no push.

Finish by printing the RESULT line and the report path. Nothing else.
