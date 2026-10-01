# cobra: "Did you mean" suggestions count bytes instead of characters

Status: **open for review, [spf13/cobra#2514](https://github.com/spf13/cobra/pull/2514).** Submitted as a draft on 2026-10-01, the CLA signed and the PR marked ready the same day. See the submission record at the end.

## The project

[spf13/cobra](https://github.com/spf13/cobra) is the Go library most command-line tools in the Go world are built on: kubectl, Hugo, the GitHub CLI, Docker's CLI. It parses commands and flags, generates help, and provides shell completion.

One feature: if you mistype a subcommand, cobra suggests the closest real one.

```
$ app statsu
Error: unknown command "statsu" for "app"

Did you mean this?
        status
```

## The bug

The user guide (`site/content/user_guide.md:791`) says suggestions "use an implementation of Levenshtein distance. Every registered command that matches a minimum distance of 2 (ignoring case) will be displayed as a suggestion." Levenshtein distance counts **character** edits.

The function that computes it, `ld` in `cobra.go`, walks the two strings byte by byte. In Go, a string is UTF-8 bytes, and letters like `ü` or `é` take two bytes, so each one costs two edits instead of one. So a command named `über` is never suggested for `app ubr`: that's one edit, but `ld` says 3. ASCII names are unaffected, which is why nobody noticed.

## The fix

Convert both strings to runes (Go's word for Unicode characters) before comparing. The rest of the function is unchanged. The parameters were renamed so the rune slices can keep the names `s` and `t` that the loop body already uses.

```diff
 // ld compares two strings and returns the levenshtein distance between them.
-func ld(s, t string, ignoreCase bool) int {
+func ld(sStr, tStr string, ignoreCase bool) int {
 	if ignoreCase {
-		s = strings.ToLower(s)
-		t = strings.ToLower(t)
+		sStr = strings.ToLower(sStr)
+		tStr = strings.ToLower(tStr)
 	}
+	// Levenshtein distance counts character edits: compare runes, not UTF-8 bytes.
+	s, t := []rune(sStr), []rune(tStr)
 	d := make([][]int, len(s)+1)
```

The test adds one row to the existing `TestLevenshteinDistance` table in `cobra_test.go`:

```diff
+		{
+			name:       "Non-ASCII characters",
+			s:          "café",
+			t:          "cafe",
+			ignoreCase: false,
+			expected:   1,
+		},
```

Total: `cobra.go` +5/−3, `cobra_test.go` +7.

## Regression test

- **Red:** with only the new test row applied, it fails: `Expected ld: 1 / Got: 2`.
- **Green:** with the fix, it passes, and the whole suite (`go test ./...`) passes.
- **Revert:** with the fix taken out again, the test fails again for the same reason. This shows the test really checks the fix.
- Logs: `red.log`, `green.log`, `revert.log` in this folder.
- Two independent executors re-ran all three steps in the review panel with the same result.

## Knock-on effects

- `ld` has exactly one caller: `SuggestionsFor` (`command.go:867`). It only runs after the user has already typed an unknown command. Nothing else in cobra uses it.
- On 2026-10-01 I compared the suggestions before and after the fix, with commands `über`, `café`, `server`, `status` and the default minimum distance of 2:

| Typed | Before | After |
|---|---|---|
| `ubr` | none | `über` |
| `uber` | `über` | `über` |
| `Über` | `über` | `über` |
| `cfe` | none | `café` |
| `cafe` | `café` | `café` |
| `srv` | none | none |
| `statsu` | `status` | `status` |
| `serve` | `server` | `server` |
| `xyz` | none | none |

  Every ASCII case is identical. The only change is that non-ASCII names now get suggested when they're within 2 character edits, which is what the docs promise.
- Performance: two string-to-rune conversions per suggestion check, on an error path. The review panel (S6) found this negligible.

## Review history

- **Confirmed** by an independent confirmer: `docs/research/campaign-2026-09-29/confirm/LEDGER.md`.
- **Full panel** (2 executors and 13 reviewers): `evidence/review-2026-09-30-wave2/`. The code was approved. The PR text needed two fixes, both made:
  - It claimed "`cafx` does not suggest `café`", which is false. That sentence was removed.
  - It didn't mention open PR #2478. It now does.
- **Upstream check (2026-10-01):** cobra `main` is still at the commit we tested (`adbc881`), and the patch applies cleanly.

## Things to know before submitting

- **Open PR #2478** (not ours) rewrites the same `ld` function to use less memory. Its new test expects `ld("café", "cafe")` to be 2, which is the byte-counting behaviour this PR calls a bug. Our PR text says so and offers to rebase onto #2478. A maintainer may prefer to fold the fix into #2478 instead, and that's a fine outcome.
- cobra asks first-time contributors to sign a CLA (contributor licence agreement); a bot will prompt you on the PR.

## The PR as it will be submitted

**Title:** fix: count runes, not bytes, in suggestion distance

> ## Summary
>
> With a subcommand `über`, `app ubr` prints `Error: unknown command "ubr" for "app"` with no suggestion, while `app uber` suggests `über`.
>
> `ld` in cobra.go indexes its strings byte by byte, so each 2-byte letter like `ü` or `é` costs two edits (`ld("cafe", "café")` is 2, `ld("ubr", "über")` is 3). The fix converts both strings to `[]rune` before computing the distance.
>
> The user guide (site/content/user_guide.md) says suggestions "use an implementation of [Levenshtein distance](https://en.wikipedia.org/wiki/Levenshtein_distance). Every registered command that matches a minimum distance of 2 (ignoring case) will be displayed as a suggestion."
>
> Open PR #2478 rewrites `ld`, and its new test expects `ld("café", "cafe")` to be 2, the byte behaviour; happy to rebase onto it.
>
> ## Test plan
>
> - [x] Added a non-ASCII case to `TestLevenshteinDistance`; fails without the fix (got 2, want 1), passes with it
> - [x] `go test ./...`, `go vet ./...`, `gofmt -l .` clean
>
> Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

## To submit

```zsh
zsh ~/Documents/QPB/evidence/SUBMIT/submit-cobra-suggest-runes.sh
```

The script runs `go test ./...` first (it needs Go installed; `SKIP_TESTS=1` skips the check), then opens a **draft** PR.

## Submission record

- **Submitted:** 2026-10-01 by Andrew, after reviewing this file, using `submit-cobra-suggest-runes.sh`.
- **PR:** [spf13/cobra#2514](https://github.com/spf13/cobra/pull/2514), opened as a **draft** from `andrewstellman:suggest-distance-runes` into `spf13:main`; 1 commit, `4850963`.
- **Verified on GitHub (2026-10-01):**
  - The PR page shows the title and body exactly as above.
  - The PR diff (`/pull/2514.diff`) matches this folder's patch line for line, with the same blob hashes (`cobra.go` `d9cd241..b36954a`, `cobra_test.go` `f1c5b0a..ef35f24`).
  - The commit hash differs from the local `63a206f` only because `git am` re-creates the commit with a new committer date.
- **Bot:** CLAassistant has asked for the cobra CLA to be signed. That is pending, and it is Andrew's action.
- **Still to do on Andrew's side:** nothing until a maintainer responds. The CLA was signed and the PR marked ready on 2026-10-01 (see below).
- **2026-10-01:** Andrew reviewed the commit on GitHub and approved it to go live.
- **2026-10-01:** Andrew signed the CLA and marked the PR ready in the web UI. I re-checked the PR page the same day:
  - **Status:** **Open** (no longer Draft).
  - **Event:** "andrewstellman marked this pull request as ready for review October 1, 2026 14:17".
  - **CLA:** CLAassistant's comment now reads "All committers have signed the CLA."
  - **Head commit:** still `4850963`.
  - **Not visible logged out:** reviewers (none yet), and the CI checks result. I didn't see the checks.
- **Maintainer responses:** none yet.
