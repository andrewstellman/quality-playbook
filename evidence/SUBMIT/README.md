# Submission kit

**Every submission follows [`../SUBMISSION-PROTOCOL.md`](../SUBMISSION-PROTOCOL.md):** one bug at a time, explained to Andrew and written to `evidence/<slug>/REVIEW.md` before he runs a script, and the submission recorded there afterwards. No schedules, no batches.

One script per bug. Each opens a **draft** pull request from a branch on your fork
(`andrewstellman/<repo>`), using the v2 patch and the panel-reviewed PR text. Nothing
here was run by Claude; the scripts are for you to run in Terminal, one at a time.

Why drafts: a draft is a real PR that maintainers can see but that isn't asking for
review yet. You flip it to ready with one command after you've read it. aiohttp's
AGENTS.md requires drafts from AI-assisted work; for the others it just costs nothing
and is reversible. Going the other way (ready → draft) is possible but looks worse.

## Before the first script

```zsh
gh auth status          # must show andrewstellman
java -version           # otel only: needs JDK 25
```

## Scripts

| Script | Repo | Extra it does before pushing | What can stop it |
|---|---|---|---|
| `submit-aiohttp-readuntil.sh` | aio-libs/aiohttp | runs `tests/test_streams.py` in a venv; after the PR exists, renames the news fragment to the PR number and force-pushes | test failure; `git am` conflict |
| `submit-calibre-opds.sh` | kovidgoyal/calibre | nothing | `git am` conflict |
| `submit-bionemo-amplify.sh` | NVIDIA-BioNeMo/bionemo-recipes | `check_copied_files.py` | copied-file mismatch |
| `submit-bionemo-thd.sh` | NVIDIA-BioNeMo/bionemo-recipes | `check_copied_files.py` | copied-file mismatch; touches 10 files, most likely to conflict |
| `submit-otel-urlparser.sh` | open-telemetry/opentelemetry-java-instrumentation | Gradle `spotlessApply` + `check` on the touched modules (slow) | Gradle failure; EasyCLA bot after opening |
| `submit-otel-forwarded.sh` | same | Gradle `spotlessApply` + `:instrumentation-api:check` | same |
| `submit-express-issue.sh` | expressjs/express | opens an **issue**, not a PR | nothing |

Every script:

1. checks `gh` is logged in as andrewstellman;
2. forks the upstream repo if you don't have a fork yet (no-op otherwise);
3. clones the fork to `~/src/pr-work/<repo>` (skipped if already there);
4. makes a branch from current upstream `main`/`master` and applies the patch with `git am`;
5. runs the repo-specific check listed above;
6. pushes the branch to your fork and runs `gh pr create --draft`;
7. prints the PR number and URL.

It stops at the first failure. If `git am` fails, upstream has changed the file since
the patch was made: run `git am --abort` in `~/src/pr-work/<repo>` and paste the error
into the chat.

## After each PR is open

- Read the diff and the body on GitHub. The disclosure line says you reviewed it.
- otel: sign the EasyCLA when the bot comments.
- bionemo: an NVIDIA member has to comment `/ok to test` before CI runs.
- When you're satisfied: `gh pr ready <url>`.

## Not in this kit

chi GetHead (fix regressed in review), assertj (human-authorship clause), nvmet
CRTO/ANAGRPID (mailing list, already sent).

## zod: issues, not PRs (added 2026-09-30)

zod limits PR creation to collaborators (no outside PR since 2026-08-16; confirmed by reporters in #6629). Each `issue-zod-*.sh` pushes the fix to a branch on your fork, then opens an issue with a repro, the root cause and a compare link to that branch. The old `submit-zod-*.sh` PR scripts would fail and should not be used. Colin has closed bursts from single contributors.

The function-implement-zoderror fix is the least minimal; the issue says so.

## adonisjs/http-server (added 2026-09-30)

Full panel review in `evidence/review-2026-09-30-adonis/SYNTHESIS.md`. Four are ready: `submit-adonis-uuid-matcher.sh`, `submit-adonis-toroute-qs-mutation.sh`, `submit-adonis-unknown-content-type.sh`, `submit-adonis-cookie-maxage-zero.sh`. Each opens a draft PR against `9.x`, after running `npm run quick:test` and `npm run typecheck` on the Mac. redirect-qs-separator and reset-content-body need revision; lookup-route-error goes as an issue; send-error-object is dropped.

## Wave 2: cobra, setuptools, addressable, javalin (added 2026-10-01)

Full panel + focused re-review in `evidence/review-2026-09-30-wave2/SYNTHESIS.md`. Five ready, all drafts against the upstream default branch; each runs a local check first (`SKIP_TESTS=1` skips it):

| Script | Check it runs | After opening |
|---|---|---|
| `submit-cobra-complete-after-dashdash.sh` | `go test ./...`, vet, gofmt (needs Go) | sign cobra's CLA when prompted |
| `submit-cobra-suggest-runes.sh` | same | names open PR #2478 (same function) |
| `submit-setuptools-missing-dynamic-crash.sh` | venv + `pip install -e .[test]` + one test module | script renames the newsfragment to the PR number and force-pushes |
| `submit-addressable-route-from-base-query.sh` | `bundle exec rspec spec/addressable/uri_spec.rb` (needs bundler) | 19 outside PRs already waiting there |
| `submit-javalin-lowercase-redirect-contextpath.sh` | `./mvnw -pl javalin test -Dtest=TestRedirectToLowercasePathPlugin` (JDK 17+) | — |

Dropped: javalin precompressMaxSize (would reintroduce the #2616 OOM), setuptools MANIFEST `**` (pulls venv/node_modules into existing sdists), express sub-second maxAge issue. Held: both pydantic PRs. Pending Andrew: addressable `{+}` pct-encoding (addr-032).
