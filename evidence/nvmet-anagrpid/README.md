# Evidence: nvmet ANA group ID 128 is silently rewritten to 0

Bug found by Quality Playbook (Claude Opus 5) in the `nvme-target` run of 2026-09-06,
recorded as `nvme-target/quality/BUGS.md` BUG-002. This file records the reproduction.
Every log below was produced inside a QEMU guest and captured over ssh; nothing was
edited. Raw capture: [red-stock-6.8.0-138-raw.txt](./red-stock-6.8.0-138-raw.txt). Working copies of the scripts live in the qemu-lab folder; the versions here are the ones that produced the logs.

## The defect

`drivers/nvme/target/configfs.c`, two sites:

```c
/* nvmet_ns_ana_grpid_store() */
	if (newgrpid < 1 || newgrpid > NVMET_MAX_ANAGRPS)      /* accepts 1..128 inclusive */
		return -EINVAL;
	...
	newgrpid = array_index_nospec(newgrpid, NVMET_MAX_ANAGRPS);   /* clamps to [0, 128): 128 -> 0 */
	nvmet_ana_group_enabled[newgrpid]++;
	ns->anagrpid = newgrpid;

/* nvmet_ana_groups_make_group() */
	grp->grpid = grpid;                                     /* keeps 128 */
	...
	grpid = array_index_nospec(grpid, NVMET_MAX_ANAGRPS);   /* 128 -> 0 */
	nvmet_ana_group_enabled[grpid]++;                       /* bumps slot 0 */
```

`NVMET_MAX_ANAGRPS` is 128 (`nvmet.h:695`). The backing array is
`u32 nvmet_ana_group_enabled[NVMET_MAX_ANAGRPS + 1]` (`core.c:51`), so index 128 is a
valid slot. `array_index_nospec(index, size)` returns 0 for any `index >= size`
(`include/linux/nospec.h`). The range check is closed at 128; the clamp is open at 128.

Consequences:

1. Writing 128 to a namespace's `ana_grpid` succeeds and the namespace lands in group 0,
   which NVMe reserves.
2. Creating `ports/N/ana_groups/128` increments slot 0, but removing it decrements slot
   128 (`configfs.c:1938`, using the unclamped `grp->grpid`). Slot 128 goes from 0 to
   `0xFFFFFFFF`. `admin-cmd.c:553` and `:563` use a non-zero slot as "group present"
   when building the ANA log page, so group 128 is reported to every host from then on.

Fix: `NVMET_MAX_ANAGRPS + 1` as the size argument at both sites
([nvmet-anagrpid-128-nospec.patch](./nvmet-anagrpid-128-nospec.patch)).

## Environment

| item | value |
|---|---|
| host | Apple Silicon Mac, QEMU 10.x via Homebrew, `-M virt -accel hvf` |
| guest | Ubuntu 24.04.4 LTS arm64 cloud image |
| guest kernel (red, stock) | `6.8.0-138-generic`, with `linux-modules-extra-6.8.0-138-generic` for `nvmet-tcp`/`nvme-tcp` |
| transport | NVMe/TCP, target and host in the same guest, `127.0.0.1:4420` (Ubuntu does not ship `nvme-loop`) |
| nvme-cli | Ubuntu 24.04 package |
| scripts | [repro-bug002-anagrpid.sh](./repro-bug002-anagrpid.sh), [repro-bug002-analog.sh](./repro-bug002-analog.sh) |

All commands were issued from the Mac as `bash ~/src/qemu-lab/ssh.sh '<command>'`, which
runs `<command>` in the guest over ssh and echoes its output.

## Red 1: configfs write, stock kernel (2026-09-09)

Command run in the guest: `sudo bash guest/repro-bug002-anagrpid.sh`

```
kernel: 6.8.0-138-generic
initial ana_grpid = 1
after writing 128, ana_grpid reads = 0
created and removed ports/99/ana_groups/128 (counter for slot 128 is now wrapped if the bug is present)
RED: 128 became 0 (reserved ANAGRPID) — bug present
```

The script also confirms that 129 is rejected, so the range check is the closed
`1..128` check quoted above.

## Red 2: ANA log page, stock kernel (2026-09-09)

Command run in the guest: `sudo bash guest/repro-bug002-analog.sh`. The script creates a
subsystem with one namespace in group 1, creates and immediately removes
`ports/1/ana_groups/128`, connects the in-guest host over TCP, and dumps the ANA log.

```
kernel: 6.8.0-138-generic   controller: /dev/nvme0
Asymmetric Namespace Access Log for NVMe device: nvme0
ANA LOG HEADER :-
chgcnt	:	2
ngrps	:	2
ANA Log Desc :-
grpid	:	1
nnsids	:	1
chgcnt	:	2
state	:	optimized
	nsid	:	1

grpid	:	128
nnsids	:	0
chgcnt	:	2
state	:	inaccessible
RED: ANA log reports group 128 after it was removed — counter wrapped
```

Group 128 no longer exists in configfs at the time of the log read, yet the target
reports `ngrps: 2` and a descriptor for group 128 with zero namespaces, state
`inaccessible`. That is the wrapped counter in `nvmet_ana_group_enabled[128]`.

## Red on the snapshot commit (2026-09-10)

Kernel built inside the guest from torvalds/linux `4d7d9486c04d` (v7.3-rc1), unpatched,
Ubuntu's config with debug info disabled and the nvmet target stack as modules; release
string `7.3.0-rc1-qpb+`. Same two scripts. Raw capture:
[red-4d7d9486-raw.txt](./red-4d7d9486-raw.txt).

```
kernel: 7.3.0-rc1-qpb+
initial ana_grpid = 1
after writing 128, ana_grpid reads = 0
created and removed ports/99/ana_groups/128 (counter for slot 128 is now wrapped if the bug is present)
RED: 128 became 0 (reserved ANAGRPID) — bug present
kernel: 7.3.0-rc1-qpb+   controller: /dev/nvme0
Asymmetric Namespace Access Log for NVMe device: nvme0
ANA LOG HEADER :-
chgcnt : 2
ngrps : 2
ANA Log Desc :-
grpid : 1
nnsids : 1
chgcnt : 2
state : optimized
nsid : 1

grpid : 128
nnsids : 0
chgcnt : 2
state : inaccessible
RED: ANA log reports group 128 after it was removed — counter wrapped
```

## Green

Pending: same two scripts on `4d7d9486c04d` with only
`nvmet-anagrpid-128-nospec.patch` applied. Expected: `ana_grpid` reads back 128;
ANA log shows `ngrps: 1` with no group 128.

## Not yet done

`Fixes:` tag. Blame `configfs.c` lines 701 and 1979 at `4d7d9486c04d` in a full-history
clone and confirm the blamed commit introduced the `array_index_nospec` call with this
bound, rather than moving it.
