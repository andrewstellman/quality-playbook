status: merged
title: addressable: display_uri showed hosts with bidi and invisible characters decoded from Punycode (security advisory, low)
link: https://github.com/sporkmonger/addressable/security/advisories/GHSA-539f-xcgw-2gjg
updated: 2026-11-22
note: GitHub issued CVE-2026-126349 on 2026-11-12. Published by the maintainer on 2026-10-30 as GHSA-539f (Low, CVSS 3.1) and fixed in addressable 2.9.1, released the same day; Andrew is the credited reporter and the maintainer requested a CVE. BUG-013-COMMENT.md is the 22 Oct addendum (round-trip check); its first case overlaps GHSA-9crm, reported earlier by tonghuaroot. The maintainer says some mitigations wait for 2.10.0. On 2026-11-22 (03:18 UTC on 23 Nov) the maintainer published GHSA-x378-rg7m-2c49 (Low, CVSS 3.1, CWE-451/1007, no CVE yet): display_uri decoded an A-label containing U+3002 IDEOGRAPHIC FULL STOP, showing a label boundary that isn't in the real host; fixed in addressable 2.10.0 (released 2026-11-23 03:15 UTC), Andrew the only credited finder. It is the full-stop-lookalike case from BUG-013-COMMENT.md (the 22 Oct addendum), extended by the maintainer to U+3002.

## History

- Record as of 2026-10-27: Private report GHSA-539f; BUG-013 addendum posted 2026-10-22; sibling report GHSA-j82w sent 2026-10-22. On 2026-10-26 the maintainer linked two overlapping reports by other reporters (GHSA-9crm, GHSA-9f42).
- Record as of 2026-10-20: BUG-044 of the 2026-09-30 addressable campaign run. Private vulnerability report submitted by Andrew via the GitHub API (submit.sh, see submission-terminal.txt) on 2026-10-20 at about 19:30 UTC, severity low, CWE-451/CWE-176, range <= 2.9.0, report only with a suggested fix and the failing spec (display_uri_bidi_spec.rb) embedded. Reproduced the same day on main d298c9f with the pure backend (REPRO.md). Awaiting maintainer response.
