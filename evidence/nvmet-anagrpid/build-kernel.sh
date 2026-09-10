#!/usr/bin/env bash
# Build a kernel from the QPB snapshot commit inside the guest, optionally with patches,
# and install it so the next reboot uses it. Run as the lab user (uses sudo for install).
#
#   bash build-kernel.sh                                   # unpatched 4d7d9486, release suffix -qpb-base
#   SUFFIX=anagrpid bash build-kernel.sh patches/x.patch   # patched, release suffix -qpb-anagrpid
# Each suffix installs as a separate kernel, so base and patched builds coexist in GRUB.
#
# Output: the kernel is installed as /boot/vmlinuz-<ver>+ and made the GRUB default.
# The build directory is ~/linux. Re-runs are incremental.
set -e
COMMIT=4d7d9486c04d917265f64c55bd23b2cc4fe7749c
# resolve patch paths relative to where the script was invoked, before we cd
PATCHES=()
for p in "$@"; do
  case "$p" in /*) PATCHES+=("$p") ;; *) PATCHES+=("$PWD/$p") ;; esac
done
set -- "${PATCHES[@]}"
cd ~
if [ ! -d linux ]; then
  git clone --filter=blob:none --no-checkout https://github.com/torvalds/linux.git linux
fi
cd linux
git fetch -q origin $COMMIT 2>/dev/null || true
git checkout -q --detach $COMMIT
git reset -q --hard
git clean -qfd -e .config

for p in "$@"; do
  echo "== applying $p"
  git apply --check "$p"
  git apply "$p"
done
git diff --stat

if [ ! -f .config ]; then
  cp /boot/config-$(uname -r) .config
  # keep the distro config but make sure the target stack is built as modules
  scripts/config --module CONFIG_NVME_TARGET --module CONFIG_NVME_TARGET_LOOP \
                 --module CONFIG_NVME_TARGET_TCP --module CONFIG_NVME_TCP \
                 --module CONFIG_VSOCKETS --module CONFIG_VIRTIO_VSOCKETS --module CONFIG_VSOCKETS_LOOPBACK \
                 --disable CONFIG_DEBUG_INFO_BTF --disable SYSTEM_TRUSTED_KEYS --disable SYSTEM_REVOCATION_KEYS \
                 --set-str CONFIG_LOCALVERSION "-qpb"
fi
SUFFIX="${SUFFIX:-base}"
scripts/config --set-str CONFIG_LOCALVERSION "-qpb-$SUFFIX"
# no debug info: with the distro config it makes the module tree tens of GB and the
# initramfs step fails with zstd exit 70 (ENOSPC). Idempotent; safe to re-apply.
scripts/config --disable CONFIG_DEBUG_INFO --disable CONFIG_DEBUG_INFO_DWARF5 \
               --disable CONFIG_DEBUG_INFO_DWARF4 --disable CONFIG_DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT \
               --enable CONFIG_DEBUG_INFO_NONE
make olddefconfig

# flash-kernel (board firmware helper in Ubuntu arm64 cloud images) breaks `make install`
# on a UEFI/GRUB guest; it is not needed here
dpkg -s flash-kernel >/dev/null 2>&1 && sudo apt-get purge -y flash-kernel >/dev/null

# clear a previous (possibly bloated) install of the same release before reinstalling
REL=$(make -s kernelrelease)
sudo rm -rf "/lib/modules/$REL"

make -j"$(nproc)" Image modules
sudo make INSTALL_MOD_STRIP=1 modules_install
sudo make install
sudo update-grub
echo
REL=$(make -s kernelrelease)
# make this build the one GRUB boots next (others stay selectable)
sudo sed -i "s|^GRUB_DEFAULT=.*|GRUB_DEFAULT=\"Advanced options for Ubuntu>Ubuntu, with Linux $REL\"|" /etc/default/grub
sudo update-grub >/dev/null 2>&1
echo "installed: $REL and set as GRUB default. Reboot (sudo reboot) and check uname -r."
