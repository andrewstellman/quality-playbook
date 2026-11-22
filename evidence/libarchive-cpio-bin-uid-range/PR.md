# Pull request: libarchive/libarchive

Base: master (8deebeb4). Head: andrewstellman:cpio-bin-uid-range (2 commits, patches/ in this folder).

## Title

cpio binary: refuse a uid or gid that doesn't fit in 16 bits

## Body

The bin and pwb cpio writers store the uid and gid in 16 bits without checking the value, so a file owned by uid 65536 is written as owned by uid 0, with no error or warning.

To reproduce, as root:

```
mkdir t
printf '#!/bin/sh\necho hi\n' > t/prog
chown 65536:65536 t/prog
bsdtar --format bin -cf a.bin -C t prog   # exits 0, no warning
bsdtar -tvf a.bin                         # owner and group show as 0 0
```

With this change the writer returns ARCHIVE_FAILED with "Numeric user or group ID out of range for binary cpio format", as the ustar writer does for a uid that's too large. bsdtar prints that message and leaves the file out, and `bsdcpio -o --format bin` exits 1. The new test, test_write_format_cpio_bin_uid, fails without the fix and passes with it, and libarchive_test, bsdtar_test and bsdcpio_test pass on Linux (Release build).

This was reported privately as GHSA-gq68-3rxh-38h2, and is posted here as requested in the advisory.

The issue was found by Claude Opus 5.5 running Quality Playbook, an LLM-driven code review tool:
https://github.com/andrewstellman/quality-playbook
The fix and this description were drafted with Claude Opus 5.5 and reviewed by me.
