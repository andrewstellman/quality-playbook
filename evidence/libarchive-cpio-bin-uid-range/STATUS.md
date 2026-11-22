status: merged
title: libarchive: the cpio bin and pwb writers stored a uid or gid above 65535 modulo 65536, so uid 65536 became 0
link: https://github.com/libarchive/libarchive/pull/3873
updated: 2026-11-22
note: Merged by Tim Kientzle into master on 2026-11-21 at 23:40 EST (merge commit 090b4ab87; commits c87c6ad and 161c746 unchanged), after his approval at 23:21. First reported privately as GHSA-gq68-3rxh-38h2 on 2026-11-20; the maintainer asked for a public PR on the advisory on 2026-11-21. Checked with git against the live repository on 2026-11-22.

## Files

- repro/bug003-uid-wrap.sh and .out: the first reproduction, on master 432ab464 (2026-11-20), ASan build.
- PR.md: the PR title and description as posted. patches/: the two commits as pushed (rebased onto master 8deebeb4).
- test-red.txt and test-green.txt: the new test without and with the fix. full-*.txt: libarchive_test, bsdtar_test and bsdcpio_test with the fix. make.log: the build. patched-tools.out: bsdtar and bsdcpio with the fix.

The private advisory text, its review rounds and the advisory comments are not published here (see "What is not published here" in README.md).
