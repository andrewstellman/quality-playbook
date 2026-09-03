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

## Artifacts

- [Patch](./virtio-pci-v2-3-of-4.patch)
- [Guest console log](./virtio-irq-guest-console.txt)
- [Host/QMP console log](./virtio-irq-host-console.txt)

Public and client IP addresses in the console logs have been redacted.
