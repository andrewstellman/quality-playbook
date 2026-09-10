# virtio-pci INTx interrupt test

Tested September 3, 2026 using an x86_64 Ubuntu 24.04 host and QEMU 8.2.2.

The test forced `virtio-blk-pci` to use legacy INTx and generated 200
configuration-change interrupts using QMP `block_resize`.

## Results

Baseline:

- `/proc/irq/11/spurious`: `unhandled 0 -> 200`
- ftrace: `irq=11 ret=unhandled`

Patched:

- `/proc/irq/11/spurious`: `unhandled 0 -> 0`
- ftrace: `irq=11 ret=handled`

## Upstream

Merged by Michael S. Tsirkin as commit
[`93fa09455fb1`](https://git.kernel.org/torvalds/c/93fa09455fb1a9624b73d42ac1f83771f4818e80)
("virtio-pci: return IRQ_HANDLED after non-zero ISR"), sent to Linus in the
2026-09-09 vhost,vdpa,virtio fixes pull for 7.3-rc3. The merged text is
[virtio-pci-v3-send.patch](./virtio-pci-v3-send.patch).

## Artifacts

- [v3 as sent and merged](./virtio-pci-v3-send.patch) (standalone repost with `Assisted-by: LLM`; no code change from v2)
- [v2 as sent](./virtio-pci-v2-3-of-4-send.patch) (part 3 of a 4-patch series; the version tested below)
- [v2 patch, tested](./virtio-pci-v2-3-of-4.patch)
- [Guest console log](./virtio-irq-guest-console.txt)
- [Host/QMP console log](./virtio-irq-host-console.txt)

Public and client IP addresses in the console logs have been redacted.

## Method

The first patch from this project; the mistakes in its submission and the pipeline built
in response are documented in [../README.md](../README.md).
