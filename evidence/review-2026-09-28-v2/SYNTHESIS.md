# Round 2 synthesis: six revised (v2) fixes

28 September 2026. Same panel design as round 1: two red/green executors (Sonnet) and 13 blind persona reviewers (5 Opus, 8 Sonnet). All reports are in this folder and were read in full by the orchestrating session.

## Result

**Executors.** All six passed red, then green, then red again after reverting the fix, with no suite regressions. How each was run:

| Fix | How it ran |
|---|---|
| aiohttp | Real project pytest |
| otel (both) | javac + JUnit console, not Gradle |
| calibre | Stubbed extraction harness |
| bionemo (both) | Verbatim-extraction harness on CPU torch |

For bionemo-thd, the repo's `check_copied_files.py` passes. Executor A also confirmed the checker does detect a deliberately broken copy.

**No correctness or security blocker on any fix.**
- The two adversarial reviewers that found the chi regression in round 1 tried again and found nothing that blocks. O3 ran 80,000 randomized aiohttp cases against a reference and got 0 mismatches. O4 fuzzed 20,000 chunkings: 1,597 mismatches on base, 0 on v2.
- O2 confirmed the otel-urlparser change closes round 1's security finding.
- S7 found no wrong factual claim.

| Fix | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aiohttp-readuntil | S | S | S | S | F | S | S | S | S | S | S | S | F |
| otel-urlparser | S | S | S | S | S | S | F | S | S | S | S | S | F |
| otel-forwarded | S | S | S | S | S | S | S | S | S | S | S | S | S |
| calibre-opds | S | S | S | S | F | S | S | S | F | S | S | S | S |
| bionemo-amplify | S | S | S | S | F | S | F | S | S | S | S | S | F |
| bionemo-thd | S | S | S | S | F | S | F | S | S | S | S | S | F |

S = SHIP, F = FIX-REQUIRED. No REJECT. Every FIX-REQUIRED falls into one of three groups:

1. **Steps only Andrew can take** (S8, O1):
   - rename aiohttp's `CHANGES/PRNUMBER.bugfix.rst` once the PR number exists;
   - run Gradle `check` and `spotlessCheck` for both otel patches on the Mac;
   - sign the OpenTelemetry EasyCLA;
   - expect NVIDIA's `/ok to test` gate on the bionemo PRs.
2. **PR text too long** (O5, S2, O1). v2 answered each round-1 item by adding text. The calibre and both bionemo descriptions have been cut to `v2/PR-DRAFT-final.md` using O5's rewrites; no code changed.
3. **Contested test and code preferences**, left as they are:
   - O5 wants the aiohttp tests trimmed from 8 functions to 4; S2, S3 and S4 would keep them.
   - O5 wants the bionemo-thd error message simplified and its control test dropped; S1 and S4 endorse both as written.
   - S2 wants the otel-urlparser IPv6 test split into separate methods; nobody else raised it.
   - S4 wants a stub-based calibre test; calibre deliberately has no OPDS tests.
   - O5 would revert the otel-forwarded comment to the house wording, which round 1 had asked to change.

## Before sending, per fix

| Fix | Use | Andrew's steps |
|---|---|---|
| aiohttp-readuntil | `v2/0001-*.patch`, `v2/PR-DRAFT.md` | Open as a draft (AGENTS.md), rename the fragment to the PR number, confirm the GitHub handle, review before marking ready |
| otel-urlparser | `v2/0001-*.patch`, `v2/PR-DRAFT.md` | Gradle `check` + `spotlessCheck` (commands in `v2/NOTES-FOR-ANDREW.md`), EasyCLA, check for a rebase against current `main` |
| otel-forwarded | `v2/0001-*.patch`, `v2/PR-DRAFT.md` | Same as otel-urlparser |
| calibre-opds | `v2/0001-*.patch`, `v2/PR-DRAFT-final.md` | None beyond reviewing it |
| bionemo-amplify | `v2/0001-*.patch`, `v2/PR-DRAFT-final.md` | Expect `/ok to test`; optionally hoist the test's import to the top of the file (O5) |
| bionemo-thd | `v2/0001-*.patch`, `v2/PR-DRAFT-final.md` | Expect `/ok to test` |

Not being filed: chi-gethead (the fix causes a regression), assertj-percentage (authorship clause), express-cookie (issue first, not a PR).
