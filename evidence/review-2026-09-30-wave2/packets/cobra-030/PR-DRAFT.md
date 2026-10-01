**Title:** fix: count runes, not bytes, in suggestion distance

## Summary

With a subcommand `über`, `app ubr` prints `Error: unknown command "ubr" for "app"` with no suggestion; with `uber` it suggests `uber`. Likewise `cafx` does not suggest `café`.

`ld` in cobra.go indexes its strings byte by byte, so each 2-byte letter like `ü` or `é` costs two edits (`ld("cafe", "café")` is 2, `ld("ubr", "über")` is 3). The fix converts both strings to `[]rune` before computing the distance.

The user guide (site/content/user_guide.md) says suggestions "use an implementation of [Levenshtein distance](https://en.wikipedia.org/wiki/Levenshtein_distance). Every registered command that matches a minimum distance of 2 (ignoring case) will be displayed as a suggestion."

## Test plan

- [x] Added a non-ASCII case to `TestLevenshteinDistance`; fails without the fix (got 2, want 1), passes with it
- [x] `go test ./...`, `go vet ./...`, `gofmt -l .` clean

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
