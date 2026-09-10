# Runbook: confirm and package the nvmet CRTO-from-CAP fix

You are Claude Code running on Andrew Stellman's Mac. Your job is to independently
reproduce one Linux kernel bug in a QEMU guest, confirm that one patch fixes it and
nothing else, trace the bug's origin for a `Fixes:` tag, and package a draft patch email.
You write everything you did and everything you saw into an evidence folder. You do not
send anything anywhere.

You have no memory of the earlier work that set this up. Everything you need is in this
file and the files it names. Read this whole file before running anything.

## The bug, in one paragraph

`drivers/nvme/target/fabrics-cmd.c`, `nvmet_get_property()`, answers a Property Get of
the CRTO register (offset 0x68) with `NVME_CAP_TIMEOUT(ctrl->csts)`. That macro extracts
bits 31:24, which is where the TO field lives in CAP, not in CSTS. CSTS defines only bits
6:0 and nvmet only ever writes RDY, CFS and SHST into it, so the expression is always 0.
The same controller sets CAP.TO = 15 in `core.c` (`ctrl->cap |= (15ULL << 24)`). The spec
(NVMe Base 2.4, Figure 36, CAP.TO) says that when CC.CRIME is 0 the TO field shall be the
CRTO.CRWMT value, so the two registers must agree; nvmet reports 15 and 0. The fix is
`ctrl->cap` in place of `ctrl->csts`. Full write-up with code and spec quotes: `README.md`
in this folder. Do not change the diagnosis or the patch; your job is to test them.

A sibling bug in the same target, the ANAGRPID-128 clamp, has already been through this
process and its patch is on the list (`../nvmet-anagrpid/`). Its two reproducers are used
here as the cross-check that this patch changes nothing else.

## Paths

| what | where |
|---|---|
| evidence folder (you write here) | `~/Documents/QPB/evidence/nvmet-crto/` |
| the patch under test | `~/Documents/QPB/evidence/nvmet-crto/nvmet-crto-from-cap.patch` |
| the other patch (control, do not apply) | `~/Documents/QPB/evidence/nvmet-anagrpid/nvmet-anagrpid-128-nospec.patch` |
| QEMU lab | `~/src/qemu-lab/` |
| ssh into the guest | `bash ~/src/qemu-lab/ssh.sh '<command>'` (runs `<command>` in the guest, echoes output) |
| copy scripts and patches into the guest | `bash ~/src/qemu-lab/scp.sh` |
| reproducer scripts (Mac side) | `~/src/qemu-lab/guest/repro-bug001-crto.sh`, `repro-bug002-anagrpid.sh`, `repro-bug002-analog.sh` |
| kernel build script (Mac side) | `~/src/qemu-lab/guest/build-kernel.sh` |
| full-history kernel clone, for blame | `~/src/linux` (blobless partial clone of torvalds/linux) |
| spec text | `~/Documents/QPB/repos/linux/nvme-target/reference_docs/cite/nvme-base-2.4.txt` |
| the previous run of this process, for shape | `~/Documents/QPB/evidence/nvmet-anagrpid/RUN-REPORT.md` |

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
6. Do not reuse any kernel already installed in the guest (`7.3.0-rc1-qpb+`,
   `-qpb-anagrpid+`, `-qpb-crto+` from the manual run; `-qpb-cc-base+`,
   `-qpb-cc-anagrpid+` from the previous autopilot run). Build your own with the suffixes
   below so this run's evidence stands on its own. The builds are incremental and cheap.
7. No estimates of how long anything will take. Report what finished.
8. Do not touch `~/Documents/QPB/evidence/nvmet-anagrpid/`. It is the record of a patch
   already sent.

## Known traps (each cost time once; the scripts already handle them)

- Ubuntu's kernel does not ship `nvme-loop`; the scripts use NVMe/TCP to `127.0.0.1:4420`.
  The transports (`nvmet-tcp`, `nvme-tcp`) live in `linux-modules-extra`, already
  installed in this guest.
- `build-kernel.sh` disables debug info, strips modules on install, and purges
  `flash-kernel`. Check `df -h /` before each build anyway; below about 8 GB free, remove
  old `/lib/modules/*qpb-cc*` trees from earlier autopilot builds (their evidence is
  already captured; do not remove the manual run's `-qpb+`, `-qpb-anagrpid+`,
  `-qpb-crto+` trees) and re-check. Record what you removed.
- nvme-cli 2.x: the get-property offset flag is `--offset=`, not `-o`. The value is
  printed without a `0x` prefix; the script handles that.
- Reboot takes under a minute; ssh refuses connections until sshd is up. Retry `ssh.sh
  'uname -r'` every 10 seconds for up to 2 minutes rather than assuming failure.
- `ssh.sh` returns the remote command's exit code. The reproducers exit 1 on RED and 0 on
  GREEN by design; do not treat exit 1 as a failure of the command.
- `~/src/linux` is currently on branch `qpb/nvmet-anagrpid` with one commit on top of the
  snapshot. Leave that branch alone; step 4 creates a new one from the snapshot commit.

## Procedure

Save every command's full output. The simplest way: run each `ssh.sh` through
`tee -a ~/Documents/QPB/evidence/nvmet-crto/cc-transcript.txt`.

### Step 0: preflight

```
bash ~/src/qemu-lab/ssh.sh 'uname -r; df -h /; ls /boot | grep vmlinuz; nvme version | head -1'
bash ~/src/qemu-lab/scp.sh
```

Record the output. If the guest is unreachable, stop: the operator has to start it
(`bash ~/src/qemu-lab/run.sh` in a terminal). Do not try to start it yourself.

### Step 1: red on the unpatched snapshot commit

```
bash ~/src/qemu-lab/ssh.sh 'SUFFIX=cc-crto-base bash guest/build-kernel.sh' 2>&1 | tail -5
```

Must end with `installed: 7.3.0-rc1-qpb-cc-crto-base+ and set as GRUB default`. Then:

```
bash ~/src/qemu-lab/ssh.sh 'sudo reboot'
# poll until it answers
bash ~/src/qemu-lab/ssh.sh 'uname -r'
bash ~/src/qemu-lab/ssh.sh 'sudo bash guest/repro-bug002-anagrpid.sh; sudo bash guest/repro-bug002-analog.sh; sudo bash guest/repro-bug001-crto.sh' 2>&1 | tee ~/Documents/QPB/evidence/nvmet-crto/cc-red-base.txt
```

`uname -r` must be exactly `7.3.0-rc1-qpb-cc-crto-base+`; if it is not, stop. Expected
verdicts, in order: RED, RED, RED. The third one is this bug; its raw lines must show
CAP `8200f0003ff` and CRTO `0`. Anything else: stop.

### Step 2: green with only this patch

```
bash ~/src/qemu-lab/ssh.sh 'SUFFIX=cc-crto bash guest/build-kernel.sh patches/nvmet-crto-from-cap.patch' 2>&1 | tail -5
```

The script resets the tree to the snapshot commit before applying, so this kernel
contains only this patch. Must end with `installed: 7.3.0-rc1-qpb-cc-crto+ ...`.
Reboot, confirm `uname -r` is exactly `7.3.0-rc1-qpb-cc-crto+`, run the same three
scripts in the same order, save to `cc-green-crto.txt`. Expected verdicts: RED, RED,
GREEN. The two leading REDs are the cross-check: the ANAGRPID defect is untouched by
this patch, and their output must match the base run line for line apart from the
kernel string. The GREEN must show CRTO `f` and `CAP.TO = 15   CRTO.CRWMT = 15`.
Anything else: stop.

### Step 3: trace the origin for `Fixes:`, and check the message's claims

In `~/src/linux` (on the Mac, not the guest). This clone is blobless, so the first blame
on a file pulls its history from GitHub; that is expected and can take a minute.

```
cd ~/src/linux
git blame -L 67,69 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/fabrics-cmd.c
```

That is the `case NVME_REG_CRTO:` block. For the blamed commit, run
`git show <sha> -- drivers/nvme/target/fabrics-cmd.c` and answer, with the diff excerpt
pasted: did this commit introduce `NVME_CAP_TIMEOUT(ctrl->csts)`, or did it move or
reformat a line that already had it? If it moved it, follow the history back
(`git log --oneline -S'NVME_CAP_TIMEOUT(ctrl->csts)' -- drivers/nvme/target/fabrics-cmd.c`)
until you find the commit that introduced the expression. The `Fixes:` tag names the
introducing commit. Write the full chain of reasoning into the report; a reviewer will
check it.

Format the tag with `git log -1 --format='Fixes: %h ("%s")' <sha>` (12-character hash).

Then verify the three factual claims the commit message makes, and paste what you find:

```
git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c:include/linux/nvme.h | grep -n 'NVME_CAP_TIMEOUT\|NVME_CSTS_\|NVME_CAP_CRMS'
git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c:drivers/nvme/target/core.c | grep -n 'ctrl->csts\|15ULL << 24'
git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c:drivers/nvme/host/core.c | grep -n -B4 -A10 'NVME_REG_CRTO'
```

The first two support "CSTS gets only RDY, CFS and SHST; CAP.TO is set to 15". The third
is for the sentence about the Linux host: it should show that the host reads CRTO only
under a `NVME_CAP_CRMS_CRWMS` (or CRIMS) check. If the host source does not say that,
drop that paragraph from the message and say so in the report; do not keep a sentence
the source does not support.

### Step 4: package the patch

```
cd ~/src/linux
git status --short            # must be empty; if not, stop and report
git checkout -q -b qpb/nvmet-crto 4d7d9486c04d917265f64c55bd23b2cc4fe7749c
git apply --check ~/Documents/QPB/evidence/nvmet-crto/nvmet-crto-from-cap.patch
git apply ~/Documents/QPB/evidence/nvmet-crto/nvmet-crto-from-cap.patch
git diff
./scripts/get_maintainer.pl -f drivers/nvme/target/fabrics-cmd.c
```

Commit with the message below, filling in the `Fixes:` line from step 3 and the
kernel release strings from your own runs. Author is
`Andrew Stellman <astellman@stellman-greene.com>`; check `git config user.name` and
`user.email` in `~/src/linux` and set them for this repo only if they differ.
Do NOT add a Signed-off-by line and do not use `git commit -s`:
`Documentation/process/coding-assistants.rst` says AI agents must not add
Signed-off-by; the operator adds it when amending before sending. Then:

```
git commit -F <message file>
./scripts/checkpatch.pl --strict -g HEAD
git format-patch -1 --base=4d7d9486c04d917265f64c55bd23b2cc4fe7749c -o ~/Documents/QPB/evidence/nvmet-crto/
```

Rename the output to `DRAFT-0001-nvmet-....patch`. Paste the checkpatch and
get_maintainer output into the report. checkpatch must be clean; if it warns, fix the
message (not the diff) and re-run. The 75-column rule applies to every body line
including the URL. Do not send it.

Commit message. Keep the shape; replace the bracketed parts; drop the host paragraph if
step 3 did not support it; do not add claims that are not in your logs:

```
nvmet: derive the CRTO property from CAP, not CSTS

nvmet_get_property() answers a Property Get of CRTO with
NVME_CAP_TIMEOUT(ctrl->csts).  NVME_CAP_TIMEOUT() extracts bits 31:24,
which is the TO field of CAP.  CSTS defines only bits 6:0 and nvmet
writes only RDY, CFS and SHST into it, so the result is always 0.  The
same controller sets CAP.TO to 15 in nvmet_init_ctrl().

NVMe Base Specification 2.4, Figure 36 (CAP), says that when CC.CRIME
is '0' the TO field "shall be set to: a) the value in the Controller
Ready With Media Timeout (CRTO.CRWMT) field; or b) FFh if the value in
the CRTO.CRWMT field is greater than FFh."  nvmet reports 15 in CAP.TO
and 0 in CRTO.CRWMT.

Take the value from ctrl->cap, where the timeout is actually stored.

The Linux host reads CRTO only when CAP.CRMS.CRWMS is set, which nvmet
does not advertise, so Linux initiators have not seen the wrong value.
A host that reads the property directly does, for example nvme-cli's
get-property.  Advertising CRWMS is a separate change.

Tested on [your -cc-crto-base+ release] (unpatched) and [your -cc-crto+
release] (patched) in an arm64 QEMU guest with nvmet over NVMe/TCP to
127.0.0.1, reading the properties with nvme get-property.  Before: CAP
reads 0x8200f0003ff (TO = 15) and CRTO reads 0.  After: CAP is
unchanged and CRTO reads 0xf, so CRWMT = 15 = CAP.TO.

The issue was found by Claude Opus 5 running Quality Playbook, an
LLM-driven code review tool:
https://github.com/andrewstellman/quality-playbook

Fixes: [from step 3]
Assisted-by: Claude:claude-opus-5 [Quality Playbook]
```

(No Signed-off-by; the operator adds it.)

The `Fixes:` tag is the one thing in this message you cannot copy from anywhere; it
comes from step 3 only. An earlier patch from this project shipped with a wrong one, so
this is the line a reviewer will check hardest.

### Step 5: the report

Write `~/Documents/QPB/evidence/nvmet-crto/RUN-REPORT.md` with these sections:
environment (Mac, QEMU version from `qemu-system-aarch64 --version`, guest kernel and
nvme-cli versions from step 0); the exact commands run; the three verdict lines from
each of `cc-red-base.txt` and `cc-green-crto.txt` plus a pointer to the full files; the
blame chain from step 3 with the diff excerpts; the three claim checks from step 3 with
the grep output; checkpatch and get_maintainer output; the draft patch filename; every
environment fix you made; every deviation from this runbook; and a final line, either
`RESULT: red/green confirmed, draft patch ready` or `RESULT: stopped at step N` with
the reason.

Then `cd ~/Documents/QPB && git add evidence/nvmet-crto && git commit -m "evidence:
nvmet CRTO autopilot run"`. Commit only; no push.

Finish by printing the RESULT line and the report path. Nothing else.
