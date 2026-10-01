# GPT review panel: six proposed upstream fixes (final versions)

This file is the complete instructions for a ChatGPT/Codex desktop session. The session reviews six patches Andrew Stellman plans to submit as pull requests. Two Claude panels have already reviewed them. This GPT panel is an independent second opinion from a different model family, and it does not see the Claude panels' output.

Run it with **Sol** sub-agents. Codex runs three sub-agents in parallel, so work through the roster in batches of three.

## Ground rules for every sub-agent

- Work only in the checkout directories created below and in the evidence folders named for each fix. Don't open any other file under `~/Documents/QPB`.
  - In particular, don't open `evidence/review-2026-09-27/`.
  - Don't open anything in `evidence/review-2026-09-28-v2/` except your own output file and, after step 3 below, `gpt/exec.md`.
- Never push, open a PR or issue, comment, or post anything anywhere.
- Never fabricate. If you didn't check something, say so. Paste command output verbatim.
- These are ordinary correctness bugs. Review them the way each project's maintainer would.

## Setup (orchestrating session, once)

For each repository, make a checkout at the pinned commit under `~/Documents/QPB/repos/review-gpt-2026-09-28/`. That path is git-ignored.

| Repo | Clone URL | Pinned commit |
|---|---|---|
| aiohttp | https://github.com/aio-libs/aiohttp | e11d2836203a21bec59095498e578d37801027e7 |
| otel | https://github.com/open-telemetry/opentelemetry-java-instrumentation | 78d71b585a77d7f2312c1b8751ff6c95a72722d7 |
| calibre | https://github.com/kovidgoyal/calibre | 7691f4f1a155d799afdfec99e2cdc2716c178402 |
| bionemo | https://github.com/NVIDIA-BioNeMo/bionemo-recipes | 11701476b005ca7bc489df924a398b8f12453f0b |

1. Clone and check out: `git clone --filter=blob:none <url> <dir>/base && git -C <dir>/base checkout --detach <commit>`.
2. For each fix, add a `v2-<ID>` worktree: `git -C <dir>/base worktree add --detach ../v2-<ID> <commit>`.
3. Apply that fix's patch in the worktree: `git -C <dir>/v2-<ID> apply <patch>`.

## The six fixes

All paths are under `~/Documents/QPB/evidence/`. The patch is always `<folder>/v2/0001-*.patch`. The PR description is `<folder>/v2/PR-DRAFT-final.md` where that file exists, otherwise `<folder>/v2/PR-DRAFT.md`.

| ID | Repo | Claim | Evidence folder |
|---|---|---|---|
| aiohttp-readuntil | aiohttp | `StreamReader.readuntil()` misses a separator whose bytes are split across two buffered chunks | `aiohttp-readuntil-split-separator/` |
| otel-urlparser | otel | `UrlParser` (incubator and reactor-netty) returns `"["` as the host for `http://[::1]:8080/` | `otel-java-urlparser-ipv6/` |
| otel-forwarded | otel | `ForwardedHostAddressAndPortExtractor.extractHost` records `"[2001"` for a bracketed IPv6 host | `otel-java-forwarded-host-ipv6/` |
| calibre-opds | calibre | the OPDS handlers return 500 instead of 404 for a malformed hex id | `calibre-opds-navcatalog/` |
| bionemo-amplify | bionemo | AMPLIFY `_pad_weights` builds padding rows in fp32 on the CPU regardless of the source embedding | `bionemo-amplify-pad-weights-dtype/` |
| bionemo-thd | bionemo | the THD context-parallel split drops remainder tokens when the padded length isn't divisible by 2 × cp_world_size | `bionemo-thd-cp-divisibility/` |

Reviewers may read the patch and the PR description from the start. Only after writing their initial verdicts (step 3 of the protocol) may they read the rest of each `v2/` folder: `CHANGES-FROM-V1.md`, `NOTES-FOR-ANDREW.md` and the logs.

## Maintainer context every reviewer needs

- A Linux NVMe maintainer replied to one of Andrew's earlier AI-assisted patches: "This is a very long explanation for a simple protocol fix. Just say something like ... Short and to the point."
- calibre's maintainer merged earlier fixes from the same tool, but said "None of these are security issues" about how they were framed.
- A psf/requests maintainer recently accused a similar report of being LLM-fabricated. Maintainers are primed to reject AI-generated PRs.
- Each project's own rules:
  - aiohttp's AGENTS.md requires a draft PR, human review and one specific AI disclosure line.
  - OpenTelemetry requires EasyCLA and recommends an `Assisted-by:` trailer.
  - bionemo-recipes has its own PR template, and CI waits for an NVIDIA member's `/ok to test`.

## Roster (batches of three)

**Batch 1**

1. **gpt-exec (executor, runs first).** Re-run red/green for every fix using each project's real toolchain on this Mac. For each fix:
   1. Apply only the patch's test changes and confirm the new tests fail for the claimed reason. Read the assertion text.
   2. Apply the rest and confirm the tests pass.
   3. Reverse only the non-test changes and confirm the tests fail again.
   4. Run the relevant existing tests before and after.

   This Mac can do what the Claude sandbox couldn't. Prioritise these:
   - **otel:** run the real Gradle tasks for both fixes (task paths from `./gradlew projects`): the tests for `:instrumentation-api`, `:instrumentation-api-incubator` and the reactor-netty 1.0 javaagent module, plus `spotlessCheck` and the checkstyle, errorprone and nullaway checks those modules run. Report the exact tasks and results. Neither Claude panel ran these.
   - **aiohttp:** `tests/test_streams.py` in pure-Python mode (`AIOHTTP_NO_EXTENSIONS=1`) and, if the build works, with the C extensions.
   - **bionemo-thd:** run `ci/scripts/check_copied_files.py` on the fixed worktree.
   - **calibre and bionemo:** these can't run their real tests without a full calibre build or a CUDA GPU. Say so; don't substitute silently.

   Write `~/Documents/QPB/evidence/review-2026-09-28-v2/gpt/exec.md`, ending with a table: ID | red | green | revert | suite | how it was run | PASS/FAIL.
2. **gpt-maintainer.** For each project, read its CONTRIBUTING, PR template and a few recently merged PRs, then answer: would I merge this as the maintainer, as written?
3. **gpt-correctness.** Try to break each fix. Find inputs or configurations where the fixed code is still wrong, or newly wrong, especially configurations the patch's own tests don't build. You may write and run small tests in your own scratch directory.

**Batch 2**

4. **gpt-not-a-bug.** Argue the maintainer's side: working as intended, documented behaviour, not worth the churn, or a better fix exists. Also check that no PR claims more than was demonstrated.
5. **gpt-slop-a.** Reject AI slop. Judge each patch and PR description as a maintainer who is tired of AI-generated PRs would. Check for:
   - message length out of proportion to the fix;
   - claims the evidence doesn't support;
   - restating the diff;
   - unrelated changes;
   - tests not in the project's own style;
   - generated-sounding padding;
   - leftover internal notes.
6. **gpt-slop-b.** Same charter as gpt-slop-a, reviewing independently.

**Batch 3**

7. **gpt-readability-code.** Readability of the code change: naming, structure, comments, and consistency with the surrounding code and the project's idioms.
8. **gpt-readability-tests.** Readability and quality of the tests. Would they catch a regression? Do they fail for the right reason? Are they minimal and idiomatic for this project?
9. **gpt-compat.** Backward compatibility: what behaviour changes for existing users, and whether the PR states each change.

## Blind protocol for reviewers 2–9

1. Form your view from the patch, the PR description and the source (compare `base` and `v2-<ID>`). Write your initial verdict for every fix.
2. Don't read other reviewers' files.
3. After your initial verdicts are written, you may read the rest of that fix's `v2/` folder and `gpt/exec.md`. If they change your mind, add a separate "after reading" note; don't overwrite your initial verdict.

## Output format

Each sub-agent writes `~/Documents/QPB/evidence/review-2026-09-28-v2/gpt/<id>.md` (for example `gpt/gpt-maintainer.md`), with the model name it ran as at the top. For each of the six fixes:

```
### <ID>
Verdict: SHIP | FIX-REQUIRED | REJECT
Confidence: high | medium | low
Findings: numbered, each with file:line or a quote from the patch/PR description, and what must change
```

- **REJECT** means it should not be submitted: not a bug, already fixed, harmful, or not worth a maintainer's time.
- **FIX-REQUIRED** means submit after the listed changes.

End with a short overall summary.

When all nine sub-agents are done, the orchestrating session writes `~/Documents/QPB/evidence/review-2026-09-28-v2/gpt/SUMMARY.md`. It contains:
- a table of fix × reviewer verdicts;
- the FIX-REQUIRED items for each fix, quoted from the reviews;
- the Gradle results from gpt-exec, verbatim.

Don't add your own opinions to the table.
