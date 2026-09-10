# RUN-REPORT: nvmet CRTO-from-CAP autopilot run (Claude Code, 2026-09-10)

Runbook: [RUNBOOK.md](./RUNBOOK.md). Full command transcript, including every build log:
[cc-transcript.txt](./cc-transcript.txt).

## Environment

| item | value |
|---|---|
| host | macOS 26.3 (25D125), arm64 |
| QEMU | `QEMU emulator version 11.1.1` (`qemu-system-aarch64 --version`) |
| guest kernel at step 0 | `7.3.0-rc1-qpb-cc-anagrpid+` (left over from the previous autopilot run; not used for any evidence) |
| guest root fs at step 0 | `/dev/vda1 58G 12G 46G 21% /` |
| nvme-cli | `nvme version 2.8 (git 2.8)` |
| snapshot commit | `4d7d9486c04d917265f64c55bd23b2cc4fe7749c` (v7.3-rc1) |

Step 0 output, verbatim:

```
7.3.0-rc1-qpb-cc-anagrpid+
Filesystem      Size  Used Avail Use% Mounted on
/dev/vda1        58G   12G   46G  21% /
vmlinuz
vmlinuz-6.8.0-138-generic
vmlinuz-6.8.0-139-generic
vmlinuz-7.3.0-rc1-qpb+
vmlinuz-7.3.0-rc1-qpb-anagrpid+
vmlinuz-7.3.0-rc1-qpb-cc-anagrpid+
vmlinuz-7.3.0-rc1-qpb-cc-base+
vmlinuz-7.3.0-rc1-qpb-crto+
vmlinuz.old
nvme version 2.8 (git 2.8)
$ bash ~/src/qemu-lab/scp.sh
[exit 0]
```

Before starting, confirmed that the evidence-folder copies of `build-kernel.sh`,
`repro-bug001-crto.sh` and `nvmet-crto-from-cap.patch` are byte-identical to the
`~/src/qemu-lab/guest/` and `~/src/qemu-lab/patches/` copies that were scp'd and run
(`diff` reported no differences).

## Commands run

In order. Every `ssh.sh` invocation and its full output is in
[cc-transcript.txt](./cc-transcript.txt).

```
# step 0 (Mac)
bash ~/src/qemu-lab/ssh.sh 'uname -r; df -h /; ls /boot | grep vmlinuz; nvme version | head -1'
bash ~/src/qemu-lab/scp.sh
qemu-system-aarch64 --version; sw_vers
cd ~/src/linux; git status --short; git config user.name; git config user.email

# step 1
bash ~/src/qemu-lab/ssh.sh 'SUFFIX=cc-crto-base bash guest/build-kernel.sh'     # failed: /boot full
bash ~/src/qemu-lab/ssh.sh 'df -h / /boot ...; sudo du -sh /lib/modules/*; ls -la /boot'
bash ~/src/qemu-lab/ssh.sh 'grep ^GRUB_DEFAULT /etc/default/grub; sudo rm -fv /boot/{vmlinuz,initrd.img,System.map,config}-7.3.0-rc1-qpb-cc-{base,anagrpid}+; ls -d /lib/modules/*qpb-cc*; df -h /boot /'
bash ~/src/qemu-lab/ssh.sh 'SUFFIX=cc-crto-base bash guest/build-kernel.sh'     # re-run, unchanged
bash ~/src/qemu-lab/ssh.sh 'sudo reboot'
bash ~/src/qemu-lab/ssh.sh 'uname -r'                      # polled every 10 s; first attempt answered
bash ~/src/qemu-lab/ssh.sh 'sudo bash guest/repro-bug002-anagrpid.sh; sudo bash guest/repro-bug002-analog.sh; sudo bash guest/repro-bug001-crto.sh' 2>&1 | tee cc-red-base.txt

# step 3 (Mac, ~/src/linux; run while the step 1 build was compiling)
git blame -L 67,69 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/fabrics-cmd.c
git show 1e058089d28f5 -- drivers/nvme/target/fabrics-cmd.c
git log --oneline -S'NVME_CAP_TIMEOUT(ctrl->csts)' 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/fabrics-cmd.c
git log --oneline -S'NVME_REG_CRTO' 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/
git describe --contains 1e058089d28f5
git merge-base --is-ancestor 1e058089d28f5 4d7d9486c04d917265f64c55bd23b2cc4fe7749c
git log -1 --abbrev=12 --format='Fixes: %h ("%s")' 1e058089d28f5
git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c:include/linux/nvme.h | grep -n 'NVME_CAP_TIMEOUT\|NVME_CSTS_\|NVME_CAP_CRMS'
git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c:drivers/nvme/target/core.c | grep -n 'ctrl->csts\|15ULL << 24'
git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c:drivers/nvme/host/core.c | grep -n -B4 -A10 'NVME_REG_CRTO'
grep -n ... ~/Documents/QPB/repos/linux/nvme-target/reference_docs/cite/nvme-base-2.4.txt

# step 2
bash ~/src/qemu-lab/ssh.sh 'df -h / /boot; ls -la /boot; ls /lib/modules; grep ^GRUB_DEFAULT /etc/default/grub'
bash ~/src/qemu-lab/ssh.sh 'cmp ...; sudo rm -fv /boot/{vmlinuz,System.map,config}-7.3.0-rc1-qpb-cc-crto-base+.old; df -h /boot'
bash ~/src/qemu-lab/ssh.sh 'SUFFIX=cc-crto bash guest/build-kernel.sh patches/nvmet-crto-from-cap.patch'
bash ~/src/qemu-lab/ssh.sh 'sudo reboot'
bash ~/src/qemu-lab/ssh.sh 'uname -r'                      # polled every 10 s; first attempt answered
bash ~/src/qemu-lab/ssh.sh 'sudo bash guest/repro-bug002-anagrpid.sh; sudo bash guest/repro-bug002-analog.sh; sudo bash guest/repro-bug001-crto.sh' 2>&1 | tee cc-green-crto.txt
diff <(sed 's/<base release>/KERNEL/' cc-red-base.txt) <(sed 's/<patched release>/KERNEL/' cc-green-crto.txt)

# step 4 (Mac, ~/src/linux)
git status --short            # 13 modified files -> stop, per the runbook
```

## Step 1: red on unpatched 4d7d9486 (`cc-red-base.txt`)

The first build attempt failed at `make install`, while generating the initramfs:

```
update-initramfs: Generating /boot/initrd.img-7.3.0-rc1-qpb-cc-crto-base+
zstd: error 70 : Write error : cannot write block : No space left on device 
E: mkinitramfs failure cpio 141
E: mkinitramfs failure zstd -q -1 -T0 70
update-initramfs: failed for /boot/initrd.img-7.3.0-rc1-qpb-cc-crto-base+ with 1.
run-parts: /etc/kernel/postinst.d/initramfs-tools exited with return code 1
make[1]: *** [arch/arm64/Makefile:196: install] Error 1
make: *** [Makefile:248: __sub-make] Error 2
[exit 2]
```

The cause was `/boot`, not `/`. See environment fix 1. After the fix, the same command,
unchanged, ended with:

```
installed: 7.3.0-rc1-qpb-cc-crto-base+ and set as GRUB default. Reboot (sudo reboot) and check uname -r.
[exit 0]
```

After `sudo reboot`, the first `uname -r` poll (10 s after the reboot command returned)
answered `7.3.0-rc1-qpb-cc-crto-base+`, exactly as required.

Verdict lines, in order:

```
RED: 128 became 0 (reserved ANAGRPID) — bug present
RED: ANA log reports group 128 after it was removed — counter wrapped
RED: CRTO reads 0 while CAP.TO = 15 — bug present
```

Expected RED, RED, RED; got RED, RED, RED (exit 1 from the last script, the CRTO RED, by
design). Full output: [cc-red-base.txt](./cc-red-base.txt). The CRTO block, verbatim:

```
kernel: 7.3.0-rc1-qpb-cc-crto-base+   controller: /dev/nvme0
nvme-cli: nvme version 2.8 (git 2.8)
--- raw CAP:
property: 0x00 (Controller Capabilities), value: 8200f0003ff
--- raw CRTO:
property: 0x68 (Unknown), value: 0
CAP  = 0x8200f0003ff
CRTO = 0x0
CAP.TO = 15   CRTO.CRWMT = 0
RED: CRTO reads 0 while CAP.TO = 15 — bug present
```

Raw CAP `8200f0003ff` and raw CRTO `0`, as the runbook requires.

## Step 2: green with only the CRTO patch (`cc-green-crto.txt`)

Before the build, `/boot` had 119M free, not enough for one more kernel. See environment
fix 2, after which `/boot` had 186M free. The build applied only this patch on top of
the reset snapshot tree:

```
== applying /home/lab/patches/nvmet-crto-from-cap.patch
 drivers/nvme/target/fabrics-cmd.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
...
installed: 7.3.0-rc1-qpb-cc-crto+ and set as GRUB default. Reboot (sudo reboot) and check uname -r.
[exit 0]
```

After `sudo reboot`, the first `uname -r` poll answered `7.3.0-rc1-qpb-cc-crto+`,
exactly as required.

Verdict lines, in order:

```
RED: 128 became 0 (reserved ANAGRPID) — bug present
RED: ANA log reports group 128 after it was removed — counter wrapped
GREEN: CRTO.CRWMT matches CAP.TO
```

Expected RED, RED, GREEN; got RED, RED, GREEN (exit 0 from the last script). Full
output: [cc-green-crto.txt](./cc-green-crto.txt). The CRTO block, verbatim:

```
kernel: 7.3.0-rc1-qpb-cc-crto+   controller: /dev/nvme0
nvme-cli: nvme version 2.8 (git 2.8)
--- raw CAP:
property: 0x00 (Controller Capabilities), value: 8200f0003ff
--- raw CRTO:
property: 0x68 (Unknown), value: f
CAP  = 0x8200f0003ff
CRTO = 0xf
CAP.TO = 15   CRTO.CRWMT = 15
GREEN: CRTO.CRWMT matches CAP.TO
```

CRTO reads `f`, and the summary line is `CAP.TO = 15   CRTO.CRWMT = 15`, as the runbook
requires. CAP is unchanged from the base run (`8200f0003ff`).

**Cross-check.** The runbook requires the two leading REDs to match the base run line for
line, apart from the kernel string. Both files are 32 lines. With each run's release
string replaced by `KERNEL`, the first 21 lines, which are the complete output of the two
ANAGRPID scripts, are identical (`diff` exit 0). Over the whole file, the only differences
are the four CRTO lines:

```
28c28
< property: 0x68 (Unknown), value: 0
---
> property: 0x68 (Unknown), value: f
30,32c30,32
< CRTO = 0x0
< CAP.TO = 15   CRTO.CRWMT = 0
< RED: CRTO reads 0 while CAP.TO = 15 — bug present
---
> CRTO = 0xf
> CAP.TO = 15   CRTO.CRWMT = 15
> GREEN: CRTO.CRWMT matches CAP.TO
[diff exit 1]
```

The ANAGRPID defect is untouched by this patch. `ana_grpid` written as 128 reads back 0,
and the ANA log shows `ngrps : 2` with a `grpid : 128`, `nnsids : 0`,
`state : inaccessible` descriptor, identical to the base run.

## Step 3: origin of the bug, for `Fixes:`

Blame at the snapshot commit, the whole `case NVME_REG_CRTO:` block:

```
$ git blame -L 67,69 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/fabrics-cmd.c
1e058089d28f5 (Keith Busch 2024-11-04 14:17:59 -0800 67) 		case NVME_REG_CRTO:
1e058089d28f5 (Keith Busch 2024-11-04 14:17:59 -0800 68) 			val = NVME_CAP_TIMEOUT(ctrl->csts);
1e058089d28f5 (Keith Busch 2024-11-04 14:17:59 -0800 69) 			break;
[exit 0]
```

All three lines blame to `1e058089d28f5`. Its diff to `fabrics-cmd.c`, in full
(`git show 1e058089d28f5 -- drivers/nvme/target/fabrics-cmd.c`):

```
commit 1e058089d28f58bd194d3c0f06512f42079f5a1d
Author: Keith Busch <kbusch@kernel.org>
Date:   Mon Nov 4 14:17:59 2024 -0800

    nvmet: implement crto property
    
    This property is required for nvme 2.1. The target only supports ready
    with media, so this is just the same value as CAP.TO.
    
    Reviewed-by: Christoph Hellwig <hch@lst.de>
    Reviewed-by: Matias Bjørling <matias.bjorling@wdc.com>
    Signed-off-by: Keith Busch <kbusch@kernel.org>

diff --git a/drivers/nvme/target/fabrics-cmd.c b/drivers/nvme/target/fabrics-cmd.c
index 28a84af1b4c0..c49904ebb6c2 100644
--- a/drivers/nvme/target/fabrics-cmd.c
+++ b/drivers/nvme/target/fabrics-cmd.c
@@ -64,6 +64,9 @@ static void nvmet_execute_prop_get(struct nvmet_req *req)
 		case NVME_REG_CSTS:
 			val = ctrl->csts;
 			break;
+		case NVME_REG_CRTO:
+			val = NVME_CAP_TIMEOUT(ctrl->csts);
+			break;
 		default:
 			status = NVME_SC_INVALID_FIELD | NVME_STATUS_DNR;
 			break;
[exit 0]
```

Did this commit introduce `NVME_CAP_TIMEOUT(ctrl->csts)`, or move or reformat a line
that already had it? It introduced it. The reasoning:

1. The whole `case NVME_REG_CRTO:` block is three pure `+` lines. The hunk has no `-`
   lines, so no existing line was moved or reformatted. The hunk header shows 6 lines
   before and 9 after, a net gain of exactly those three lines.
2. Before this commit, `nvmet_execute_prop_get()` had no `NVME_REG_CRTO` case at all: the
   context goes straight from `NVME_REG_CSTS` to `default:`. So there was no earlier
   CRTO handler for the expression to have moved from.
3. The pickaxe history finds one commit, up to the snapshot, for both the exact expression
   and, more broadly, any `NVME_REG_CRTO` use anywhere in the target:

   ```
   $ git log --oneline -S'NVME_CAP_TIMEOUT(ctrl->csts)' 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/fabrics-cmd.c
   1e058089d28f nvmet: implement crto property
   [exit 0]
   $ git log --oneline -S'NVME_REG_CRTO' 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/
   1e058089d28f5 nvmet: implement crto property
   [exit 0]
   ```

   So no later commit added or removed the expression. Blame at the snapshot still names
   `1e058089d28f5` for all three lines, so nothing rewrote them afterwards either (they
   moved from line 67 of the new side of the hunk only by context, not by edit).
4. The commit's own message says the intent was "just the same value as CAP.TO". The
   code reads CSTS instead, so the defect is in the introducing commit itself, not a
   later regression.

There was no move to follow back; the chain ends at the first commit. Supporting checks:

```
$ git describe --contains 1e058089d28f5
v6.13-rc1~211^2~11^2~10
$ git merge-base --is-ancestor 1e058089d28f5 4d7d9486c04d917265f64c55bd23b2cc4fe7749c
[ancestor exit 0]
```

The tag, formatted with `git log -1 --abbrev=12 --format='Fixes: %h ("%s")' 1e058089d28f5`:

```
Fixes: 1e058089d28f ("nvmet: implement crto property")
```

### Claim checks for the commit message

**Claim 1:** "NVME_CAP_TIMEOUT() extracts bits 31:24 ... CSTS defines only bits 6:0".

```
$ git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c:include/linux/nvme.h | grep -n 'NVME_CAP_TIMEOUT\|NVME_CSTS_\|NVME_CAP_CRMS'
166:#define NVME_CAP_TIMEOUT(cap)	(((cap) >> 24) & 0xff)
253:	NVME_CSTS_RDY		= 1 << 0,
254:	NVME_CSTS_CFS		= 1 << 1,
255:	NVME_CSTS_NSSRO		= 1 << 4,
256:	NVME_CSTS_PP		= 1 << 5,
257:	NVME_CSTS_SHST_NORMAL	= 0 << 2,
258:	NVME_CSTS_SHST_OCCUR	= 1 << 2,
259:	NVME_CSTS_SHST_CMPLT	= 2 << 2,
260:	NVME_CSTS_SHST_MASK	= 3 << 2,
274:	NVME_CAP_CRMS_CRWMS	= 1ULL << 59,
275:	NVME_CAP_CRMS_CRIMS	= 1ULL << 60,
```

`NVME_CAP_TIMEOUT(x)` is `(x >> 24) & 0xff`, bits 31:24. Every `NVME_CSTS_*` bit Linux
defines is at bit 5 or below. The header does not define bit 6 (ST), so the "bits 6:0"
figure comes from the spec rather than this header. Either way, nothing sits at 24 or
above. Supported.

**Claim 2:** "nvmet writes only RDY, CFS and SHST into it ... sets CAP.TO to 15 in
nvmet_init_ctrl()".

```
$ git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c:drivers/nvme/target/core.c | grep -n 'ctrl->csts\|15ULL << 24'
1399:		ctrl->csts = NVME_CSTS_CFS;
1406:		ctrl->csts = NVME_CSTS_CFS;
1410:	ctrl->csts = NVME_CSTS_RDY;
1427:	ctrl->csts &= ~NVME_CSTS_RDY;
1445:		ctrl->csts |= NVME_CSTS_SHST_CMPLT;
1448:		ctrl->csts &= ~NVME_CSTS_SHST_CMPLT;
1460:	ctrl->cap |= (15ULL << 24);
1522:	if (unlikely(!(req->sq->ctrl->csts & NVME_CSTS_RDY))) {
1789:	if (!(ctrl->csts & NVME_CSTS_CFS)) {
1790:		ctrl->csts |= NVME_CSTS_CFS;
```

Every write to `ctrl->csts` uses `NVME_CSTS_CFS`, `NVME_CSTS_RDY` or
`NVME_CSTS_SHST_CMPLT`; lines 1522 and 1789 are reads. Line 1460 sets CAP.TO = 15.

**The function name in the draft message is wrong.** Line 1460 is in `nvmet_init_cap()`,
not `nvmet_init_ctrl()`. The snapshot's `core.c` has no function named
`nvmet_init_ctrl`:

```
$ git show 4d7d9486...:drivers/nvme/target/core.c | awk '<nearest function header above line N>'
1453: static void nvmet_init_cap(struct nvmet_ctrl *ctrl)
1460: 	ctrl->cap |= (15ULL << 24);
$ git show 4d7d9486...:drivers/nvme/target/core.c | grep -n '^[a-z].*nvmet_init_cap\|^[a-z].*nvmet_init_ctrl\|nvmet_init_cap(ctrl)'
1453:static void nvmet_init_cap(struct nvmet_ctrl *ctrl)
1650:	nvmet_init_cap(ctrl);
$ (same awk, line 1650)
1594: struct nvmet_ctrl *nvmet_alloc_ctrl(struct nvmet_alloc_ctrl_args *args)
1650: 	nvmet_init_cap(ctrl);
```

`nvmet_init_cap()` is called from `nvmet_alloc_ctrl()`. The CSTS part of the claim and
the CAP.TO = 15 part are supported. The sentence should say "in nvmet_init_cap()". The
runbook says not to keep a claim the source does not support, so I would have made that
one-word correction to the message when committing. The run stopped at step 4 before
any commit (see step 4), so no message was produced with either name.

**Claim 3:** the Linux-host paragraph, "The Linux host reads CRTO only when CAP.CRMS.CRWMS
is set".

```
$ git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c:drivers/nvme/host/core.c | grep -n -B4 -A10 'NVME_REG_CRTO'
2814-	timeout = NVME_CAP_TIMEOUT(ctrl->cap);
2815-	if (ctrl->cap & NVME_CAP_CRMS_CRWMS) {
2816-		u32 crto, ready_timeout;
2817-
2818:		ret = ctrl->ops->reg_read32(ctrl, NVME_REG_CRTO, &crto);
2819-		if (ret) {
2820-			dev_err(ctrl->device, "Reading CRTO failed (%d)\n",
2821-				ret);
2822-			return ret;
2823-		}
2824-
2825-		/*
2826-		 * CRTO should always be greater or equal to CAP.TO, but some
2827-		 * devices are known to get this wrong. Use the larger of the
2828-		 * two values.
```

The only `NVME_REG_CRTO` read in the host core is inside `if (ctrl->cap &
NVME_CAP_CRMS_CRWMS)`. Supported, so the paragraph would stay. That nvmet does not
advertise CRWMS is also shown by the measured CAP: `0x8200f0003ff` has bits 60:59 = 00b.

**Spec quote**, checked against the local spec text
(`nvme-base-2.4.txt`, lines 4483–4489, inside Figure 36 "Offset 0h: CAP – Controller
Capabilities", bits 31:24):

```
                             If the Controller Ready Independent of Media Enable (CC.CRIME) bit is cleared to
                             ‘0’ and the worst-case time for the CSTS.RDY bit to change state is due to enabling
                             the controller after the CC.EN bit transitions from ‘0’ to ‘1’, then this field shall be
                             set to:
                                 a)   the value in the Controller Ready With Media Timeout (CRTO.CRWMT)
                                      field; or
                     Impl        b)   FFh if the value in the CRTO.CRWMT field is greater than FFh.
   31:24      RO
```

The quoted words match the spec.

## Step 4: packaging, stopped

The runbook's first step 4 command is `git status --short`, with the instruction "must be
empty; if not, stop and report". In `~/src/linux`, run at its place in the sequence
(after steps 1–3 had passed):

```
$ git status --short
 M include/uapi/linux/netfilter/xt_CONNMARK.h
 M include/uapi/linux/netfilter/xt_DSCP.h
 M include/uapi/linux/netfilter/xt_MARK.h
 M include/uapi/linux/netfilter/xt_RATEEST.h
 M include/uapi/linux/netfilter/xt_TCPMSS.h
 M include/uapi/linux/netfilter_ipv4/ipt_ECN.h
 M include/uapi/linux/netfilter_ipv4/ipt_TTL.h
 M include/uapi/linux/netfilter_ipv6/ip6t_HL.h
 M net/netfilter/xt_DSCP.c
 M net/netfilter/xt_HL.c
 M net/netfilter/xt_RATEEST.c
 M net/netfilter/xt_TCPMSS.c
 M tools/memory-model/litmus-tests/Z6.0+pooncelock+poonceLock+pombonce.litmus
[exit 0]
count: 13
```

It is not empty, so the run stops here.

### Stopped

What the 13 files are. The same 13 files were already modified at step 0, before this run
touched anything, and the previous run's report (deviation 4 there) records the same set.
The repo has `core.ignorecase=true`, and each of these paths is one half of a pair that git
tracks twice, differing only in case. For example, `git ls-files` lists both
`include/uapi/linux/netfilter/xt_CONNMARK.h` and `xt_connmark.h`, and both `xt_DSCP.h` and
`xt_dscp.h`. The case-insensitive macOS filesystem can hold only one file per pair, so one
side always shows as modified. I did not modify these files, and a checkout cannot clean
them on this filesystem.

What was not done, because of the stop: the `qpb/nvmet-crto` branch was not created, the
patch was not applied in `~/src/linux`, and there was no commit, no checkpatch, no
get_maintainer and no format-patch. There is no `DRAFT-0001-*.patch` in this folder. The
branch `qpb/nvmet-anagrpid` was left exactly as it was.

What packaging would need. The runbook's requirement is a clean tree, and on this
filesystem the only way to meet it is a different tree. Examples: a checkout on a
case-sensitive APFS volume; a worktree with sparse-checkout excluding the colliding
paths; or a waiver of the check for these 13 known paths, as the previous run took. That
is the operator's call; I did not choose among them. Everything the packaging step needs
from this run is recorded above:
- the `Fixes:` tag, `Fixes: 1e058089d28f ("nvmet: implement crto property")`
- the release strings `7.3.0-rc1-qpb-cc-crto-base+` (unpatched) and
  `7.3.0-rc1-qpb-cc-crto+` (patched)
- the claim checks: the host paragraph is supported and stays, and the function name
  `nvmet_init_ctrl()` must become `nvmet_init_cap()`

## Environment fixes

1. **Guest `/boot` full (step 1).** The guest has a separate 891M `/boot` partition
   (`/dev/vda16`). The first step 1 build failed with `zstd: error 70 : ... No space left
   on device` while writing the initramfs. At that point `df` showed
   `/dev/vda16 891M 835M 0 100% /boot`, while `/` still had 46G free. Each 7.3 kernel
   takes about 126M in `/boot` (vmlinuz 58M, initrd 58M, System.map 9M, config 0.4M).
   The runbook's trap covers old `/lib/modules/*qpb-cc*` trees on `/`. I applied the same
   rule to `/boot`: I removed the `/boot` files of the two earlier autopilot kernels and
   of nothing else. Removed, from `rm -v`:

   ```
   removed '/boot/vmlinuz-7.3.0-rc1-qpb-cc-base+'
   removed '/boot/initrd.img-7.3.0-rc1-qpb-cc-base+'
   removed '/boot/System.map-7.3.0-rc1-qpb-cc-base+'
   removed '/boot/config-7.3.0-rc1-qpb-cc-base+'
   removed '/boot/vmlinuz-7.3.0-rc1-qpb-cc-anagrpid+'
   removed '/boot/initrd.img-7.3.0-rc1-qpb-cc-anagrpid+'
   removed '/boot/System.map-7.3.0-rc1-qpb-cc-anagrpid+'
   removed '/boot/config-7.3.0-rc1-qpb-cc-anagrpid+'
   ```

   Afterwards `/boot` showed 244M free. The manual run's kernels (`-qpb+`,
   `-qpb-anagrpid+`, `-qpb-crto+`) and the stock `6.8.0-138/139-generic` kernels were
   left in place. `-qpb-cc-anagrpid+` was the running kernel at the time. Its files were
   no longer needed, since the reboot went into the new build, but GRUB_DEFAULT still
   named it until the re-run build reset it to `-qpb-cc-crto-base+`.

   Observation, not a change I made: when I first listed `/lib/modules` (after the failed
   build), it held only `6.8.0-138-generic`, `6.8.0-139-generic` and this run's
   `7.3.0-rc1-qpb-cc-crto-base+`. The module trees of the manual run and of the earlier
   autopilot run were already gone. `build-kernel.sh` removes only
   `/lib/modules/<its own release>`, so they were removed outside this run. I removed no
   `/lib/modules` tree.

2. **Leftover `.old` files from the failed install (step 2).** Before the step 2 build,
   `/boot` had 119M free, less than one kernel install needs. The re-run install in step 1
   had renamed the failed attempt's files to `*.old`. `cmp` showed the vmlinuz identical to
   the installed one (`vmlinuz-identical`), and I removed those three files:

   ```
   removed '/boot/vmlinuz-7.3.0-rc1-qpb-cc-crto-base+.old'
   removed '/boot/System.map-7.3.0-rc1-qpb-cc-crto-base+.old'
   removed '/boot/config-7.3.0-rc1-qpb-cc-crto-base+.old'
   ```

   `/boot` then showed 186M free. This leaves the dangling symlink `/boot/vmlinuz.old`,
   which the next `make install` replaces.

3. **Orphaned `~/Documents/QPB/.git/HEAD.lock`.** It was found before the step 5 commit,
   and it is the same pattern the previous run recorded. Diagnosis before touching it:
   - The file was 0 bytes, inode 511308222, born and modified `Sep 10 12:13:29 2026`.
   - The reflog records `bd28617 HEAD@{2026-09-10 12:13:29 -0400}: commit: evidence:
     nvmet CRTO autopilot runbook` as complete. `.git/logs/HEAD` and
     `.git/refs/heads/1.6.1` were both modified at `12:13:29`.
   - No `git` process was running, and `lsof` showed no open handle on the file.

   Conclusion: an orphaned lock from a completed commit. I removed it with `/bin/rm -f`,
   only after checking in the same command that it was still inode 511308222 and still
   empty (`removed inode 511308222`).

4. **Concurrent commit in `~/Documents/QPB` during this run (not a fix; I left it
   alone).** The first attempt at the step 5 commit failed:

   ```
   fatal: Unable to create '/Users/andrewstellman/Documents/QPB/.git/index.lock': File exists.
   ```

   A new `.git/HEAD.lock` (inode 511334699, born 12:32:49) and `.git/index.lock` (inode
   511334758, born 12:33:13) had appeared, both 0 bytes. Both were held read-only
   (`*308r`, `*386r`) by pid 64242, `com.apple.Virtualization.VirtualMachine`, the Cowork
   VM that mounts this folder. No git process was running on the host. The reflog showed
   that another session had committed during this run:

   ```
   e8d4937 HEAD@{2026-09-10 12:32:49 -0400}: commit: evidence: document the method (roles, pipeline, rules, virtio lessons); refresh bug READMEs
   ```

   Because another session had been active in the repo minutes earlier, I did not
   remove either lock. When I re-checked at 12:36:45, both were gone, and I had not
   removed them. The commit was then retried.

   What `e8d4937` did to this folder (`git show --name-status e8d4937 -- evidence/nvmet-crto/`):

   ```
   M	evidence/nvmet-crto/README.md
   A	evidence/nvmet-crto/cc-red-base.txt
   A	evidence/nvmet-crto/cc-transcript.txt
   ```

   - `cc-red-base.txt` was committed mid-run by the other session. It has not changed
     since, so the committed copy is this run's step 1 output as written.
   - `cc-transcript.txt` was committed as a partial snapshot. It has grown since, and this
     run's commit carries the complete version.
   - `README.md` gained a `## Status` section, which I did not write and did not change:
     "Manual red/green confirmed (below). Not yet sent. Next: the autopilot run from
     RUNBOOK.md, then the three-reviewer panel, then send."
   - `RUNBOOK.md` was not touched, so the runbook I followed is the committed `bd28617`
     version.

   Nothing under `evidence/nvmet-anagrpid/` was touched by this run. `e8d4937` itself
   changed `evidence/nvmet-anagrpid/README.md`, which is the other session's work, not
   this run's.

## Deviations from the runbook

1. The runbook pipes each build to `tail -5`. I kept that, and also saved the full build
   output to `cc-transcript.txt`, which is where the error context above comes from.
2. The step 1 build command was run twice. The first run failed on `/boot` space, and
   the second, unchanged, ran after environment fix 1. No reproducer was retried.
3. Step 3 ran on the Mac while the step 1 kernel was compiling in the guest. `git log -S`
   used the snapshot commit as the explicit revision rather than the checked-out HEAD, so
   the history is exactly that of the tested tree. I added a second, broader pickaxe
   (`-S'NVME_REG_CRTO'` over all of `drivers/nvme/target/`), `git describe --contains`,
   `git merge-base --is-ancestor`, and a check of the spec quote against
   `nvme-base-2.4.txt`. The `Fixes:` format command has an explicit `--abbrev=12` to
   guarantee the 12-character hash.
4. The runbook's `df -h /` check before each build does not cover `/boot`, which is what
   actually filled. From step 2 on I checked `df -h / /boot`.
5. The reboot poll sleeps 10 s before the first `uname -r` attempt instead of trying
   immediately.
6. The step 4 `git status --short` check was also run at step 0 and once more during the
   step 2 build (both read-only), before its place in the sequence. See step 4.
   The in-sequence run gave the same 13 files as both earlier runs.
7. After the stop at step 4, I still carried out step 5's report and evidence commit
   (`git add evidence/nvmet-crto && git commit`, no push). Step 5 is where the
   `RESULT: stopped at step N` line is defined, and committing preserves this run's
   evidence. The runbook says this folder is where this run writes.

## Result

Steps 0–3 passed. Red on `7.3.0-rc1-qpb-cc-crto-base+` (RED, RED, RED; CRTO `0`, CAP
`8200f0003ff`). Green on `7.3.0-rc1-qpb-cc-crto+` (RED, RED, GREEN; CRTO `f`,
`CAP.TO = 15   CRTO.CRWMT = 15`), with the ANAGRPID output identical line for line.
`Fixes: 1e058089d28f ("nvmet: implement crto property")`. No draft patch was produced.

RESULT: stopped at step 4: `git status --short` in `~/src/linux` is not empty (13 case-colliding files on the case-insensitive macOS filesystem, present before this run); red/green confirmed, no draft patch
