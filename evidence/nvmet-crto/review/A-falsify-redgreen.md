# Reviewer A — falsify the red/green

Charter: try to show that the GREEN result does not prove the patch fixes the bug.

**Overall verdict: FIX-REQUIRED** — but not on the experiment. I could not falsify the
red/green on any of the five questions; all five are SHIP. The blocker is one sentence in
the commit message that names a function that does not exist in the kernel
(`nvmet_get_property()`), found while tracing question 4. That is a message edit, not a
re-run.

## What I could and could not read

Read in full: `README.md`, `RUNBOOK.md`, `RUN-REPORT.md`, `cc-red-base.txt`,
`cc-green-crto.txt`, `green-crto-raw.txt`, `DRAFT-0001-nvmet-derive-the-CRTO-property-from-CAP-not-CSTS.patch`,
`nvmet-crto-from-cap.patch`, `repro-bug001-crto.sh`, `build-kernel.sh`, and the sibling
folder's `red-4d7d9486-raw.txt`, `green-anagrpid-raw.txt`, `cc-red-base.txt`,
`cc-green-anagrpid.txt`. Grepped `cc-transcript.txt` (6.9 MB) at the build boundaries.
Source read at the snapshot: `/Users/andrewstellman/Documents/QPB/repos/linux/nvme-target/`
and the spec text `.../reference_docs/cite/nvme-base-2.4.txt`.

**Limitation, stated up front:** my shell cannot reach `~/src/linux` — it is not one of
this session's mounted directories, and the file tools reject the path. So I did **not**
re-derive the `git blame` / pickaxe chain behind the `Fixes:` tag, and I did not run the
`Assisted-by:` survey. Everything I assert about history below is either from the
RUN-REPORT's pasted output or from the snapshot source I can read directly; I say which.
Reviewer C's charter covers the `Fixes:` chain, and that verification is still owed by
someone with access to that clone.

For the host-side trace (question 4) I substituted a different tree: the QPB host snapshot
at `/Users/andrewstellman/Documents/QPB/repos/linux/nvme-host/`, whose single commit is
`8563722 nvme host subsystem @ torvalds/linux master`, dated `Fri Sep 4 12:58:53 2026` —
close to, but not identical with, `4d7d9486c04d` (v7.3-rc1). Disclosed as a substitution.
Its `drivers/nvme/host/core.c:2814-2818` is character-for-character the text the
RUN-REPORT pastes from the exact snapshot, which is decent corroboration that the two
agree on this code.

---

## Q1 — Is the GREEN kernel different from the RED kernel in any way other than the patch?

**Verdict: SHIP.**

### Does the tree get reset before applying?

Yes. `build-kernel.sh:23-27`:

```
cd linux
git fetch -q origin $COMMIT 2>/dev/null || true
git checkout -q --detach $COMMIT
git reset -q --hard
git clean -qfd -e .config
```

`git checkout --detach <sha>` + `git reset --hard` puts the tracked tree at exactly
`4d7d9486c04d` regardless of what the previous build left behind, and only then does the
loop at lines 29-33 apply patches. So the patched build cannot carry a previous build's
source changes.

`git clean -qfd` has no `-x`, so ignored files — the object tree — survive. That is the
"re-runs are incremental" property, and it is the one thing worth attacking. I attacked it
and it holds, for two reasons visible in the transcript:

1. The base build applied nothing. At `cc-transcript.txt:30793` the re-run command line is
   followed immediately by `# configuration written to .config` — no `== applying` line
   (which `build-kernel.sh:30` would have printed) and no output from the unconditional
   `git diff --stat` at line 34, i.e. an empty diff against the snapshot.
2. The patched build applied exactly one patch and kbuild actually rebuilt the affected
   object. `cc-transcript.txt:53942-53945`:

   ```
   $ bash ~/src/qemu-lab/ssh.sh 'SUFFIX=cc-crto bash guest/build-kernel.sh patches/nvmet-crto-from-cap.patch'
   == applying /home/lab/patches/nvmet-crto-from-cap.patch
    drivers/nvme/target/fabrics-cmd.c | 2 +-
    1 file changed, 1 insertion(+), 1 deletion(-)
   ```

   and 30 lines later in that build:

   ```
     CC [M]  drivers/nvme/target/core.o
     CC [M]  drivers/nvme/target/admin-cmd.o
     CC [M]  drivers/nvme/target/fabrics-cmd.o
     CC [M]  drivers/nvme/target/discovery.o
     LD [M]  drivers/nvme/target/nvmet.o
   ```

   `fabrics-cmd.o` was recompiled and `nvmet.ko` relinked, so the running module contains
   the patched line. The three neighbours are explained without any appeal to
   contamination: `core.c:1864` and `discovery.c:298` both reference `UTS_RELEASE`
   (`grep -rn UTS_RELEASE drivers/nvme/target/`), and `CONFIG_LOCALVERSION` changed
   between builds, so `utsrelease.h` changed and those objects were correctly invalidated.
   `admin-cmd.c` is in the same dependency neighbourhood. Nothing under `drivers/nvme/`
   was rebuilt that shouldn't have been, and nothing that should have been was skipped.

### Same config?

Same `.config`, deliberately preserved (`git clean -qfd -e .config`, line 27), then
`scripts/config --set-str CONFIG_LOCALVERSION "-qpb-$SUFFIX"` (line 46) and
`make olddefconfig` (line 52). The patch touches no Kconfig and no header, and the source
commit is identical, so `olddefconfig` has nothing to resolve differently. The only
intended config delta is `CONFIG_LOCALVERSION`.

**This is the one gap I found, and it is small.** Nobody ran
`diff /boot/config-7.3.0-rc1-qpb-cc-crto-base+ /boot/config-7.3.0-rc1-qpb-cc-crto+`. That
one command would turn "the configs must be identical apart from LOCALVERSION" from an
inference into an observation, and both files should still exist in the guest's `/boot`
(the RUN-REPORT only deleted the `.old` copies, environment fix 2). I would run it, but
I would not hold the patch for it, because of the next paragraph.

### Could the suffix change, the /boot cleanup, or a rebuild artifact explain the result?

No, and the evidence folder already contains the control that kills all three hypotheses,
though the README's summary table under-sells it. Across the two runs there are **four**
unpatched kernels with **four different `CONFIG_LOCALVERSION` suffixes**, built at
different times, and every one reads CRTO = 0:

| kernel (from the capture's own `uname -r` line) | file | CRTO |
|---|---|---|
| `7.3.0-rc1-qpb+` | `../nvmet-anagrpid/red-4d7d9486-raw.txt` last block | `0` |
| `7.3.0-rc1-qpb-anagrpid+` (**a different patch applied**) | `../nvmet-anagrpid/green-anagrpid-raw.txt` | `0` |
| `7.3.0-rc1-qpb-cc-base+` | `../nvmet-anagrpid/cc-red-base.txt` | `0` |
| `7.3.0-rc1-qpb-cc-anagrpid+` (**a different patch applied**) | `../nvmet-anagrpid/cc-green-anagrpid.txt` | `0` |
| `7.3.0-rc1-qpb-cc-crto-base+` | `cc-red-base.txt` | `0` |

and **two** kernels, built in two separate runs, with the CRTO patch and two different
suffixes, both read `f`: `7.3.0-rc1-qpb-crto+` (`green-crto-raw.txt`) and
`7.3.0-rc1-qpb-cc-crto+` (`cc-green-crto.txt`).

`-qpb-anagrpid+` and `-qpb-cc-anagrpid+` are the decisive controls: a fresh suffix, a
fresh incremental rebuild, a fresh install into `/boot`, a patch applied — and CRTO is
still 0. So "a rebuild produces `f`" and "a new suffix produces `f`" are both falsified by
data already in the folder. Only the CRTO patch produces `f`.

The `/boot` cleanup (environment fix 1) removed `vmlinuz`/`initrd`/`System.map`/`config`
for `-qpb-cc-base+` and `-qpb-cc-anagrpid+` only, after their evidence was captured.
Deleting an unbooted kernel's files cannot change what a different, running kernel
returns over a socket. And the reproducer prints `uname -r` itself on every invocation
(`repro-bug001-crto.sh:46`), so the identity of the kernel under test is stamped into each
capture rather than inferred: `cc-red-base.txt:23` and `cc-green-crto.txt:23` carry the
two release strings, and `cc-transcript.txt:53859` / `:84755` show
`poll 1 (+10s): rc=0 7.3.0-rc1-qpb-cc-crto-base+` and `... -qpb-cc-crto+` from the reboot
polls. Stale-module risk is handled too: `build-kernel.sh:60` does
`sudo rm -rf "/lib/modules/$REL"` before `modules_install`, and each suffix is its own
`$REL`, so `modprobe nvmet` on either boot loads that boot's own `nvmet.ko`.

Finally, I verified that the scripts and patch in the evidence folder are the ones that
were actually run: `diff` of `build-kernel.sh`, `repro-bug001-crto.sh` and
`nvmet-crto-from-cap.patch` against `~/src/qemu-lab/guest/` and `~/src/qemu-lab/patches/`
reports no differences, independently reproducing the RUN-REPORT's claim at its lines
37-40. `build-kernel.sh` here is also byte-identical to `../nvmet-anagrpid/build-kernel.sh`.

---

## Q2 — Does the cross-check hold?

**Verdict: SHIP.**

I ran the comparison myself rather than trusting RUN-REPORT lines 187-211. Both files are
32 lines. With each run's own release string mapped to `KERNEL`:

```
$ diff <(sed 's/7\.3\.0-rc1-qpb-cc-crto-base+/KERNEL/g' cc-red-base.txt) \
       <(sed 's/7\.3\.0-rc1-qpb-cc-crto+/KERNEL/g' cc-green-crto.txt)
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

Lines 1-22 — the complete output of both ANAGRPID reproducers, including
`RED: 128 became 0 (reserved ANAGRPID) — bug present` and `RED: ANA log reports group 128
after it was removed — counter wrapped`, and the whole ANA log dump with `ngrps : 2`,
`grpid : 128`, `nnsids : 0`, `state : inaccessible` — are identical, exit 0. Lines 23-27
and 29 (controller name, nvme-cli version, the raw CAP line `value: 8200f0003ff`) are
identical too. Exactly four lines differ, and all four are CRTO. The RUN-REPORT's diff
reproduces exactly.

One honest caveat about how much weight this carries. The cross-check is corroboration,
not the load-bearing argument. Two ANAGRPID reproducers exercise configfs `ana_grpid`
writes and the ANA log page; they do not sweep the target's surface, so "changes nothing
else" rests mainly on the diff itself being a one-token substitution inside a single
`case` label (`fabrics-cmd.c:68`), which no other code path reads. `git diff --cached
--stat` in RUN-REPORT line 698 confirms one file, one insertion, one deletion. That is
enough; the cross-check is a bonus.

Also worth noting because it is *nice*, not suspicious: the CAP value is fully
reconstructible from the source. `core.c:1453-1467` `nvmet_init_cap()` sets
`(1ULL << 37) | (1ULL << 43) | (15ULL << 24)` plus `max_queue_size - 1`, and
`(1<<37)|(1<<43)|(15<<24)|1023 == 0x8200f0003ff` exactly — the measured value, with
TO = 15, MQES = 1023, and bits 60:59 (CRMS) = 00b. Nothing else in the system could have
produced that number by coincidence.

---

## Q3 — Could `repro-bug001-crto.sh` produce GREEN on a buggy kernel or RED on a fixed one?

**Verdict: SHIP.** No input produces a false GREEN. I tested this rather than reasoned it.

The parse (`repro-bug001-crto.sh:55-56`) is
`sed -n 's/.*value: *\([0-9a-fA-F]*\).*/0x\1/p' | head -1`, the arithmetic (lines 61-62)
is `cap_to=$(( ( CAP >> 24 ) & 0xff ))` and `crwmt=$(( CRTO & 0xffff ))`, and the exit
paths (lines 64-66) are:

```
if [ "$crwmt" -eq "$cap_to" ] && [ "$cap_to" -ne 0 ]; then echo "GREEN: ..."; exit 0; fi
if [ "$crwmt" -eq 0 ] && [ "$cap_to" -ne 0 ]; then echo "RED: ..."; exit 1; fi
echo "UNEXPECTED"; exit 4
```

I extracted the parse-and-decide block verbatim into a standalone harness and drove it
with ten inputs:

| raw CAP / raw CRTO | parsed | verdict |
|---|---|---|
| `value: 8200f0003ff` / `value: 0` | CAP.TO 15, CRWMT 0 | RED |
| `value: 8200f0003ff` / `value: f` | 15, 15 | GREEN |
| `value: 8200f0003ff` / `value: f000f` (CRIMT=15) | 15, 15 | GREEN |
| `value: 8200f0003ff` / `value: 10000` (CRIMT=1, CRWMT=0) | 15, 0 | RED |
| `value: 8200f0003ff` / `value: 00000000f` | 15, 15 | GREEN |
| `value: ` (empty) both | `0x` → 0, 0 | UNEXPECTED |
| `value: zz` both | `0x` → 0, 0 | UNEXPECTED |
| `failed to open /dev/nvme0` both | empty | exits 2 at line 60 |
| `value: 0` / `value: 0` | 0, 0 | UNEXPECTED |
| `value: 8200f0003ff` / same 43-bit value | 15, 1023 | UNEXPECTED |

**GREEN with CRTO still 0 is unreachable.** GREEN requires `crwmt -eq cap_to` *and*
`cap_to -ne 0`; if CRTO is 0 then `crwmt` is 0, so GREEN would require `cap_to == 0`,
which the same condition forbids. **RED on a fixed kernel is unreachable** for this
target: RED requires `crwmt -eq 0`, and a fixed nvmet returns 15.

Two things I went looking for and did not find as false-GREEN vectors:

- The `\([0-9a-fA-F]*\)` group can match empty, so garbage output yields the string `0x`
  rather than an empty string, sailing past the `[ -n "$CAP" ]` guard at line 60. I
  expected an arithmetic error; bash evaluates `$(( 0x ))` as 0 silently. The result is
  `cap_to = 0`, which lands on UNEXPECTED, never GREEN. Fail-safe by accident, but
  fail-safe.
- Greedy `.*value:` would take the *last* `value:` on a line if there were several.
  `nvme get-property` prints one, and both captures show the expected single line.

Two false-*alarm* paths exist and are worth one sentence in a future runbook, since
neither can mislead in the direction that matters: a controller with CAP.TO = 0 and
CRTO = 0 is spec-legal but scores UNEXPECTED, and a controller whose CRWMT legitimately
differs from CAP.TO also scores UNEXPECTED. Both halt the run under runbook hard rule 4
rather than producing a wrong verdict. nvmet hard-codes CAP.TO = 15 (`core.c:1460`), so
neither arises here.

Controller-name grep, line 44:
`CTRL=$(ls /sys/class/nvme-fabrics/ctl/ | grep -E '^nvme[0-9]+$' | head -1)`. This picks
the lexicographically first fabrics controller without checking it belongs to `$NQN`, and
`ls` sorting would put `nvme10` before `nvme2`. Three things defuse it: `cleanup()` runs
at line 30 before anything is created; all three reproducers use the same
`NQN=qpb-test-nqn` (checked in `repro-bug002-anagrpid.sh:9`, `repro-bug002-analog.sh:9`,
`repro-bug001-crto.sh:10`), so the preceding two scripts leave nothing connected; and the
chosen name is printed into the capture — both files show `/dev/nvme0`. Fine as run;
worth hardening only if the lab ever grows a second fabrics controller.

Unit check, because "the numbers match" is not the same as "the fix is right": Figure 36
(`nvme-base-2.4.txt:4481-4482`) says CAP.TO "is in 500 millisecond units", and Figure 57
(`:5476`) says CRWMT "is in 500 millisecond units". Same units, so CRWMT = CAP.TO = 15 is
semantically correct and not a coincidence of scale.

---

## Q4 — Is the value at offset 0x68 actually CRTO as served by the target?

**Verdict: SHIP.** Nothing substitutes or caches it.

Target side, which is the part I can read at the exact snapshot. In
`drivers/nvme/target/fabrics-cmd.c`, `nvmet_execute_prop_get()` (line 38) splits on
`req->cmd->prop_get.attrib & 1`: the 64-bit branch (lines 47-54) accepts only
`NVME_REG_CAP`; the 32-bit branch (lines 56-71) is where `case NVME_REG_CRTO:` lives at
line 67 with `val = NVME_CAP_TIMEOUT(ctrl->csts);` at line 68. The result is written once,
at line 81: `req->cqe->result.u64 = cpu_to_le64(val);`. `NVME_REG_CRTO = 0x0068`
(`include/linux/nvme.h:152`). A grep of the whole target tree finds exactly one
`NVME_REG_CRTO` reference and exactly one `NVME_CAP_TIMEOUT` use — both are that one line.
There is no other producer of a value for offset 0x68 anywhere in nvmet.

That also disposes of the "maybe it errored and printed 0" story. If nvmet had not
recognised 0x68 it would have taken `default:` at line 69 and returned
`NVME_SC_INVALID_FIELD | NVME_STATUS_DNR`; nvme-cli would have printed a status error, not
`property: 0x68 (Unknown), value: 0`. The `(Unknown)` in that line is nvme-cli 2.8's own
label for an offset it has no name string for, not a target error.

Host side (substituted tree, disclosed above). `nvme get-property` reaches the target
through `NVME_IOCTL_ADMIN_CMD` → `nvme_user_cmd()` (`drivers/nvme/host/ioctl.c:316-362`),
which copies the user's cdw fields straight into `struct nvme_command`, gates fabrics
opcodes on `CAP_SYS_ADMIN` (`nvme_cmd_allowed()`, `ioctl.c:111-113`), submits, and copies
the raw completion result back with `put_user(result, &ucmd->result)` (line 358). There is
no cache, no fixup, no default. The kernel's own CRTO consumer is separate and
irrelevant here: `core.c:2814-2833` reads `NVME_REG_CRTO` only inside
`if (ctrl->cap & NVME_CAP_CRMS_CRWMS)` (line 2815) during `nvme_enable_ctrl()`, and the
measured CAP has bits 60:59 = 00b, so that branch never runs against nvmet. There is
nothing cached for a `get-property` to be served from.

But the argument that actually settles it needs none of that source reading. The same
nvme-cli 2.8 binary, the same nvme-tcp transport, the same loopback socket, the same
guest, returned `0` on one boot and `f` on the next, and the only difference between the
two boots is one token in one `case` arm of the target. If nvme-cli, the fabrics host, or
the TCP transport were substituting a value, a target-side edit could not have changed the
answer. Any substitution hypothesis is falsified by the fact that the substitution
tracked the target patch.

---

## Q5 — Is "CSTS defines only bits 6:0 and nvmet writes only RDY, CFS and SHST" true at the snapshot?

**Verdict: SHIP**, with one completeness note that does not change the conclusion.

Spec half, verified directly: Figure 42, `nvme-base-2.4.txt:4854-4857`, first row is
`31:07  RO  0h  Reserved`; the highest defined bit is 06, Shutdown Type (ST), at
`:4870-4877`. So "CSTS defines only bits 6:0" is exact.

Macro half: `include/linux/nvme.h:166` is
`#define NVME_CAP_TIMEOUT(cap) (((cap) >> 24) & 0xff)` — bits 31:24. `ctrl->csts` is `u32`
(`nvmet.h:267`), so there is no width or sign surprise; `(csts >> 24) & 0xff` on a value
whose bits 31:7 are always clear is identically 0.

Every write in the target tree, from `grep -rn csts drivers/nvme/target/`:

| site | statement |
|---|---|
| `core.c:1399` | `ctrl->csts = NVME_CSTS_CFS;` |
| `core.c:1406` | `ctrl->csts = NVME_CSTS_CFS;` |
| `core.c:1410` | `ctrl->csts = NVME_CSTS_RDY;` |
| `core.c:1427` | `ctrl->csts &= ~NVME_CSTS_RDY;` |
| `core.c:1445` | `ctrl->csts \|= NVME_CSTS_SHST_CMPLT;` |
| `core.c:1448` | `ctrl->csts &= ~NVME_CSTS_SHST_CMPLT;` |
| `core.c:1790` | `ctrl->csts \|= NVME_CSTS_CFS;` |
| `pci-epf.c:1817` | `tctrl->csts = 0;` |

`core.c:1522`, `discovery.c:397`, `debugfs.c:84` and `pci-epf.c:1962` are reads. The
`ctrl->csts` writes at `pci-epf.c:1818, 1884, 1921, 1923, 1959` are a *different* struct —
`struct nvmet_pci_epf_ctrl`'s own `u32 csts` at `pci-epf.c:173` — not `nvmet_ctrl`.

**The note:** `pci-epf.c:1817` (`nvmet_pci_epf_clear_ctrl_config()`, via
`tctrl = ctrl->tctrl` on line 1814) is a write to `nvmet_ctrl->csts` that is neither RDY
nor CFS nor SHST. It writes 0. So the message's "nvmet writes only RDY, CFS and SHST into
it" is a shade looser than the source, and the RUN-REPORT's claim-check grep (lines
330-341) only covered `core.c` and would not have found it. The load-bearing conclusion —
no bit at or above 24 is ever set, so `NVME_CAP_TIMEOUT(ctrl->csts)` is identically 0 — is
strengthened, not weakened, by a write of zero. I would not block on this, and I would not
lengthen the sentence to accommodate it; a maintainer reading "writes only RDY, CFS and
SHST" against `= 0` will not blink. Recording it so nobody mistakes the grep for
exhaustive.

The corresponding value bounds also check out: `nvmet_init_cap()` at `core.c:1453-1470`
sets `ctrl->cap |= (15ULL << 24)` at line 1460, and `NVME_CAP_TIMEOUT(ctrl->cap)` yields
15 in bits 7:0, so CRTO.CRWMT = 15 and CRTO.CRIMT = 0 — which is what Figure 57 requires
when CAP.CRMS.CRIMS is clear ("shall clear this field to 0h", `:5449-5451`), and CRIMS is
clear in the measured CAP.

---

## The reason not to send it, found outside the five questions

The draft commit message's opening sentence, `DRAFT-0001-...patch:6-7`:

> nvmet_get_property() answers a Property Get of CRTO with
> NVME_CAP_TIMEOUT(ctrl->csts).

**`nvmet_get_property()` does not exist.** `grep -rn nvmet_get_property` over
`/Users/andrewstellman/Documents/QPB/repos/linux/` returns nothing in any source file.
The function is `nvmet_execute_prop_get()` (`drivers/nvme/target/fabrics-cmd.c:38`,
installed as `req->execute` at line 113). The wrong name propagated from the bug report
into `README.md:14`, `repro-bug001-crto.sh:3`, `RUNBOOK.md:14` and `RUNBOOK.md:220` (the
message template), and from there into the committed message. It is the first identifier a
maintainer will read and the first one they will fail to find.

This is the same class of defect the RUN-REPORT caught for `nvmet_init_ctrl()` →
`nvmet_init_cap()` (its lines 346-360): the claim check grepped for the names it was told
to check and did not grep for the names it wasn't. The fix is one word in the message; the
tested diff is unaffected and nothing needs rebuilding. `RUNBOOK.md:14` and `:220` should
be corrected too, or the next run will reintroduce it.

Two smaller things I noticed while reading, both Reviewer C's territory, listed without
verdicts so they are not lost:

- The message paraphrases Figure 36 as "when CC.CRIME is '0' the TO field shall be set
  to…", but the spec's condition (`nvme-base-2.4.txt:4483-4486`) is a conjunction: CRIME
  cleared **and** the worst-case CSTS.RDY transition time being due to enabling the
  controller. The quoted words themselves (`:4487-4489`) match verbatim; only the
  introduced condition is abridged.
- `../nvmet-anagrpid/red-4d7d9486-raw.txt` contains a stale `UNEXPECTED` block
  (`CAP = 0x00`, `CRTO = 0x68`, `CAP.TO = 0   CRTO.CRWMT = 104`) produced by an older
  version of the parser, immediately above the good block for the same kernel
  `7.3.0-rc1-qpb+`. This folder's `README.md:46-50` disclaims the *stock 6.8* capture but
  not this one, and `README.md:57` points a reader at the file with only "this run is the
  last block" to guide them. Nothing in the patch depends on it. It is a documentation
  hazard in the evidence, not an experimental one, and the manual run it belongs to has
  been superseded by the autopilot run in any case.

---

## Per-question summary

| Q | subject | verdict |
|---|---|---|
| 1 | GREEN vs RED differ only by the patch | SHIP |
| 2 | ANAGRPID cross-check identical apart from the kernel string | SHIP |
| 3 | reproducer cannot emit a false GREEN or a false RED | SHIP |
| 4 | 0x68 is nvmet's CRTO, unsubstituted and uncached | SHIP |
| 5 | CSTS claim true at the snapshot | SHIP |
| — | commit message names a non-existent function | **FIX-REQUIRED** |

## Required before sending

1. `DRAFT-0001-...patch:6` — `nvmet_get_property()` → `nvmet_execute_prop_get()`. Amend
   the commit and regenerate the patch. Also fix `RUNBOOK.md:14` and `:220`,
   `README.md:14`, and `repro-bug001-crto.sh:3`.

## Recommended, not blocking

2. Run `diff` on the two `/boot/config-7.3.0-rc1-qpb-cc-crto{-base,}+` files in the guest
   and paste the result (expected: one line, `CONFIG_LOCALVERSION`). It converts the last
   inferred step in the Q1 chain into an observed one, and costs one ssh round trip.
3. Someone with access to `~/src/linux` still owes the `Fixes:` chain re-derivation and
   the `Assisted-by:` survey; I could not reach that clone from this session.
4. Optional, for the folder rather than the patch: note the stale parser block inside
   `../nvmet-anagrpid/red-4d7d9486-raw.txt` where `README.md:57` links to it.
