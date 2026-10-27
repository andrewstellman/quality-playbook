status: open
title: marshmallow: five bugs from the 2026-10-05 run, three of them first reported privately to Tidelift
link: https://github.com/marshmallow-code/marshmallow/pulls?q=is%3Apr+author%3Aandrewstellman
updated: 2026-10-27
note: Five PRs open against dev: #3086 (BUG-004), #3087 (BUG-001), #3088 (BUG-002), #3089 (BUG-003), #3090 (BUG-006, changed on 2026-10-22 to raise a validation error after review by Jared Deckard). BUG-001, 003 and 006 went to Tidelift first; Tidelift ruled them not vulnerabilities and asked for public PRs.

## History

- Record as of 2026-10-21: BUG-001, BUG-003 and BUG-006 of the 2026-10-05 marshmallow campaign run, emailed by Andrew to security@tidelift.com (marshmallow's SECURITY.md contact) on 2026-10-20 16:00 -0400 from astellman@stellman-greene.com, with patches 0001, 0003 and 0006 attached (sent-email.eml; the saved .eml shows the three attachment parts with empty bodies, to be checked against the Sent folder). Tidelift acknowledges within 2 business days. BUG-002 and BUG-004 are ordinary bugs, to go as public PRs. Reproduced the same day on dev b762ea2 (REPRO.md). 2026-10-21 11:25 -0400: Jeremy Katz (sonarsource.com, replying for security@tidelift.com, which was cc'd) confirmed all three behaviours against b762ea2 but ruled them not vulnerabilities (non-default, developer-chosen configurations; no documented security guarantee), and asked that all five bugs go as public GitHub issues or PRs on marshmallow-code/marshmallow (received-2026-10-21-tidelift.eml). Public PRs to be staged. 2026-10-21 ~20:30Z: Andrew opened all five as public PRs against dev: BUG-004 #3086 (also adds him to AUTHORS.rst), BUG-001 #3087, BUG-002 #3088 (builds on #3087), BUG-003 #3089, BUG-006 #3090 (stage-marshmallow-1021/, submission-terminal.txt). Reply to Tidelift with the links drafted (EMAIL-to-tidelift.md), not yet sent.
- 2026-10-21 16:31 -0400: reply with the five PR links sent to Jeremy Katz, cc security@tidelift.com.
- 2026-10-22: #3090 (marshmallow-006): Jared Deckard reproduced it and suggested returning a validation error instead of silently discarding the colliding unknown key. Awaiting Andrew on whether to switch the PR to raise.
- 2026-10-22: Andrew agreed; review change staged (push-006-review.sh) switching #3090 from skipping to raising.
- 2026-10-22 ~13:12 -0400: review change pushed (51a9ba9), PR retitled "Raise for an unknown key under INCLUDE that collides with a loaded field", reply to Jared posted (issuecomment-6346686603).
