status: open
title: setuptools: MANIFEST.in exclude patterns ignored character ranges such as [a-c]
link: https://github.com/pypa/setuptools/pull/5374
updated: 2026-11-16
note: PR #5374 opened 2026-11-09 against main. On 10 Nov an outside reviewer (agammann) pointed out that a reversed range such as [z-a] now raised an error, a case the PR had noted but not fixed. Andrew pushed a follow-up commit that drops reversed ranges as fnmatch does, and replied (review-1/). Waiting on a maintainer review on 2026-11-16.

## History

- Record as of 2026-11-16: The original patch and PR text are at the top level; the follow-up commits and reply are in review-1/.
