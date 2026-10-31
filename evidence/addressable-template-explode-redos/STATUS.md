status: merged
title: addressable: Template#match still backtracked exponentially for {/var*}, {.var*} and {;var*} after the 2.9.0 ReDoS fix (security advisory, moderate)
link: https://github.com/sporkmonger/addressable/security/advisories/GHSA-j82w-28jv-3pmj
updated: 2026-10-31
note: BUG-022 of the 2026-09-30 addressable run. Sent as a private report on 2026-10-22; published by the maintainer on 2026-10-30 as GHSA-j82w (Moderate), fixed in addressable 2.9.1. Credited reporters: andrewstellman, halogenandtoast (GHSA-9f42, which also covers multi-variable expressions) and ebenoist.

## History

- 2026-10-22: private report GHSA-j82w sent by Andrew through the GitHub API (REPORT-AS-SENT.md, BUG-022.patch, result-BUG-022.txt). Reproduced on MRI 3.1.6 at main d298c9f; full suite 1438 examples, 0 failures with the patch on MRI 3.1.6 and 3.3.6.
- 2026-10-26: the maintainer linked halogenandtoast's overlapping report GHSA-9f42; Andrew commented that its patch is the more complete fix.
- 2026-10-28: the maintainer acknowledged and opened a fix PR in the advisory's temporary private fork.
- 2026-10-30: published, fixed in 2.9.1.
