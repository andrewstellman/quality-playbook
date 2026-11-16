status: ruled-out
title: adonisjs/http-server: cookie maxAge 0 drops Max-Age
link: https://github.com/adonisjs/http-server/pull/145
updated: 2026-11-16
note: Closed by the maintainer, Harminder Virk (thetutlage), on 2026-11-16 without merging: "We'll keep maxAge: 0 as a session cookie, and the docs will be updated to match." This is the docs change Andrew offered on 2026-10-14.

## History

- Record as of 2026-10-27: The maintainer asked on 2026-10-14 for a non-breaking alternative. Andrew replied offering to turn it into a docs change or close it. No answer on 2026-10-27.

- Record as of 2026-10-20: Maintainer RomainLanz (2026-10-14, from his review comment, relayed by email) is unsure about merging as-is: changing maxAge 0 would be a silent breaking change for users who rely on it; he asks for an alternative syntax that does not break them. Reply not yet sent. Still open on 2026-10-20 (git).
