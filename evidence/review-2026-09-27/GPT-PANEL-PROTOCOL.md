# GPT review panel: nine proposed upstream fixes

This file is the complete instructions for a ChatGPT/Codex desktop session to review nine patches Andrew Stellman may submit as pull requests. A Claude panel (5 Opus and 8 Sonnet reviewers plus two test executors) is reviewing the same patches independently. This GPT panel is a second, different-model opinion. It does not see the Claude panel's output.

Run it with **Sol** sub-agents. Codex can run three sub-agents in parallel, so run the roster below in batches of three.

## Ground rules for every sub-agent

- Work only in the checkout directories named below and the evidence folders named for each fix. Do not open any other file under `~/Documents/QPB`, and in particular do not open anything in `~/Documents/QPB/evidence/review-2026-09-27/` except your own output file and, after step 3 below, the executor reports named there.
- Never push, open a PR or issue, comment, or post anything anywhere.
- Never fabricate. If you didn't check something, say so. Paste command output verbatim.
- The fixes are ordinary correctness bugs. Review them as a maintainer would.

## Setup (orchestrating session, once)

For each repository, make a checkout at the pinned commit under `~/Documents/QPB/repos/review-gpt-2026-09-27/` (that path is git-ignored):

| Repo | Clone URL | Pinned commit |
|---|---|---|
| aiohttp | https://github.com/aio-libs/aiohttp | e11d2836203a21bec59095498e578d37801027e7 |
| chi | https://github.com/go-chi/chi | 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc |
| express | https://github.com/expressjs/express | 9a34acf03cb818ff3f8bc40e44176e277a25cbb9 |
| otel | https://github.com/open-telemetry/opentelemetry-java-instrumentation | 78d71b585a77d7f2312c1b8751ff6c95a72722d7 |
| assertj | https://github.com/assertj/assertj | 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada |
| calibre | https://github.com/kovidgoyal/calibre | 7691f4f1a155d799afdfec99e2cdc2716c178402 |
| bionemo | https://github.com/NVIDIA-BioNeMo/bionemo-recipes | 11701476b005ca7bc489df924a398b8f12453f0b |

`git clone --filter=blob:none <url> <dir> && git -C <dir> checkout --detach <commit>`. Create one `base` checkout per repo and one `fixed-<ID>` worktree per fix with that fix's patch applied (`git worktree add --detach ../fixed-<ID> <commit>` then `git -C ../fixed-<ID> apply <patch>`).

## The nine fixes

| ID | Repo | Claim | Patch and PR draft (in `~/Documents/QPB/evidence/`) |
|---|---|---|---|
| aiohttp-readuntil | aiohttp | `StreamReader.readuntil()` misses a separator whose bytes are split across two buffered chunks | `aiohttp-readuntil-split-separator/` |
| chi-gethead | chi | `middleware.GetHead` inside a mounted sub-router ignores the sub-router's own HEAD handler and can return 405 | `chi-gethead-mount/` |
| express-cookie | express | `res.cookie` with `maxAge` under 1000 ms sends `Max-Age=0` with a future `Expires`, deleting the cookie | `express-cookie-subsecond-maxage/` |
| otel-urlparser | otel | `UrlParser` (incubator and reactor-netty) returns `"["` as the host for `http://[::1]:8080/` | `otel-java-urlparser-ipv6/` |
| otel-forwarded | otel | `ForwardedHostAddressAndPortExtractor.extractHost` records `"[2001"` for a bracketed IPv6 host | `otel-java-forwarded-host-ipv6/` |
| assertj-percentage | assertj | `Percentage.toString()` prints `2147483647%` for whole values above int range | `assertj-percentage-tostring-overflow/` |
| calibre-opds | calibre | content server `/opds/navcatalog` returns 500 instead of 404 for a malformed hex id | `calibre-opds-navcatalog/` (an alternative wider patch is in `alt/`) |
| bionemo-amplify | bionemo | AMPLIFY `_pad_weights` returns fp32 for a bf16 input | `bionemo-amplify-pad-weights-dtype/` |
| bionemo-thd | bionemo | THD context-parallel split drops remainder tokens when the length isn't divisible | `bionemo-thd-cp-divisibility/` |

In each evidence folder, reviewers may read the `0001-*.patch` file and `PR-DRAFT.md` from the start. They must not read `README.md` or the logs until after writing their initial verdicts (step 3).

## Maintainer context every reviewer needs

- A Linux NVMe maintainer replied to one of Andrew's earlier AI-assisted patches: "This is a very long explanation for a simple protocol fix. Just say something like ... Short and to the point."
- calibre's maintainer merged earlier fixes from the same tool but said "None of these are security issues" about how they were framed.
- A psf/requests maintainer recently accused a similar report of being LLM-fabricated. Maintainers are primed to reject AI-generated PRs.
- aiohttp's AGENTS.md requires a human-reviewed draft and an AI disclosure. assertj's CONTRIBUTING says contributors submit only content they authored 100%. express asks for an issue before a PR. OpenTelemetry has a generative-AI policy recommending an `Assisted-by:` trailer and requires EasyCLA.

## Roster (run in batches of three)

**Batch 1**
1. **gpt-exec (executor, runs first).** Re-run red/green for every fix on this Mac, using each project's real toolchain. Per fix: apply only the patch's test changes and confirm the new tests fail for the claimed reason (read the assertion text); apply the rest and confirm they pass; reverse only the non-test changes and confirm they fail again; run the relevant existing tests before and after. This Mac can do what the Claude sandbox could not, so prioritise these:
   - otel: run the real Gradle tasks, `./gradlew :instrumentation-api:test :instrumentation-api-incubator:test :instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent:test` (adjust task paths to what `./gradlew projects` shows) and `./gradlew spotlessCheck` plus the checkstyle/errorprone/nullaway checks those modules run, on both fixed worktrees.
   - bionemo-thd: the fix is copied into nine collator files; run the repository's own copy-consistency checker (look for `check_copied_files.py`) on the fixed worktree and report whether every copy matches.
   - aiohttp (`tests/test_streams.py`), chi (`go test ./...` and `go test -race ./middleware/...`), express (`npm test`), assertj (`./mvnw` for the Percentage test classes).
   - calibre and bionemo cannot run their real tests without a full calibre build or a CUDA GPU. Say so rather than substituting silently.
   Write `~/Documents/QPB/evidence/review-2026-09-27/gpt/exec.md` with a table: ID | red | green | revert | suite | how it was run | PASS/FAIL.
2. **gpt-maintainer.** For each project, read its CONTRIBUTING, PR template and a few recently merged PRs, then answer "would I merge this as the maintainer?"
3. **gpt-correctness.** Try to break each fix. Find inputs where the fixed code is still wrong or newly wrong. You may write and run small tests in your own scratch directory.

**Batch 2**
4. **gpt-not-a-bug.** Argue the maintainer's side: working as intended, documented behaviour, not worth the churn, or a better fix exists.
5. **gpt-slop-a.** Reject AI slop. Judge each patch and PR draft the way a maintainer who is tired of AI-generated PRs would: message length proportional to the fix, no claims the evidence doesn't support, no restating the diff, no unrelated changes, tests in the project's own style, nothing that reads as generated padding.
6. **gpt-slop-b.** Same charter as gpt-slop-a, reviewing independently. Pay particular attention to the PR-DRAFT.md text and the commit message.

**Batch 3**
7. **gpt-readability-code.** Readability of the code change itself: naming, structure, consistency with the surrounding code and the project's idioms.
8. **gpt-readability-tests.** Readability and quality of the tests: would they catch a regression, do they fail for the right reason, are they minimal and idiomatic for this project.
9. **gpt-compat.** Backward compatibility: what behaviour changes for existing users of each project, and whether that change is acceptable or needs a note.

## Blind protocol for reviewers 2–9

1. Form your view from the patch, the PR draft and the source (compare `base` and `fixed-<ID>`). Write your initial verdict for every fix.
2. Do not read other reviewers' files.
3. After your initial verdicts are written, you may read that fix's `README.md` in its evidence folder and `~/Documents/QPB/evidence/review-2026-09-27/gpt/exec.md`. If they change your mind, add a separate "after reading README/exec" note; do not overwrite your initial verdict.

## Output format

Each sub-agent writes `~/Documents/QPB/evidence/review-2026-09-27/gpt/<id>.md` (for example `gpt/gpt-maintainer.md`). Put the model name you ran as at the top. For each of the nine fixes:

```
### <ID>
Verdict: SHIP | FIX-REQUIRED | REJECT
Confidence: high | medium | low
Findings: numbered, each with file:line or a quote from the patch/PR draft, and what must change
```

REJECT means it should not be submitted (not a bug, already fixed, harmful, or not worth a maintainer's time). FIX-REQUIRED means submit after the listed changes. End with a short overall summary.

When all nine sub-agents are done, the orchestrating session writes `~/Documents/QPB/evidence/review-2026-09-27/gpt/SUMMARY.md`: a table of fix × reviewer verdicts and the list of FIX-REQUIRED items per fix, quoted from the reviews. It should not add its own opinions to the table.
