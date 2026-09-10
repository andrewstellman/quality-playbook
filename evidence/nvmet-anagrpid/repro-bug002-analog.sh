#!/usr/bin/env bash
# nvme-target BUG-002, host-visible symptom: after mkdir+rmdir of ports/N/ana_groups/128,
# nvmet_ana_group_enabled[128] has wrapped to 0xFFFFFFFF, so the ANA log page
# (admin-cmd.c nvmet_execute_get_log_page_ana) reports group 128 as present forever.
# Run AFTER repro-bug002-anagrpid.sh on the same boot. Needs nvmet-tcp + nvme-tcp + nvme-cli. Root.
# Prints RED if group 128 shows up in the ANA log, GREEN if it does not.
set -u
CFG=/sys/kernel/config/nvmet
NQN=qpb-test-nqn

for m in nvmet nvmet-tcp nvme-fabrics nvme-tcp; do
  modprobe "$m" || { echo "module $m not available on $(uname -r)"; exit 2; }
done
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

# the trigger, on this port (harmless on a fixed kernel)
mkdir $CFG/ports/1/ana_groups/128 && rmdir $CFG/ports/1/ana_groups/128

nvme connect -t tcp -a 127.0.0.1 -s 4420 -n $NQN >/dev/null || { echo "connect failed"; cleanup; exit 2; }
sleep 1
CTRL=$(ls /sys/class/nvme-fabrics/ctl/ 2>/dev/null | grep nvme | head -1)
[ -n "$CTRL" ] || { echo "no tcp controller"; cleanup; exit 2; }
echo "kernel: $(uname -r)   controller: /dev/$CTRL"
LOG=$(nvme ana-log /dev/$CTRL 2>&1)
echo "$LOG" | head -40
cleanup
if echo "$LOG" | grep -qiE "grpid[^0-9]*128\b|group.*\b128\b"; then
  echo "RED: ANA log reports group 128 after it was removed — counter wrapped"; exit 1
fi
echo "GREEN: group 128 absent from ANA log"; exit 0
