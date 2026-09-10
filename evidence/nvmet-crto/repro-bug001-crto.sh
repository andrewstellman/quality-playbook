#!/usr/bin/env bash
# nvme-target BUG-001: Property Get of CRTO is computed from CSTS instead of CAP.
#   drivers/nvme/target/fabrics-cmd.c  nvmet_get_property()  case NVME_REG_CRTO
# The target advertises CAP.TO = 15 (core.c: ctrl->cap |= 15ULL << 24) but returns
# CRTO = 0. NVMe Base 2.4 says CAP.TO shall equal CRTO.CRWMT when CC.CRIME is 0.
# Needs NVMe/TCP to localhost (nvmet-tcp + nvme-tcp, both in Ubuntu) and nvme-cli. Run as root inside the guest.
# Prints RED (CRTO == 0) or GREEN (CRTO.CRWMT == CAP.TO).
set -u
CFG=/sys/kernel/config/nvmet
NQN=qpb-test-nqn

for m in nvmet nvmet-tcp nvme-fabrics nvme-tcp; do
  modprobe "$m" || { echo "module $m not available on $(uname -r)"; exit 2; }
done
command -v nvme >/dev/null || { echo "missing nvme-cli"; exit 2; }
mount | grep -q configfs || mount -t configfs none /sys/kernel/config

[ -e /tmp/nvmet-back.img ] || truncate -s 64M /tmp/nvmet-back.img
LOOP=$(losetup -j /tmp/nvmet-back.img | cut -d: -f1)
[ -n "$LOOP" ] || LOOP=$(losetup --find --show /tmp/nvmet-back.img)

cleanup() {
  nvme disconnect -n $NQN >/dev/null 2>&1
  rm -f $CFG/ports/1/subsystems/$NQN 2>/dev/null
  rmdir $CFG/ports/1 2>/dev/null
  [ -e $CFG/subsystems/$NQN/namespaces/1 ] && echo 0 > $CFG/subsystems/$NQN/namespaces/1/enable 2>/dev/null
  rmdir $CFG/subsystems/$NQN/namespaces/1 2>/dev/null
  rmdir $CFG/subsystems/$NQN 2>/dev/null
}
cleanup
mkdir -p $CFG/subsystems/$NQN/namespaces/1
echo 1 > $CFG/subsystems/$NQN/attr_allow_any_host
echo -n "$LOOP" > $CFG/subsystems/$NQN/namespaces/1/device_path
echo 1 > $CFG/subsystems/$NQN/namespaces/1/enable
mkdir -p $CFG/ports/1
echo tcp > $CFG/ports/1/addr_trtype
echo ipv4 > $CFG/ports/1/addr_adrfam
echo 127.0.0.1 > $CFG/ports/1/addr_traddr
echo 4420 > $CFG/ports/1/addr_trsvcid
ln -s $CFG/subsystems/$NQN $CFG/ports/1/subsystems/$NQN

nvme connect -t tcp -a 127.0.0.1 -s 4420 -n $NQN >/dev/null || { echo "connect failed"; cleanup; exit 2; }
sleep 1
CTRL=$(ls /sys/class/nvme-fabrics/ctl/ 2>/dev/null | grep -E '^nvme[0-9]+$' | head -1)
[ -n "$CTRL" ] || { echo "could not find the tcp controller"; cleanup; exit 2; }
echo "kernel: $(uname -r)   controller: /dev/$CTRL"

# CAP at offset 0x00 (64-bit); CRTO at offset 0x68 (32-bit)
CAP=$(nvme get-property /dev/$CTRL -o 0x00 2>/dev/null | grep -o '0x[0-9a-fA-F]*' | head -1)
CRTO=$(nvme get-property /dev/$CTRL -o 0x68 2>/dev/null | grep -o '0x[0-9a-fA-F]*' | head -1)
echo "CAP  = $CAP"
echo "CRTO = $CRTO"
cleanup
[ -n "$CAP" ] && [ -n "$CRTO" ] || { echo "get-property failed (need nvme-cli with get-property support)"; exit 2; }
cap_to=$(( ( CAP >> 24 ) & 0xff ))
crwmt=$(( CRTO & 0xffff ))
echo "CAP.TO = $cap_to   CRTO.CRWMT = $crwmt"
if [ "$crwmt" -eq "$cap_to" ] && [ "$cap_to" -ne 0 ]; then echo "GREEN: CRTO.CRWMT matches CAP.TO"; exit 0; fi
if [ "$crwmt" -eq 0 ] && [ "$cap_to" -ne 0 ]; then echo "RED: CRTO reads 0 while CAP.TO = $cap_to — bug present"; exit 1; fi
echo "UNEXPECTED"; exit 4
