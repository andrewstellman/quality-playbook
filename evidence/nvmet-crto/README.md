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

Pending: first attempt failed on a controller-name bug in the script (probed `/dev/nvme`
instead of `/dev/nvme0`); fixed, rerun pending.

## Red on the snapshot commit

Pending.

## Green

Pending: `4d7d9486c04d` with only `nvmet-crto-from-cap.patch`. Expected:
CRTO.CRWMT = CAP.TO = 15.
