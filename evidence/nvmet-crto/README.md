# Evidence: nvmet Property Get of CRTO is derived from CSTS instead of CAP

Bug found by Quality Playbook (Claude Opus 5) in the `nvme-target` run of 2026-09-06,
recorded as `nvme-target/quality/BUGS.md` BUG-001. This file records the reproduction.

## The defect

`drivers/nvme/target/fabrics-cmd.c`, `nvmet_get_property()`:

```c
		case NVME_REG_CRTO:
			val = NVME_CAP_TIMEOUT(ctrl->csts);
			break;
```

`NVME_CAP_TIMEOUT(cap)` is `(((cap) >> 24) & 0xff)` (`include/linux/nvme.h`), the
accessor for CAP.TO. CSTS defines only bits 6:0 and nvmet writes only bits 3:0, so the
expression is always 0. The same controller sets `ctrl->cap |= 15ULL << 24`
(`core.c`), advertising CAP.TO = 15.

NVM Express Base Specification 2.4, CAP.TO (Figure 36): when CC.CRIME is 0 this field
"shall be set to: a) the value in the Controller Ready With Media Timeout (CRTO.CRWMT)
field; or b) FFh if the value in the CRTO.CRWMT field is greater than FFh." nvmet reports
15 in one register and 0 in the other.

Related, not fixed by this patch: nvmet advertises NVMe 2.1 (`NVMET_DEFAULT_VS`) but
never sets CAP.CRMS.CRWMS, which the same spec says "shall be set to '1' on controllers
compliant with NVM Express Base Specification, Revision 2.0 and later." Because CRWMS is
clear, the Linux host does not read CRTO from nvmet, which is why this has gone
unnoticed. Advertising CRWMS is a separate change that depends on this one.

Fix: `ctrl->cap` in place of `ctrl->csts` ([nvmet-crto-from-cap.patch](./nvmet-crto-from-cap.patch)).

## Environment

Same guest as [../nvmet-anagrpid/README.md](../nvmet-anagrpid/README.md). Script: [repro-bug001-crto.sh](./repro-bug001-crto.sh),
which connects the in-guest host over NVMe/TCP and reads CAP (offset 0x00) and CRTO
(offset 0x68) with `nvme get-property`.

## Red, stock kernel 6.8.0-138-generic

Not captured with a clean verdict line: two script bugs (controller name, and nvme-cli 2.x
uses `--offset`, not `-o`) were fixed in between runs, and the kernel was rebuilt before a
clean stock-kernel rerun. The snapshot-commit run below is the red of record.

## Red on the snapshot commit (2026-09-10)

Kernel built inside the guest from torvalds/linux `4d7d9486c04d` (v7.3-rc1), unpatched,
release string `7.3.0-rc1-qpb+`. Host and target in the same guest over NVMe/TCP
(`127.0.0.1:4420`); nvme-cli 2.8. Raw capture:
[../nvmet-anagrpid/red-4d7d9486-raw.txt](../nvmet-anagrpid/red-4d7d9486-raw.txt) (shared
capture, this run is the last block).

```
kernel: 7.3.0-rc1-qpb+   controller: /dev/nvme0
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

CAP `0x8200f0003ff`: bits 31:24 = `0x0f`, TO = 15 (7.5 s). Bits 60:59 (CRMS) = 00b,
confirming nvmet does not advertise CRWMS. CRTO reads 0.

## Green (2026-09-10)

Same tree, same config, with only [nvmet-crto-from-cap.patch](./nvmet-crto-from-cap.patch)
applied; release string `7.3.0-rc1-qpb-crto+`. All three reproducers run on the same boot;
the two ANAGRPID scripts are included as a cross-check that this patch changes nothing
else. Raw capture: [green-crto-raw.txt](./green-crto-raw.txt).

```
kernel: 7.3.0-rc1-qpb-crto+
...
RED: 128 became 0 (reserved ANAGRPID) — bug present
...
RED: ANA log reports group 128 after it was removed — counter wrapped
kernel: 7.3.0-rc1-qpb-crto+   controller: /dev/nvme0
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

Result: CRTO reads `0xf`, CRWMT = 15 = CAP.TO; the unrelated ANAGRPID defect is still
present, as expected.

## Summary

| kernel | CRTO.CRWMT vs CAP.TO | ANAGRPID (unrelated) |
|---|---|---|
| 4d7d9486 unpatched (`-qpb+`) | 0 vs 15, RED | RED |
| 4d7d9486 + this patch (`-qpb-crto+`) | 15 vs 15, GREEN | RED |
| 4d7d9486 + anagrpid patch only (`-qpb-anagrpid+`) | 0 vs 15, RED | GREEN |

Build procedure for all three kernels: [build-kernel.sh](./build-kernel.sh).
