#!/bin/sh
# BUG-003: a setuid file owned by uid/gid 65536 is archived in cpio bin/pwb format as uid/gid 0.
# Run as root. libarchive 432ab464 (master, 2026-11-20), ASan build in /home/claude/la/build.
B=/home/claude/la/build/bin; export ASAN_OPTIONS=detect_leaks=0
W=$(mktemp -d); cd "$W"; mkdir t
printf '#!/bin/sh\necho hi\n' > t/prog; chown 65536:65536 t/prog; chmod 4755 t/prog
echo "source:"; ls -ln t/prog | awk '{print $1,$3,$4,$NF}'
for f in bin pwb odc newc ustar; do
  $B/bsdtar --format $f -cf a.$f -C t prog; c=$?
  mkdir out-$f; $B/bsdtar -xpf a.$f -C out-$f; x=$?
  echo "$f: create rc=$c, extract (-p, as root) rc=$x: $(ls -ln out-$f/prog | awk '{print $1,$3,$4}')"
done
