#!/usr/bin/env bash
# nvme-target BUG-002: ana_grpid 128 is accepted by the range check, then silently
# mapped to the reserved value 0 by a half-open array_index_nospec().
#   drivers/nvme/target/configfs.c  nvmet_ns_ana_grpid_store(), nvmet_ana_groups_make_group()
# No NVMe host needed: this is a pure configfs test.
# Prints RED (bug present) or GREEN (fixed). Run as root inside the guest.
set -u
CFG=/sys/kernel/config/nvmet
NQN=qpb-test-nqn

need() { command -v "$1" >/dev/null || { echo "missing: $1"; exit 2; }; }
need modprobe
modprobe nvmet 2>/dev/null || { echo "nvmet module not available; try: apt install linux-modules-extra-$(uname -r)"; exit 2; }
mount | grep -q configfs || mount -t configfs none /sys/kernel/config

# backing device: a 64 MB file on a loop device (avoids needing null_blk)
if [ ! -e /tmp/nvmet-back.img ]; then truncate -s 64M /tmp/nvmet-back.img; fi
LOOP=$(losetup -j /tmp/nvmet-back.img | cut -d: -f1)
[ -n "$LOOP" ] || LOOP=$(losetup --find --show /tmp/nvmet-back.img)

cleanup() {
  [ -e $CFG/subsystems/$NQN/namespaces/1 ] && echo 0 > $CFG/subsystems/$NQN/namespaces/1/enable 2>/dev/null
  rmdir $CFG/subsystems/$NQN/namespaces/1 2>/dev/null
  rmdir $CFG/subsystems/$NQN 2>/dev/null
}
cleanup
mkdir -p $CFG/subsystems/$NQN/namespaces/1
echo 1 > $CFG/subsystems/$NQN/attr_allow_any_host
echo -n "$LOOP" > $CFG/subsystems/$NQN/namespaces/1/device_path

A=$CFG/subsystems/$NQN/namespaces/1/ana_grpid
echo "kernel: $(uname -r)"
echo "initial ana_grpid = $(cat $A)"

# 129 must be rejected (range check is 1..NVMET_MAX_ANAGRPS=128)
if echo 129 > $A 2>/dev/null; then echo "unexpected: 129 accepted"; fi

# 128 is the top legal group id; nvmet_ana_group_enabled[] has 129 slots
if ! echo 128 > $A 2>/dev/null; then
  echo "write of 128 rejected (-EINVAL) — not the bug shape we expected"; cleanup; exit 3
fi
got=$(cat $A)
echo "after writing 128, ana_grpid reads = $got"
echo 1 > $A   # put it back so the enable counters are consistent for the next check

# Second symptom: creating and removing ANA group 128 on a port. Create bumps the
# clamped slot (0) but the release decrements slot 128, a u32 at 0, which wraps to
# 0xFFFFFFFF. admin-cmd.c then treats group 128 as present in every ANA log page.
# We can see this from the host side only; here we just perform the sequence and
# report whether the kernel let it happen. The host-side check is in
# repro-bug001-crto.sh's companion step (nvme ana-log) when run on the same boot.
mkdir -p $CFG/ports/99
if mkdir $CFG/ports/99/ana_groups/128 2>/dev/null; then
  rmdir $CFG/ports/99/ana_groups/128
  echo "created and removed ports/99/ana_groups/128 (counter for slot 128 is now wrapped if the bug is present)"
fi
rmdir $CFG/ports/99 2>/dev/null
cleanup
if [ "$got" = "128" ]; then echo "GREEN: 128 preserved"; exit 0; fi
if [ "$got" = "0" ];   then echo "RED: 128 became 0 (reserved ANAGRPID) — bug present"; exit 1; fi
echo "UNEXPECTED value $got"; exit 4
